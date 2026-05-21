"""System Daemon Agent — monitors health and performs analysis using local Ollama (qwen2.5-coder:32b)."""

import asyncio
import logging
import traceback

import httpx

from app.config import settings
from app.services.ollama_manager import get_ollama_base, ollama_manager
from app.ws_server import ConnectionManager

logger = logging.getLogger(__name__)


class SystemDaemon:
    """Background daemon that monitors system health and can analyze errors with local LLM."""

    def __init__(self, ws_manager: ConnectionManager, app_state=None):
        self.ws_manager = ws_manager
        self.app_state = app_state
        self._running = False
        self._error_counts: dict[str, int] = {}
        self._health_status: dict[str, str] = {
            "redis": "unknown",
            "postgres": "unknown",
            "qdrant": "unknown",
            "ollama": "unknown",
            "telegram": "unknown",
        }

    async def start(self) -> None:
        """Start the health monitoring loop."""
        self._running = True
        logger.info("System Daemon started")

        while self._running:
            await self._check_health()
            await asyncio.sleep(30)

    async def stop(self) -> None:
        self._running = False
        logger.info("System Daemon stopped")

    async def _check_health(self) -> None:
        """Run all health checks and broadcast status."""
        await self._check_redis()
        await self._check_postgres()
        await self._check_qdrant()
        await self._check_ollama()

        await self.ws_manager.broadcast(
            {
                "type": "agent_status",
                "agent": "System Daemon",
                "status": "running",
                "activity": f"Health: {self._health_status}",
            }
        )

        # Broadcast structured health report for Monitor Health tab
        import time

        await self.ws_manager.broadcast(
            {
                "type": "health_report",
                "timestamp": time.time(),
                "services": dict(self._health_status),
                "error_counts": dict(self._error_counts),
            }
        )

    async def _check_redis(self) -> None:
        try:
            import redis.asyncio as aioredis

            r = aioredis.from_url(settings.redis_url)
            await r.ping()
            await r.close()
            self._health_status["redis"] = "healthy"
            self._error_counts["redis"] = 0
        except Exception as e:
            self._health_status["redis"] = "unhealthy"
            self._error_counts["redis"] = self._error_counts.get("redis", 0) + 1
            if self._error_counts["redis"] <= 3:
                logger.warning(f"Redis health check failed: {e}")

    async def _check_postgres(self) -> None:
        try:
            # Use raw asyncpg to avoid the greenlet dependency of SQLAlchemy async
            import asyncpg

            # Parse connection URL: postgresql+asyncpg://user:pass@host:port/db → strip driver prefix
            db_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
            conn = await asyncpg.connect(db_url, timeout=5)
            await conn.execute("SELECT 1")
            await conn.close()
            self._health_status["postgres"] = "healthy"
            self._error_counts["postgres"] = 0
        except Exception as e:
            self._health_status["postgres"] = "unhealthy"
            self._error_counts["postgres"] = self._error_counts.get("postgres", 0) + 1
            if self._error_counts["postgres"] <= 3:
                logger.warning(f"PostgreSQL health check failed: {e}")
            # Suppress repeated identical errors after 3 consecutive failures

    async def _check_qdrant(self) -> None:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{settings.qdrant_url}/healthz", timeout=5)
                if resp.status_code == 200:
                    self._health_status["qdrant"] = "healthy"
                    self._error_counts["qdrant"] = 0
                else:
                    raise Exception(f"Status {resp.status_code}")
        except Exception as e:
            self._health_status["qdrant"] = "unhealthy"
            self._error_counts["qdrant"] = self._error_counts.get("qdrant", 0) + 1
            if self._error_counts["qdrant"] <= 3:
                logger.warning(f"Qdrant health check failed: {e}")

    async def _check_ollama(self) -> None:
        """Check Ollama server health."""
        try:
            health = await ollama_manager.health_check()
            if health.get("healthy"):
                self._health_status["ollama"] = "healthy"
                self._error_counts["ollama"] = 0
            else:
                raise Exception("Ollama unreachable or unhealthy")
        except Exception as e:
            self._health_status["ollama"] = "unhealthy"
            self._error_counts["ollama"] = self._error_counts.get("ollama", 0) + 1
            if self._error_counts["ollama"] <= 3:
                logger.warning(f"Ollama health check failed: {e}")

    async def analyze_error(self, agent_name: str, error: Exception, context: str = "") -> str | None:
        """Use qwen2.5-coder to analyze an error and suggest a fix.

        Only loads the daemon model when actually needed — doesn't keep it in memory.
        """
        logger.error(f"Error from {agent_name}: {error}")

        try:
            model = await ollama_manager.ensure_model_loaded("daemon")

            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"{get_ollama_base()}/api/chat",
                    json={
                        "model": model,
                        "messages": [
                            {
                                "role": "system",
                                "content": (
                                    "You are a system operations AI analyzing errors in a Python/Telegram "
                                    "OSINT pipeline. Provide a brief diagnosis and actionable fix."
                                ),
                            },
                            {
                                "role": "user",
                                "content": (
                                    f"Agent: {agent_name}\n"
                                    f"Error: {error}\n"
                                    f"Traceback: {traceback.format_exc()}\n"
                                    f"Context: {context}"
                                ),
                            },
                        ],
                        "stream": False,
                        "options": {"num_predict": 512},
                        "keep_alive": "5m",
                    },
                )
                resp.raise_for_status()
                suggestion = resp.json()["message"]["content"]

            logger.info(f"Daemon suggestion for {agent_name}: {suggestion[:200]}")

            await self.ws_manager.broadcast(
                {
                    "type": "agent_status",
                    "agent": "System Daemon",
                    "status": "running",
                    "activity": f"Diagnosed error in {agent_name}",
                }
            )

            # Broadcast daemon insight for Monitor Health tab
            import time as _time

            await self.ws_manager.broadcast(
                {
                    "type": "daemon_insight",
                    "timestamp": _time.time(),
                    "agent": agent_name,
                    "error": str(error),
                    "suggestion": suggestion,
                }
            )

            return suggestion

        except Exception as e:
            logger.error(f"Daemon analysis failed: {e}")
            return None

    async def report_error(self, agent_name: str, error: Exception) -> None:
        """Called by other agents to report errors to the daemon."""
        await self.ws_manager.broadcast(
            {
                "type": "agent_status",
                "agent": agent_name,
                "status": "error",
                "activity": str(error),
            }
        )
