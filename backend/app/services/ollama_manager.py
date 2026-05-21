"""Ollama Model Manager — handles dynamic model loading/unloading for 64GB RAM constraint.

On a Mac Studio M4 with 64GB unified memory, we cannot run a 70B model alongside
multiple 32B models simultaneously. This manager ensures only one large model is loaded
at a time by explicitly managing Ollama's model lifecycle via its REST API.

Model assignments:
  - Translator:   aya-expanse:32b (~19GB) — Arabic/Persian/Russian → Hebrew (Cohere multilingual)
  - Orchestrator: llama3.3:70b    (~40GB) — Task delegation and system logic
  - Reviewer:     deepseek-r1:32b (~19GB) — Translation validation and reasoning
  - Daemon:       qwen2.5-coder:32b (~19GB) — System health and code analysis
"""

import asyncio
import logging
import time

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Keep-alive duration: how long Ollama keeps the model loaded after last request.
# Set to "0" for immediate unload after completion, or "5m" for 5 minutes.
DEFAULT_KEEP_ALIVE = "0"


def _build_model_map() -> dict[str, str]:
    """Build model assignments from settings."""
    return {
        "translator": settings.ollama_model_translator,
        "reviewer": settings.ollama_model_reviewer,
        "daemon": settings.ollama_model_daemon,
        "orchestrator": settings.ollama_model_orchestrator,
    }


def get_ollama_base() -> str:
    """Return the Ollama base URL from settings."""
    return settings.ollama_base_url


class OllamaManager:
    """Manages Ollama model lifecycle to prevent OOM on 64GB systems.

    Key behaviors:
    - Before loading a model, unloads any currently loaded large model
    - Uses Ollama's keep_alive=0 to auto-unload after each request
    - Provides an explicit unload method for aggressive memory reclaim
    - Tracks which model is currently loaded to minimize unnecessary swaps
    """

    def __init__(self):
        self._current_model: str | None = None
        self._lock = asyncio.Lock()
        self._last_used: dict[str, float] = {}

    async def ensure_model_loaded(self, role: str) -> str:
        """Ensure the model for the given role is loaded and ready.

        Returns the model name to use in API calls.
        """
        model_map = _build_model_map()
        model = model_map.get(role)
        if not model:
            raise ValueError(f"Unknown agent role: {role}. Valid roles: {list(model_map.keys())}")

        async with self._lock:
            if self._current_model == model:
                logger.info(f"Model {model} already loaded for role '{role}'")
                self._last_used[model] = time.time()
                return model

            # Unload current model first to free RAM
            if self._current_model:
                await self._unload_model(self._current_model)

            # Pre-load the new model with a dummy request
            await self._preload_model(model)
            self._current_model = model
            self._last_used[model] = time.time()

            return model

    async def _preload_model(self, model: str) -> None:
        """Pre-load a model into Ollama's memory by sending a warmup request."""
        logger.info(f"Pre-loading model: {model}")

        try:
            async with httpx.AsyncClient(timeout=settings.ollama_preload_timeout) as client:
                # Use the generate endpoint with keep_alive to load the model
                resp = await client.post(
                    f"{settings.ollama_base_url}/api/generate",
                    json={
                        "model": model,
                        "prompt": "hello",
                        "options": {"num_predict": 1},
                        "keep_alive": settings.ollama_keep_alive,
                    },
                )
                if resp.status_code == 200:
                    logger.info(f"Model {model} loaded successfully")
                else:
                    logger.error(f"Failed to preload {model}: {resp.status_code} {resp.text}")
        except httpx.TimeoutException:
            logger.warning(f"Timeout preloading {model} — model may still be loading")
        except Exception as e:
            logger.error(f"Error preloading model {model}: {e}")

    async def _unload_model(self, model: str) -> None:
        """Explicitly unload a model from Ollama's memory."""
        logger.info(f"Unloading model: {model}")

        try:
            async with httpx.AsyncClient(timeout=settings.ollama_unload_timeout) as client:
                # Setting keep_alive to 0 with an empty prompt triggers unload
                resp = await client.post(
                    f"{settings.ollama_base_url}/api/generate",
                    json={
                        "model": model,
                        "prompt": "",
                        "keep_alive": 0,
                    },
                )
                if resp.status_code == 200:
                    logger.info(f"Model {model} unloaded")
                else:
                    logger.warning(f"Unload response for {model}: {resp.status_code}")
        except Exception as e:
            logger.warning(f"Error unloading model {model}: {e}")

        self._current_model = None

    async def unload_all(self) -> None:
        """Unload all models — call on pipeline stop or shutdown."""
        async with self._lock:
            if self._current_model:
                await self._unload_model(self._current_model)
            self._current_model = None

    async def get_loaded_models(self) -> list[dict]:
        """Query Ollama for currently loaded models."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{settings.ollama_base_url}/api/ps")
                if resp.status_code == 200:
                    return resp.json().get("models", [])
        except Exception as e:
            logger.error(f"Failed to query loaded models: {e}")
        return []

    async def get_installed_models(self) -> list[str]:
        """Query Ollama for all installed (pulled) models."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{settings.ollama_base_url}/api/tags")
                if resp.status_code == 200:
                    models = resp.json().get("models", [])
                    return [m.get("name", "") for m in models]
        except Exception as e:
            logger.error(f"Failed to query installed models: {e}")
        return []

    async def health_check(self) -> dict:
        """Check Ollama server status including installed models."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{settings.ollama_base_url}/api/version")
                if resp.status_code == 200:
                    loaded = await self.get_loaded_models()
                    installed = await self.get_installed_models()
                    return {
                        "healthy": True,
                        "version": resp.json().get("version", "unknown"),
                        "loaded_models": [m.get("name") for m in loaded],
                        "installed_models": installed,
                        "current_model": self._current_model,
                    }
        except Exception:
            pass
        return {"healthy": False, "installed_models": [], "loaded_models": [], "current_model": None}

    def get_openai_base_url(self) -> str:
        """Return the OpenAI-compatible base URL for Ollama."""
        return f"{settings.ollama_base_url}/v1"

    def get_model_for_role(self, role: str) -> str:
        """Get the model name assigned to a role."""
        model_map = _build_model_map()
        model = model_map.get(role)
        if not model:
            raise ValueError(f"Unknown role: {role}")
        return model


# Singleton instance
ollama_manager = OllamaManager()
