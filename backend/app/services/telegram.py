"""Telegram client wrapper for shared session management."""

import logging

from telethon import TelegramClient

from app.config import settings

logger = logging.getLogger(__name__)

_client: TelegramClient | None = None


async def get_telegram_client() -> TelegramClient:
    """Get or create the shared Telegram client.

    Uses the existing authenticated session managed by telegram_session.py.
    Falls back to settings.telegram_phone for legacy compatibility.
    """
    global _client
    if _client is None or not _client.is_connected():
        # Prefer using the session-managed client if available
        try:
            from app.services.telegram_session import _connected
            from app.services.telegram_session import get_client as get_session_client

            if _connected:
                _client = await get_session_client()
                if _client.is_connected():
                    logger.info("Telegram client reused from session manager")
                    return _client
        except Exception:
            pass

        # Fallback: create new client (requires existing .session file or env phone)
        _client = TelegramClient(
            settings.telegram_session_name,
            settings.telegram_api_id,
            settings.telegram_api_hash,
        )
        phone = settings.telegram_phone or None
        await _client.start(phone=phone)
        logger.info("Telegram client connected via fallback")
    return _client


async def download_media(client: TelegramClient, message, output_dir: str) -> str | None:
    """Download media from a Telegram message to the local filesystem."""
    if message.media:
        path = await client.download_media(message, file=output_dir)
        logger.info(f"Downloaded media to {path}")
        return path
    return None


async def disconnect() -> None:
    """Disconnect the Telegram client."""
    global _client
    if _client and _client.is_connected():
        await _client.disconnect()
        _client = None
        logger.info("Telegram client disconnected")
