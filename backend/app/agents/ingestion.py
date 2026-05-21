"""Ingestion Agent — manages Telethon scraper and normalizes incoming messages."""

import logging
import time
from collections.abc import Awaitable, Callable
from pathlib import Path

from telethon import TelegramClient, events

from app.config import settings
from app.orchestrator.state import PipelineState
from app.services import restricted_downloader
from app.services.ghost_engine import GhostEngine

logger = logging.getLogger(__name__)


def _ensure_media_dir() -> Path:
    """Ensure the media download directory exists and return its path."""
    media_path = Path(settings.media_dir)
    media_path.mkdir(parents=True, exist_ok=True)
    return media_path


async def ingest_node(state: PipelineState) -> PipelineState:
    """LangGraph node: normalize the raw ingested message.

    In the real-time flow, messages arrive from the Telethon event handler
    and are pre-populated in state. This node performs any additional
    normalization or enrichment needed.
    """
    logger.info(f"[{state['message_id']}] Ingesting from {state['source_channel']}")

    # Normalize text: strip excessive whitespace, etc.
    text = state["original_text"].strip()
    state["original_text"] = text

    return state


def _cleanup_stale_handlers(client: TelegramClient) -> None:
    """Remove any leftover NewMessage handlers from previous scraper instances.

    After a hot-reload or pipeline restart, old handlers may linger on the
    singleton Telethon client, causing every message to be processed multiple
    times. This wipes all NewMessage handlers so we start fresh.
    """
    removed = 0
    for cb, handler_instance in list(client.list_event_handlers()):
        if isinstance(handler_instance, events.NewMessage):
            client.remove_event_handler(cb, handler_instance)
            removed += 1
    if removed:
        logger.info(f"Cleaned up {removed} stale NewMessage handler(s) from Telethon client")


class TelegramScraper:
    """Real-time Telegram channel scraper using Telethon.

    Reuses an already-connected TelegramClient (from telegram_session)
    rather than creating its own, to avoid session conflicts.
    """

    def __init__(self, on_message: Callable[..., Awaitable[None]]):
        """
        Args:
            on_message: Async callback(source_channel, text, media_items, timestamp, raw_metadata)
        """
        self.on_message = on_message
        self._running = False
        self._handler_ref = None
        self._client: TelegramClient | None = None
        # Track processed Telegram message IDs to prevent duplicates from
        # catch_up() replays or hot-reload double-handler scenarios.
        self._seen_msg_ids: set[int] = set()
        self._seen_max = 2000  # evict oldest when exceeded

    async def start(self, client: TelegramClient, channels: list[str]) -> None:
        """Register an event handler on the existing connected client.

        Does NOT call client.start() or run_until_disconnected() — the
        FastAPI/uvicorn event loop keeps the client alive. We just add
        our NewMessage handler to an already-authenticated session.
        """
        # Clean up any stale handlers from a previous scraper instance
        # (e.g. after hot-reload or pipeline restart)
        _cleanup_stale_handlers(client)

        self._client = client
        self._running = True

        # Ensure media directory exists at startup
        _ensure_media_dir()

        # Pre-resolve channels — skip any that Telethon can't find
        resolved = []
        for ch in channels:
            try:
                entity = await client.get_input_entity(ch)
                resolved.append(entity)
                logger.info(f"Resolved channel: {ch}")
            except Exception as e:
                logger.warning(f"Skipping unresolvable channel '{ch}': {e}")

        if not resolved:
            logger.error("No channels could be resolved — scraper has nothing to monitor")
            return

        logger.info(f"Monitoring {len(resolved)}/{len(channels)} channels (skipped {len(channels) - len(resolved)})")

        @client.on(events.NewMessage(chats=resolved))
        async def handler(event):
            if not self._running:
                return

            # Dedup: skip messages already processed (catch_up replays, double handlers)
            tg_msg_id = event.message.id
            if tg_msg_id in self._seen_msg_ids:
                logger.debug(f"Skipping duplicate Telegram message {tg_msg_id}")
                return
            self._seen_msg_ids.add(tg_msg_id)
            if len(self._seen_msg_ids) > self._seen_max:
                # Evict oldest entries (sets are unordered, but this is good enough)
                to_remove = list(self._seen_msg_ids)[:len(self._seen_msg_ids) - self._seen_max + 500]
                self._seen_msg_ids -= set(to_remove)

            try:
                # Extract deep metadata via Ghost Engine
                raw_metadata = None
                try:
                    raw_metadata = GhostEngine.extract_deep_metadata(event.message)
                except Exception as meta_err:
                    logger.warning(f"Deep metadata extraction failed: {meta_err}")

                # Extract and download media items (using RestrictedDownloader)
                media_items = []
                msg_id = event.message.id

                if event.photo:
                    file_id = str(event.photo.id)
                    prefix = f"{msg_id}_{file_id}"
                    try:
                        local_path, file_type = await restricted_downloader.download_media(
                            client,
                            event.message,
                            prefix=prefix,
                        )
                        logger.info(f"Downloaded photo {file_id} → {local_path}")
                    except Exception as dl_err:
                        logger.error(f"Failed to download photo {file_id}: {dl_err}")
                        local_path = None
                        file_type = "photo"

                    media_items.append(
                        {
                            "file_id": file_id,
                            "file_type": file_type,
                            "local_path": str(local_path) if local_path else None,
                            "stamped_path": None,
                        }
                    )
                elif event.video:
                    file_id = str(event.video.id)
                    prefix = f"{msg_id}_{file_id}"
                    try:
                        local_path, file_type = await restricted_downloader.download_media(
                            client,
                            event.message,
                            prefix=prefix,
                        )
                        logger.info(f"Downloaded video {file_id} → {local_path}")
                    except Exception as dl_err:
                        logger.error(f"Failed to download video {file_id}: {dl_err}")
                        local_path = None
                        file_type = "video"

                    media_items.append(
                        {
                            "file_id": file_id,
                            "file_type": file_type,
                            "local_path": str(local_path) if local_path else None,
                            "stamped_path": None,
                        }
                    )

                await self.on_message(
                    source_channel=event.chat.username or str(event.chat_id),
                    text=event.raw_text or "",
                    media_items=media_items,
                    timestamp=time.time(),
                    raw_metadata=raw_metadata,
                )
            except Exception as e:
                logger.error(f"Scraper handler error (message skipped): {e}", exc_info=True)

        self._handler_ref = handler
        logger.info(f"Scraper started, monitoring {len(channels)} channels: {channels}")

        # Kick-start Telethon's internal update loop so event handlers fire.
        # catch_up() fetches missed updates from the server. It can throw if
        # the session isn't fully ready or the network hiccups — non-fatal.
        try:
            await client.catch_up()
        except Exception as e:
            logger.warning(f"catch_up() failed (non-fatal, events will still arrive): {e}")

    async def stop(self) -> None:
        """Stop the scraper by deregistering the event handler."""
        self._running = False
        if self._client and self._handler_ref:
            self._client.remove_event_handler(self._handler_ref)
            self._handler_ref = None
        logger.info("Scraper stopped")
