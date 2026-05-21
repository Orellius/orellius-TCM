"""Stripe billing integration for SaaS plans.

Plans:
  - Free: 1 channel, 100 messages/day
  - Pro: 10 channels, unlimited messages
  - Enterprise: custom limits
"""

import logging
from datetime import UTC, datetime

import stripe
from sqlalchemy import select

from app.config import settings
from app.db.models import Subscription
from app.db.session import async_session

logger = logging.getLogger(__name__)

PLAN_LIMITS = {
    "free": {"max_channels": 1, "max_messages_per_day": 100},
    "pro": {"max_channels": 10, "max_messages_per_day": -1},  # -1 = unlimited
    "enterprise": {"max_channels": -1, "max_messages_per_day": -1},
}


def _init_stripe():
    """Initialize Stripe API key from settings."""
    key = getattr(settings, "stripe_secret_key", "")
    if key:
        stripe.api_key = key
        return True
    return False


async def get_subscription(org_id: int) -> dict | None:
    """Get the current subscription for an organization."""
    async with async_session() as session:
        result = await session.execute(select(Subscription).where(Subscription.org_id == org_id))
        sub = result.scalar_one_or_none()
        if not sub:
            return None
        return {
            "plan": sub.plan,
            "status": sub.status,
            "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
            "messages_used_today": sub.messages_used_today,
        }


async def check_plan_limits(org_id: int) -> dict:
    """Check if an org is within its plan limits. Returns limits info."""
    async with async_session() as session:
        result = await session.execute(select(Subscription).where(Subscription.org_id == org_id))
        sub = result.scalar_one_or_none()
        plan = sub.plan if sub else "free"
        limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])

        messages_used = sub.messages_used_today if sub else 0
        max_messages = limits["max_messages_per_day"]

        return {
            "plan": plan,
            "within_limits": max_messages == -1 or messages_used < max_messages,
            "messages_used": messages_used,
            "messages_limit": max_messages,
            "channels_limit": limits["max_channels"],
        }


async def increment_message_count(org_id: int) -> None:
    """Increment daily message counter for billing."""
    async with async_session() as session:
        result = await session.execute(select(Subscription).where(Subscription.org_id == org_id))
        sub = result.scalar_one_or_none()
        if sub:
            # Reset counter if new day
            now = datetime.now(UTC)
            if sub.messages_reset_at and sub.messages_reset_at.date() < now.date():
                sub.messages_used_today = 0
                sub.messages_reset_at = now
            sub.messages_used_today += 1
            await session.commit()


async def create_checkout_session(org_id: int, plan: str, success_url: str, cancel_url: str) -> str | None:
    """Create a Stripe checkout session. Returns the checkout URL."""
    if not _init_stripe():
        return None

    price_map = getattr(settings, "stripe_price_ids", {})
    price_id = price_map.get(plan)
    if not price_id:
        return None

    try:
        checkout = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"org_id": str(org_id), "plan": plan},
        )
        return checkout.url
    except stripe.StripeError as e:
        logger.error(f"Stripe checkout error: {e}")
        return None


async def handle_stripe_webhook(payload: bytes, sig_header: str) -> bool:
    """Process Stripe webhook events."""
    if not _init_stripe():
        return False

    webhook_secret = getattr(settings, "stripe_webhook_secret", "")
    if not webhook_secret:
        return False

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except (ValueError, stripe.SignatureVerificationError):
        return False

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        org_id = int(session["metadata"]["org_id"])
        plan = session["metadata"]["plan"]

        async with async_session() as db:
            result = await db.execute(select(Subscription).where(Subscription.org_id == org_id))
            sub = result.scalar_one_or_none()
            if sub:
                sub.plan = plan
                sub.stripe_customer_id = session.get("customer")
                sub.stripe_subscription_id = session.get("subscription")
                sub.status = "active"
            else:
                sub = Subscription(
                    org_id=org_id,
                    plan=plan,
                    stripe_customer_id=session.get("customer"),
                    stripe_subscription_id=session.get("subscription"),
                    status="active",
                )
                db.add(sub)
            await db.commit()

    elif event["type"] == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        stripe_sub_id = subscription["id"]

        async with async_session() as db:
            result = await db.execute(select(Subscription).where(Subscription.stripe_subscription_id == stripe_sub_id))
            sub = result.scalar_one_or_none()
            if sub:
                sub.status = "canceled"
                sub.plan = "free"
                await db.commit()

    return True
