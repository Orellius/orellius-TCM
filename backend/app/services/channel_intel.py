"""Channel Intelligence Agent — proactive ghost agent for channel exploration and profiling.

Provides channel discovery (forward chain + mention extraction), history scraping
with deep metadata, channel profiling (posting patterns, media distribution),
and member analysis for groups/supergroups.
"""

import asyncio
import logging
import re
import time
from collections import Counter

from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.tl.functions.channels import GetParticipantsRequest
from telethon.tl.functions.messages import GetHistoryRequest
from telethon.tl.types import (
    ChannelParticipantsSearch,
    MessageMediaDocument,
    MessageMediaPhoto,
)

from app.config import settings
from app.services.ghost_engine import GhostEngine

logger = logging.getLogger(__name__)

# Rate limiting: max 2 concurrent scrape operations
_scrape_semaphore = asyncio.Semaphore(2)

# In-memory store for channel profiles
_channel_profiles: dict[str, dict] = {}
_discovered_channels: dict[str, dict] = {}

# Regex for @username and t.me links
_MENTION_RE = re.compile(r"(?:@|(?:https?://)?t\.me/)([a-zA-Z_][a-zA-Z0-9_]{3,})")


async def discover_channels(
    client: TelegramClient,
    seed_channel: str,
    depth: int = 1,
) -> list[dict]:
    """Discover related channels from a seed channel's recent messages.

    Collects forwarded-from channels and @username/t.me mentions,
    optionally recursing to the specified depth.

    Args:
        client: Connected Telethon client.
        seed_channel: Channel username or ID to start from.
        depth: How many hops to follow (default 1, max 3).

    Returns:
        List of discovered channel dicts with discovery method.
    """
    depth = min(depth, 3)  # Safety cap
    discovered: dict[str, dict] = {}
    visited: set[str] = set()

    async def _discover_one(channel_id: str, current_depth: int):
        if current_depth > depth or channel_id in visited:
            return
        visited.add(channel_id)

        try:
            async with _scrape_semaphore:
                messages = await _fetch_history(client, channel_id, limit=50)

            for msg in messages:
                # Forward-based discovery
                if msg.forward and hasattr(msg.forward, "from_id"):
                    fwd_id = msg.forward.from_id
                    if hasattr(fwd_id, "channel_id"):
                        ch_id = str(fwd_id.channel_id)
                        if ch_id not in discovered:
                            from_name = getattr(msg.forward, "from_name", None)
                            discovered[ch_id] = {
                                "channel_id": ch_id,
                                "title": from_name or f"Channel {ch_id}",
                                "username": None,
                                "discovery_method": "forward",
                                "discovered_from": channel_id,
                                "depth": current_depth,
                            }

                # Mention-based discovery
                if msg.raw_text:
                    for match in _MENTION_RE.finditer(msg.raw_text):
                        username = match.group(1).lower()
                        if username not in discovered and username not in visited:
                            discovered[username] = {
                                "channel_id": None,
                                "title": f"@{username}",
                                "username": username,
                                "discovery_method": "mention",
                                "discovered_from": channel_id,
                                "depth": current_depth,
                            }

            # Recurse into discovered channels
            if current_depth < depth:
                for ch_key in list(discovered.keys()):
                    ch = discovered[ch_key]
                    target = ch.get("username") or ch.get("channel_id")
                    if target:
                        await asyncio.sleep(1)  # Rate limit
                        await _discover_one(target, current_depth + 1)

        except FloodWaitError as e:
            logger.warning(f"FloodWait during discovery: sleeping {e.seconds}s")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            logger.error(f"Discovery error for {channel_id}: {e}")

    await _discover_one(seed_channel, 1)

    result = list(discovered.values())
    # Cache results
    for ch in result:
        key = ch.get("username") or ch.get("channel_id", "")
        _discovered_channels[key] = ch

    logger.info(f"Discovered {len(result)} channels from seed '{seed_channel}'")
    return result


async def scrape_history(
    client: TelegramClient,
    channel: str,
    limit: int | None = None,
) -> list[dict]:
    """Scrape message history from a channel with deep metadata extraction.

    Args:
        client: Connected Telethon client.
        channel: Channel username or ID.
        limit: Max messages to fetch (default from settings).

    Returns:
        List of message metadata dicts.
    """
    if limit is None:
        limit = settings.history_scrape_depth

    async with _scrape_semaphore:
        messages = await _fetch_history(client, channel, limit=limit)

    results = []
    for msg in messages:
        meta = GhostEngine.extract_deep_metadata(msg)
        results.append(
            {
                "message_id": msg.id,
                "date": msg.date.isoformat() if msg.date else None,
                "text": msg.raw_text or "",
                "has_media": bool(msg.media),
                "media_type": _get_media_type(msg),
                "views": getattr(msg, "views", None),
                "forwards": getattr(msg, "forwards", None),
                "metadata": meta,
            }
        )

    logger.info(f"Scraped {len(results)} messages from '{channel}'")
    return results


