"""Situational awareness engine -- post correlation via Redis sorted sets.

Indexes pipeline messages by region:event_type for fast 24h lookups.
Detects escalation patterns (3+ posts in same region within 6h).
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, TypedDict

logger = logging.getLogger(__name__)


class RelatedMessage(TypedDict):
    message_id: str
    title: str
    source_channel: str
    timestamp: float
    event_type: str
    threat_level: str
    countries: list[str]


# -- Redis Key Patterns -------------------------------------------------------
# geo:events:{region}:{event_type} -> sorted set (score=timestamp, value=msg_id)
# geo:msg:{msg_id} -> hash with title, channel, timestamp, countries, event_type, threat_level

_KEY_PREFIX = "geo:events"
_MSG_PREFIX = "geo:msg"
_TTL_SECONDS = 48 * 3600  # 48h auto-cleanup


async def index_post(
    message_id: str,
    region: str,
    event_type: str,
    title: str,
    source_channel: str,
    timestamp: float,
    countries: list[str],
    threat_level: str = "medium",
) -> None:
    """Write post to Redis sorted sets for future correlation lookups.

    Creates two keys:
    - Sorted set for region:event_type (score=timestamp)
    - Hash with post metadata for display
    """
    from app.redis_client import get_redis

    if not region or not event_type:
        return

    try:
        r = await get_redis()
        region_key = f"{_KEY_PREFIX}:{region.lower()}:{event_type.lower()}"
        msg_key = f"{_MSG_PREFIX}:{message_id}"

        pipe = r.pipeline()

        # Add to sorted set (score = timestamp for range queries)
        pipe.zadd(region_key, {message_id: timestamp})
        pipe.expire(region_key, _TTL_SECONDS)

        # Store message metadata
        pipe.hset(
            msg_key,
            mapping={
                "title": title or "",
                "channel": source_channel,
                "timestamp": str(timestamp),
                "countries": json.dumps(countries),
                "event_type": event_type,
                "threat_level": threat_level,
            },
        )
        pipe.expire(msg_key, _TTL_SECONDS)

        await pipe.execute()
        logger.debug(f"[{message_id[:8]}] Indexed in {region_key}")

    except Exception as e:
        logger.warning(f"Failed to index post {message_id[:8]}: {e}")


async def find_related_posts(
    region: str,
    event_type: str,
    timestamp: float,
    lookback_hours: int = 24,
    exclude_id: str | None = None,
    limit: int = 5,
) -> list[RelatedMessage]:
    """Query Redis for recent posts in the same region:event_type.

    Returns up to `limit` related messages from the last `lookback_hours`.
    """
    from app.redis_client import get_redis

    if not region or not event_type:
        return []

    try:
        r = await get_redis()
        region_key = f"{_KEY_PREFIX}:{region.lower()}:{event_type.lower()}"

        min_ts = timestamp - (lookback_hours * 3600)
        msg_ids: list[str] = await r.zrangebyscore(region_key, min_ts, timestamp)

        if exclude_id:
            msg_ids = [mid for mid in msg_ids if mid != exclude_id]

        # Get most recent first, limit
        msg_ids = msg_ids[-limit:]
        msg_ids.reverse()

        results: list[RelatedMessage] = []
        for mid in msg_ids:
            msg_key = f"{_MSG_PREFIX}:{mid}"
            data = await r.hgetall(msg_key)
            if not data:
                continue

            countries_raw = data.get("countries", "[]")
            try:
                countries = json.loads(countries_raw)
            except (json.JSONDecodeError, TypeError):
                countries = []

            results.append(
                RelatedMessage(
                    message_id=mid,
                    title=data.get("title", ""),
                    source_channel=data.get("channel", ""),
                    timestamp=float(data.get("timestamp", 0)),
                    event_type=data.get("event_type", ""),
                    threat_level=data.get("threat_level", "medium"),
                    countries=countries,
                )
            )

        return results

    except Exception as e:
        logger.warning(f"Failed to find related posts for {region}/{event_type}: {e}")
        return []


async def detect_escalation(
    region: str,
    event_type: str,
    window_hours: int = 6,
    threshold: int = 3,
) -> dict[str, Any] | None:
    """Detect escalation: threshold+ posts in same region within window_hours.

    Returns escalation info dict or None.
    """
    from app.redis_client import get_redis

    if not region or not event_type:
        return None

    try:
        r = await get_redis()
        region_key = f"{_KEY_PREFIX}:{region.lower()}:{event_type.lower()}"

        now = time.time()
        min_ts = now - (window_hours * 3600)
        count = await r.zcount(region_key, min_ts, now)

        if count >= threshold:
            return {
                "status": "DEVELOPING",
                "region": region,
                "event_type": event_type,
                "post_count": count,
                "window_hours": window_hours,
            }

        return None

    except Exception as e:
        logger.warning(f"Failed to detect escalation for {region}/{event_type}: {e}")
        return None


def generate_situation_brief(
    related: list[RelatedMessage],
    geo_context: dict[str, Any],
    escalation: dict[str, Any] | None,
) -> str:
    """Generate a template-based situation brief. No LLM call.

    Examples:
    - "DEVELOPING: 4 reports from southern_lebanon (kinetic_strike) in 6h"
    - "2 related reports from eastern_ukraine in 24h"
    - "" (empty if no related posts)
    """
    parts: list[str] = []

    if escalation:
        parts.append(
            f"DEVELOPING: {escalation['post_count']} reports from "
            f"{escalation['region']} ({escalation['event_type']}) "
            f"in {escalation['window_hours']}h"
        )

    conflict = geo_context.get("conflict_context")
    if conflict:
        flags = " ".join(c.get("flag", "") for c in geo_context.get("countries", []))
        parts.append(f"{flags} {conflict}")

    if related and not escalation:
        parts.append(f"{len(related)} related report(s) in 24h")

    return " | ".join(parts)
