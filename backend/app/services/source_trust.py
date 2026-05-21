"""Source trust / channel reliability tracking.

Tracks channel accuracy over time using PostgreSQL.
Trust levels: verified | trusted | neutral | suspect | untrusted
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TypedDict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings

logger = logging.getLogger(__name__)


class SourceTrustInfo(TypedDict):
    channel_id: str
    trust_level: str  # verified | trusted | neutral | suspect | untrusted
    accuracy_score: float  # 0.0-1.0
    total_posts: int
    corroborated_posts: int


# ── Lazy async engine ─────────────────────────────────────────

_engine = None
_session_factory = None


def _get_engine():
    global _engine, _session_factory
    if _engine is None:
        _engine = create_async_engine(settings.database_url, pool_size=5, max_overflow=10)
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine, _session_factory


# ── Trust Level Computation ───────────────────────────────────


def compute_trust_level(accuracy: float, total_posts: int, consistency: float) -> str:
    """Compute trust level from metrics.

    Rules:
    - <5 posts → neutral (insufficient data)
    - accuracy ≥ 0.85 + consistency ≥ 0.7 → verified
    - accuracy ≥ 0.70 → trusted
    - accuracy ≥ 0.50 → neutral
    - accuracy ≥ 0.30 → suspect
    - accuracy < 0.30 → untrusted
    """
    if total_posts < 5:
        return "neutral"
    if accuracy >= 0.85 and consistency >= 0.7:
        return "verified"
    if accuracy >= 0.70:
        return "trusted"
    if accuracy >= 0.50:
        return "neutral"
    if accuracy >= 0.30:
        return "suspect"
    return "untrusted"


# ── Public API ────────────────────────────────────────────────


async def get_channel_trust(channel_id: str) -> SourceTrustInfo | None:
    """Get trust info for a channel. Returns None if channel not tracked yet."""
    from app.db.models import SourceTrust

    _, factory = _get_engine()
    async with factory() as session:
        result = await session.execute(select(SourceTrust).where(SourceTrust.channel_id == channel_id))
        row = result.scalar_one_or_none()

        if row is None:
            # Auto-create entry for new channels
            new_entry = SourceTrust(
                channel_id=channel_id,
                trust_level="neutral",
                accuracy_score=0.5,
                total_posts=0,
                corroborated_posts=0,
                content_consistency=0.5,
            )
            session.add(new_entry)
            await session.commit()
            return SourceTrustInfo(
                channel_id=channel_id,
                trust_level="neutral",
                accuracy_score=0.5,
                total_posts=0,
                corroborated_posts=0,
            )

        return SourceTrustInfo(
            channel_id=row.channel_id,
            trust_level=row.trust_level,
            accuracy_score=row.accuracy_score,
            total_posts=row.total_posts,
            corroborated_posts=row.corroborated_posts,
        )


async def update_trust_on_publish(channel_id: str, was_corroborated: bool) -> None:
    """Update trust metrics after a message is published.

    Increments total_posts, and corroborated_posts if the message was corroborated
    by another channel. Recomputes trust level.
    """
    from app.db.models import SourceTrust

    _, factory = _get_engine()
    async with factory() as session:
        result = await session.execute(select(SourceTrust).where(SourceTrust.channel_id == channel_id))
        row = result.scalar_one_or_none()

        if row is None:
            row = SourceTrust(
                channel_id=channel_id,
                trust_level="neutral",
                accuracy_score=0.5,
                total_posts=0,
                corroborated_posts=0,
                content_consistency=0.5,
            )
            session.add(row)

        row.total_posts += 1
        if was_corroborated:
            row.corroborated_posts += 1

        # Recompute accuracy and trust level
        if row.total_posts > 0:
            row.accuracy_score = row.corroborated_posts / row.total_posts
        row.trust_level = compute_trust_level(
            row.accuracy_score,
            row.total_posts,
            row.content_consistency,
        )
        row.last_updated = datetime.now(UTC)

        await session.commit()
        logger.info(f"Trust updated for {channel_id}: {row.trust_level} (accuracy={row.accuracy_score:.2f})")


async def set_channel_trust(channel_id: str, trust_level: str) -> SourceTrustInfo | None:
    """Manual trust level override for an operator."""
    from app.db.models import SourceTrust

    valid_levels = {"verified", "trusted", "neutral", "suspect", "untrusted"}
    if trust_level not in valid_levels:
        return None

    _, factory = _get_engine()
    async with factory() as session:
        result = await session.execute(select(SourceTrust).where(SourceTrust.channel_id == channel_id))
        row = result.scalar_one_or_none()

        if row is None:
            row = SourceTrust(
                channel_id=channel_id,
                trust_level=trust_level,
                accuracy_score=0.5,
                total_posts=0,
                corroborated_posts=0,
                content_consistency=0.5,
            )
            session.add(row)
        else:
            row.trust_level = trust_level
            row.last_updated = datetime.now(UTC)

        await session.commit()
        return SourceTrustInfo(
            channel_id=row.channel_id,
            trust_level=row.trust_level,
            accuracy_score=row.accuracy_score,
            total_posts=row.total_posts,
            corroborated_posts=row.corroborated_posts,
        )


async def list_all_trust() -> list[SourceTrustInfo]:
    """List all tracked channel trust entries."""
    from app.db.models import SourceTrust

    _, factory = _get_engine()
    async with factory() as session:
        result = await session.execute(select(SourceTrust).order_by(SourceTrust.channel_id))
        rows = result.scalars().all()
        return [
            SourceTrustInfo(
                channel_id=r.channel_id,
                trust_level=r.trust_level,
                accuracy_score=r.accuracy_score,
                total_posts=r.total_posts,
                corroborated_posts=r.corroborated_posts,
            )
            for r in rows
        ]
