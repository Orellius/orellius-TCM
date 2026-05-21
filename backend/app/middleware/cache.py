"""Redis-backed response cache with configurable TTL.

Usage:
    @cached(ttl=60)
    async def my_endpoint():
        ...

Cache is automatically busted when POST/PUT/DELETE requests hit related resources.
"""

import hashlib
import json
import logging
from collections.abc import Callable
from functools import wraps

from fastapi import Request, Response

logger = logging.getLogger(__name__)

# In-memory fallback when Redis is unavailable
_memory_cache: dict[str, tuple[float, str]] = {}
_MAX_MEMORY_CACHE = 500


def _cache_key(request: Request) -> str:
    """Generate cache key from request path + query params."""
    raw = f"{request.url.path}?{request.url.query}"
    return f"cache:{hashlib.md5(raw.encode()).hexdigest()}"


async def _get_redis():
    """Get Redis client, return None if unavailable."""
    try:
        from app.redis_client import get_redis

        return await get_redis()
    except Exception:
        return None


def cached(ttl: int = 60):
    """Decorator for caching GET endpoint responses in Redis."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Find the Request object from args/kwargs
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            if request is None:
                request = kwargs.get("request")

            # Only cache GET requests
            if request and request.method != "GET":
                return await func(*args, **kwargs)

            if not request:
                return await func(*args, **kwargs)

            key = _cache_key(request)

            # Try Redis first
            redis = await _get_redis()
            if redis:
                try:
                    cached_data = await redis.get(key)
                    if cached_data:
                        data = json.loads(cached_data)
                        return Response(
                            content=cached_data,
                            media_type="application/json",
                            headers={"X-Cache": "HIT"},
                        )
                except Exception:
                    pass

            # Try memory cache
            import time

            now = time.time()
            if key in _memory_cache:
                expires, data = _memory_cache[key]
                if expires > now:
                    return Response(
                        content=data,
                        media_type="application/json",
                        headers={"X-Cache": "HIT"},
                    )
                else:
                    del _memory_cache[key]

            # Cache miss — execute handler
            result = await func(*args, **kwargs)

            # Store result
            try:
                if isinstance(result, Response):
                    serialized = result.body.decode() if hasattr(result, "body") else None
                else:
                    serialized = json.dumps(result)

                if serialized:
                    if redis:
                        try:
                            await redis.setex(key, ttl, serialized)
                        except Exception:
                            pass

                    # Also store in memory cache
                    if len(_memory_cache) < _MAX_MEMORY_CACHE:
                        _memory_cache[key] = (now + ttl, serialized)

            except Exception:
                pass

            return result

        return wrapper

    return decorator


async def bust_cache(pattern: str = "cache:*") -> int:
    """Invalidate cached entries matching a pattern."""
    redis = await _get_redis()
    count = 0
    if redis:
        try:
            cursor = 0
            while True:
                cursor, keys = await redis.scan(cursor, match=pattern, count=100)
                if keys:
                    await redis.delete(*keys)
                    count += len(keys)
                if cursor == 0:
                    break
        except Exception:
            pass

    # Clear memory cache too
    _memory_cache.clear()
    return count
