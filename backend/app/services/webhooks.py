"""Webhook delivery service.

Delivers events to registered webhook URLs with HMAC-SHA256 signature
verification. Uses ARQ job queue for async delivery with retry.

Events: message.published, alert.hfc, pipeline.started, pipeline.stopped, message.failed
"""

import hashlib
import hmac
import json
import logging
import time

import httpx
from sqlalchemy import select

from app.db.models import Webhook
from app.db.session import async_session

logger = logging.getLogger(__name__)


def _sign_payload(payload: bytes, secret: str) -> str:
    """Generate HMAC-SHA256 signature for webhook payload."""
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


async def deliver_webhook(webhook_id: int, event: str, data: dict) -> bool:
    """Deliver a single webhook. Returns True if successful."""
    async with async_session() as session:
        result = await session.execute(select(Webhook).where(Webhook.id == webhook_id))
        webhook = result.scalar_one_or_none()

        if not webhook or not webhook.active:
            return False

        payload = json.dumps(
            {
                "event": event,
                "data": data,
                "timestamp": int(time.time()),
                "webhook_id": webhook_id,
            }
        ).encode()

        signature = _sign_payload(payload, webhook.secret)

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    webhook.url,
                    content=payload,
                    headers={
                        "Content-Type": "application/json",
                        "X-Orellius-Signature": f"sha256={signature}",
                        "X-Orellius-Event": event,
                    },
                )
                if resp.status_code >= 200 and resp.status_code < 300:
                    logger.info(f"Webhook {webhook_id} delivered: {event} -> {resp.status_code}")
                    return True
                else:
                    logger.warning(f"Webhook {webhook_id} failed: {event} -> {resp.status_code}")
                    return False
        except Exception as e:
            logger.error(f"Webhook {webhook_id} delivery error: {e}")
            return False


async def dispatch_event(event: str, data: dict, org_id: int | None = None) -> int:
    """Dispatch an event to all matching webhooks for an org.

    Returns count of webhooks queued.
    """
    async with async_session() as session:
        query = select(Webhook).where(Webhook.active.is_(True))
        if org_id is not None:
            query = query.where(Webhook.org_id == org_id)

        result = await session.execute(query)
        webhooks = result.scalars().all()

        count = 0
        for wh in webhooks:
            events = wh.events or []
            if event in events or "*" in events:
                # Try to enqueue via ARQ, fall back to direct delivery
                try:
                    from arq.connections import RedisSettings, create_pool

                    from app.config import settings

                    redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
                    await redis.enqueue_job("deliver_webhook_job", wh.id, event, data)
                    await redis.close()
                except Exception:
                    # Fallback: deliver directly
                    await deliver_webhook(wh.id, event, data)
                count += 1

        return count


async def list_webhooks(org_id: int) -> list[dict]:
    """List all webhooks for an organization."""
    async with async_session() as session:
        result = await session.execute(
            select(Webhook).where(Webhook.org_id == org_id).order_by(Webhook.created_at.desc())
        )
        return [
            {
                "id": wh.id,
                "url": wh.url,
                "events": wh.events,
                "active": wh.active,
                "created_at": wh.created_at.isoformat() if wh.created_at else None,
            }
            for wh in result.scalars().all()
        ]


async def create_webhook(org_id: int, url: str, events: list[str]) -> dict:
    """Create a new webhook."""
    import secrets

    secret = secrets.token_hex(32)

    async with async_session() as session:
        wh = Webhook(
            org_id=org_id,
            url=url,
            events=events,
            secret=secret,
            active=True,
        )
        session.add(wh)
        await session.commit()

        return {
            "id": wh.id,
            "url": wh.url,
            "events": wh.events,
            "secret": secret,
            "active": True,
        }


async def delete_webhook(webhook_id: int, org_id: int) -> bool:
    """Delete a webhook."""
    async with async_session() as session:
        result = await session.execute(select(Webhook).where(Webhook.id == webhook_id, Webhook.org_id == org_id))
        wh = result.scalar_one_or_none()
        if not wh:
            return False
        await session.delete(wh)
        await session.commit()
        return True
