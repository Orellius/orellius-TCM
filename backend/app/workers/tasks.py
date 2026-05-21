"""Background job tasks using Redis-backed queue.

Provides a simple job queue abstraction using Redis lists and JSON payloads.
Supports retry with exponential backoff and dead-letter queue.

Note: ARQ was considered but has a redis<6 version constraint incompatible
with our redis 7.x dependency. This module provides equivalent functionality.
"""

import asyncio
import json
import logging
import time
import traceback
import uuid
from collections.abc import Callable

logger = logging.getLogger(__name__)

QUEUE_KEY = "orellius:jobs:pending"
DEAD_LETTER_KEY = "orellius:jobs:dead"
JOB_STATUS_PREFIX = "orellius:job:"

MAX_RETRIES = 3
RETRY_BASE_DELAY = 30  # seconds


async def _get_redis():
    from app.redis_client import get_redis

    return await get_redis()


async def enqueue_job(task_name: str, **kwargs) -> str:
    """Enqueue a background job. Returns job ID."""
    job_id = str(uuid.uuid4())
    payload = {
        "id": job_id,
        "task": task_name,
        "kwargs": kwargs,
        "created_at": time.time(),
        "retries": 0,
    }
    try:
        r = await _get_redis()
        await r.lpush(QUEUE_KEY, json.dumps(payload))
        await r.setex(f"{JOB_STATUS_PREFIX}{job_id}", 3600, json.dumps({"status": "queued"}))
        logger.info(f"[job] Enqueued {task_name} as {job_id}")
    except Exception as e:
        logger.error(f"[job] Failed to enqueue {task_name}: {e}")
    return job_id


async def get_job_status(job_id: str) -> dict:
    """Get the status of a job by ID."""
    try:
        r = await _get_redis()
        data = await r.get(f"{JOB_STATUS_PREFIX}{job_id}")
        if data:
            return json.loads(data)
    except Exception:
        pass
    return {"status": "unknown"}


# ── Task Registry ─────────────────────────────────────────────

_task_registry: dict[str, Callable] = {}


def register_task(name: str):
    """Decorator to register a task function."""

    def wrapper(func):
        _task_registry[name] = func
        return func

    return wrapper


@register_task("process_media")
async def process_media_job(message_id: str, state: dict) -> dict:
    """Background media processing (watermark removal + stamping)."""
    from app.agents.media_handler import process_media_node

    logger.info(f"[job] Processing media for {message_id}")
    result = await process_media_node(state)
    return {"ok": True, "message_id": message_id, "media_items": result.get("media_items", [])}


@register_task("scrape_channel")
async def scrape_channel_job(channel: str, limit: int = 100) -> dict:
    """Background channel scraping."""
    from app.services.channel_intel import scrape_history
    from app.services.telegram_session import get_client

    logger.info(f"[job] Scraping {channel} (limit={limit})")
    client = await get_client()
    messages = await scrape_history(client, channel, limit=limit)
    return {"ok": True, "channel": channel, "count": len(messages)}


@register_task("health_check")
async def health_check_job() -> dict:
    """Periodic health check."""
    from sqlalchemy import text

    from app.db.session import engine

    services = {}
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        services["postgres"] = "ok"
    except Exception:
        services["postgres"] = "down"

    try:
        r = await _get_redis()
        await r.ping()
        services["redis"] = "ok"
    except Exception:
        services["redis"] = "down"

    return {"services": services}


# ── Worker Loop ───────────────────────────────────────────────


async def run_worker(max_jobs: int = 10, poll_interval: float = 1.0):
    """Run the background job worker loop.

    Usage: asyncio.run(run_worker())
    Or from CLI: python -m app.workers.tasks
    """
    logger.info(f"[worker] Starting with max_jobs={max_jobs}")

    while True:
        try:
            r = await _get_redis()
            raw = await r.brpop(QUEUE_KEY, timeout=int(poll_interval))

            if not raw:
                continue

            payload = json.loads(raw[1])
            job_id = payload["id"]
            task_name = payload["task"]
            kwargs = payload.get("kwargs", {})
            retries = payload.get("retries", 0)

            func = _task_registry.get(task_name)
            if not func:
                logger.error(f"[worker] Unknown task: {task_name}")
                continue

            # Update status
            await r.setex(f"{JOB_STATUS_PREFIX}{job_id}", 3600, json.dumps({"status": "running"}))

            try:
                result = await asyncio.wait_for(func(**kwargs), timeout=600)
                await r.setex(
                    f"{JOB_STATUS_PREFIX}{job_id}",
                    3600,
                    json.dumps({"status": "completed", "result": result}),
                )
                logger.info(f"[worker] Completed {task_name} ({job_id})")

            except Exception as e:
                logger.error(f"[worker] Task {task_name} ({job_id}) failed: {e}")

                if retries < MAX_RETRIES:
                    # Retry with exponential backoff
                    delay = RETRY_BASE_DELAY * (2**retries)
                    payload["retries"] = retries + 1
                    await asyncio.sleep(delay)
                    await r.lpush(QUEUE_KEY, json.dumps(payload))
                    await r.setex(
                        f"{JOB_STATUS_PREFIX}{job_id}",
                        3600,
                        json.dumps({"status": "retrying", "retry": retries + 1, "error": str(e)}),
                    )
                else:
                    # Dead letter queue
                    payload["error"] = str(e)
                    payload["traceback"] = traceback.format_exc()
                    await r.lpush(DEAD_LETTER_KEY, json.dumps(payload))
                    await r.setex(
                        f"{JOB_STATUS_PREFIX}{job_id}",
                        86400,
                        json.dumps({"status": "failed", "error": str(e)}),
                    )

        except Exception as e:
            logger.error(f"[worker] Loop error: {e}")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(run_worker())