async def profile_channel(
    client: TelegramClient,
    channel: str,
) -> dict:
    """Build a channel profile from recent message history.

    Aggregates posting frequency by hour, media type distribution,
    peak hours, forwarded-from source counts.
    """
    async with _scrape_semaphore:
        messages = await _fetch_history(client, channel, limit=200)

    if not messages:
        return {"channel": channel, "error": "No messages found"}

    # Posting frequency by hour
    hour_counts = Counter()
    media_types = Counter()
    forward_sources = Counter()
    total_views = 0
    dates = []

    for msg in messages:
        if msg.date:
            hour_counts[msg.date.hour] += 1
            dates.append(msg.date)

        media_type = _get_media_type(msg)
        media_types[media_type] += 1

        if msg.forward and hasattr(msg.forward, "from_name"):
            forward_sources[msg.forward.from_name or "Unknown"] += 1

        total_views += getattr(msg, "views", 0) or 0

    # Calculate posting frequency
    if len(dates) >= 2:
        time_span = (max(dates) - min(dates)).total_seconds() / 3600  # hours
        posts_per_hour = len(messages) / max(time_span, 1)
    else:
        posts_per_hour = 0

    # Peak hours (top 3)
    peak_hours = [h for h, _ in hour_counts.most_common(3)]

    profile = {
        "channel": channel,
        "message_count": len(messages),
        "posts_per_hour": round(posts_per_hour, 2),
        "peak_hours": peak_hours,
        "hour_distribution": dict(sorted(hour_counts.items())),
        "media_distribution": dict(media_types.most_common()),
        "top_forward_sources": dict(forward_sources.most_common(10)),
        "avg_views": round(total_views / max(len(messages), 1)),
        "date_range": {
            "oldest": min(dates).isoformat() if dates else None,
            "newest": max(dates).isoformat() if dates else None,
        },
        "profiled_at": time.time(),
    }

    # Cache profile
    _channel_profiles[channel] = profile

    logger.info(f"Profiled channel '{channel}': {len(messages)} msgs, {posts_per_hour:.1f} posts/hr")
    return profile


async def get_members(
    client: TelegramClient,
    channel: str,
    limit: int = 200,
) -> list[dict]:
    """Get member list for groups/supergroups (not broadcast channels).

    Args:
        client: Connected Telethon client.
        channel: Channel username or ID.
        limit: Max members to fetch.

    Returns:
        List of member info dicts.
    """
    try:
        entity = await client.get_entity(channel)
        if not hasattr(entity, "megagroup") or not entity.megagroup:
            return []  # Broadcast channels don't expose members

        participants = await client(
            GetParticipantsRequest(
                channel=entity,
                filter=ChannelParticipantsSearch(""),
                offset=0,
                limit=min(limit, 200),
                hash=0,
            )
        )

        members = []
        for user in participants.users:
            members.append(
                {
                    "id": user.id,
                    "first_name": user.first_name or "",
                    "last_name": user.last_name or "",
                    "username": user.username or "",
                    "is_bot": getattr(user, "bot", False),
                }
            )

        logger.info(f"Retrieved {len(members)} members from '{channel}'")
        return members

    except FloodWaitError as e:
        logger.warning(f"FloodWait for members: sleeping {e.seconds}s")
        await asyncio.sleep(e.seconds)
        return []
    except Exception as e:
        logger.error(f"Failed to get members for '{channel}': {e}")
        return []


def get_cached_profiles() -> dict[str, dict]:
    """Return all cached channel profiles."""
    return dict(_channel_profiles)


def get_discovered_channels() -> dict[str, dict]:
    """Return all discovered channels."""
    return dict(_discovered_channels)


# ── Internal helpers ──────────────────────────────────────────


async def _fetch_history(
    client: TelegramClient,
    channel: str,
    limit: int = 100,
) -> list:
    """Paginated GetHistoryRequest with rate limiting and flood handling."""
    messages = []
    offset_id = 0

    try:
        entity = await client.get_entity(channel)
    except Exception as e:
        logger.error(f"Cannot resolve channel '{channel}': {e}")
        return []

    while len(messages) < limit:
        batch_size = min(100, limit - len(messages))
        try:
            result = await client(
                GetHistoryRequest(
                    peer=entity,
                    offset_id=offset_id,
                    offset_date=None,
                    add_offset=0,
                    limit=batch_size,
                    max_id=0,
                    min_id=0,
                    hash=0,
                )
            )

            if not result.messages:
                break

            messages.extend(result.messages)
            offset_id = result.messages[-1].id

            # Rate limit between pagination calls
            await asyncio.sleep(1)

        except FloodWaitError as e:
            logger.warning(f"FloodWait: sleeping {e.seconds}s then resuming")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            logger.error(f"History fetch error for '{channel}': {e}")
            break

    return messages[:limit]


def _get_media_type(msg) -> str:
    """Classify message media type."""
    if not msg.media:
        return "text"
    if isinstance(msg.media, MessageMediaPhoto):
        return "photo"
    if isinstance(msg.media, MessageMediaDocument):
        doc = msg.media.document
        if doc and doc.mime_type:
            if doc.mime_type.startswith("video/"):
                return "video"
            if doc.mime_type.startswith("audio/"):
                return "audio"
        return "document"
    return "other"
