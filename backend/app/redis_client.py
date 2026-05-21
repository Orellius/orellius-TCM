import json
import logging
from typing import Any

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger(__name__)

# Lazy-initialized Redis connection pool
_pool: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """Get or create the Redis connection."""
    global _pool
    if _pool is None:
        _pool = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=20,
        )
    return _pool


async def publish_event(channel: str, data: dict[str, Any]) -> None:
    """Publish an event to a Redis pub/sub channel."""
    r = await get_redis()
    await r.publish(channel, json.dumps(data))


async def push_to_stream(stream: str, data: dict[str, Any]) -> str:
    """Push a message to a Redis Stream. Returns the message ID."""
    r = await get_redis()
    msg_id = await r.xadd(stream, {"payload": json.dumps(data)})
    return msg_id


async def read_from_stream(
    stream: str,
    group: str,
    consumer: str,
    count: int = 1,
    block_ms: int = 5000,
) -> list[dict[str, Any]]:
    """Read messages from a Redis Stream consumer group."""
    r = await get_redis()
    # Ensure the consumer group exists
    try:
        await r.xgroup_create(stream, group, id="0", mkstream=True)
    except aioredis.ResponseError:
        pass  # Group already exists

    messages = await r.xreadgroup(group, consumer, {stream: ">"}, count=count, block=block_ms)
    results = []
    for _, entries in messages:
        for msg_id, fields in entries:
            payload = json.loads(fields["payload"])
            payload["_msg_id"] = msg_id
            results.append(payload)
            # Acknowledge the message
            await r.xack(stream, group, msg_id)
    return results


async def close_redis() -> None:
    """Close the Redis connection."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
