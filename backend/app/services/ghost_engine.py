"""Ghost Engine — stealth wrapper around the shared Telethon client.

Intercepts outgoing RPC calls to suppress read receipts, typing indicators,
and online status. Also registers passive event handlers for edit/delete tracking
and provides deep metadata extraction from raw messages.
"""

import asyncio
import logging
import time
import types
from typing import Any

from telethon import TelegramClient, events
from telethon.tl.functions.account import UpdateStatusRequest
from telethon.tl.functions.messages import (
    ReadEncryptedHistoryRequest,
    ReadHistoryRequest,
    SetTypingRequest,
)

from app.config import settings

logger = logging.getLogger(__name__)


def _sanitize_for_json(obj: Any) -> Any:
    """Recursively convert bytes and other non-JSON-safe types in Telethon dicts."""
    if isinstance(obj, bytes):
        return f"<{len(obj)} bytes>"
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(v) for v in obj]
    return obj


# Singleton instance
_instance: "GhostEngine | None" = None


class GhostEngine:
    """Stealth wrapper for the shared Telethon client.

    Monkey-patches client.__call__ to intercept and suppress outgoing requests
    that would reveal monitoring activity (read receipts, typing, online status).
    """

    def __init__(self, client: TelegramClient):
        self._client = client
        self._enabled = False
        self._original_call = None
        self._offline_task: asyncio.Task | None = None
        self._edit_handler = None
        self._delete_handler = None

        # Track edits and deletions across monitored channels
        self.edit_history: dict[int, list[dict]] = {}  # msg_id → list of edits
        self.deleted_messages: dict[int, float] = {}  # msg_id → deletion timestamp

    @classmethod
    def get_instance(cls) -> "GhostEngine | None":
        return _instance

    @classmethod
    def init(cls, client: TelegramClient) -> "GhostEngine":
        global _instance
        if _instance is None:
            _instance = cls(client)
        return _instance

    @classmethod
    def destroy(cls):
        global _instance
        _instance = None

    async def enable(self) -> None:
        """Activate ghost mode: patch RPC calls, set offline, start monitors."""
        if self._enabled:
            return

        self._enabled = True

        # Instance-level monkey-patch (does not affect other TelegramClient instances)
        self._original_call = self._client.__class__.__call__

        engine = self  # closure reference

        async def _ghost_call(client_self, request, *args, **kwargs):
            if engine._enabled:
                # Suppress read receipts
                if settings.suppress_read_receipts and isinstance(
                    request, (ReadHistoryRequest, ReadEncryptedHistoryRequest)
                ):
                    logger.debug(f"Ghost: suppressed {type(request).__name__}")
                    return None

                # Suppress typing indicators
                if isinstance(request, SetTypingRequest):
                    logger.debug("Ghost: suppressed SetTypingRequest")
                    return None

            return await engine._original_call(client_self, request, *args, **kwargs)

        self._client.__call__ = types.MethodType(_ghost_call, self._client)

        # Force offline status immediately
        if settings.suppress_online_status:
            await self._set_offline()
            # Periodically re-assert offline status (Telegram resets it)
            self._offline_task = asyncio.create_task(self._offline_loop())

        # Register passive event handlers for edit/delete tracking
        self._register_monitors()

        logger.info("Ghost Engine ENABLED — read receipts suppressed, offline enforced")

    async def disable(self) -> None:
        """Deactivate ghost mode: restore original RPC call, stop monitors."""
        if not self._enabled:
            return

        self._enabled = False

        # Remove instance-level override, restoring the class method
        if self._original_call:
            try:
                del self._client.__call__
            except AttributeError:
                pass
            self._original_call = None

        # Cancel offline loop
        if self._offline_task and not self._offline_task.done():
            self._offline_task.cancel()
            self._offline_task = None

        # Remove event handlers
        self._unregister_monitors()

        logger.info("Ghost Engine DISABLED")

    async def _set_offline(self) -> None:
        """Send UpdateStatusRequest(offline=True) to force offline appearance."""
        try:
            # Use the original call to bypass our own filter
            if self._original_call:
                await self._original_call(self._client, UpdateStatusRequest(offline=True))
            else:
                await self._client(UpdateStatusRequest(offline=True))
            logger.debug("Ghost: offline status asserted")
        except Exception as e:
            logger.warning(f"Ghost: failed to set offline status: {e}")

    async def _offline_loop(self) -> None:
        """Re-assert offline status every 5 minutes."""
        while self._enabled:
            try:
                await asyncio.sleep(settings.ghost_offline_interval)
                if self._enabled:
                    await self._set_offline()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Ghost: offline loop error: {e}")

    def _register_monitors(self) -> None:
        """Register event handlers for message edits and deletions."""

        @self._client.on(events.MessageEdited)
        async def on_edit(event):
            msg_id = event.message.id
            edit_entry = {
                "timestamp": time.time(),
                "text": event.message.raw_text,
                "edit_date": (event.message.edit_date.timestamp() if event.message.edit_date else None),
            }
            if msg_id not in self.edit_history:
                self.edit_history[msg_id] = []
            self.edit_history[msg_id].append(edit_entry)
            # Evict oldest entries when dict grows too large
            if len(self.edit_history) > 1200:
                keys = list(self.edit_history.keys())
                for k in keys[: len(keys) - 1000]:
                    del self.edit_history[k]
            logger.debug(f"Ghost: tracked edit for message {msg_id}")

        @self._client.on(events.MessageDeleted)
        async def on_delete(event):
            for msg_id in event.deleted_ids:
                self.deleted_messages[msg_id] = time.time()
                logger.debug(f"Ghost: tracked deletion of message {msg_id}")
            # Evict oldest entries when dict grows too large
            if len(self.deleted_messages) > 1200:
                sorted_keys = sorted(self.deleted_messages, key=self.deleted_messages.get)
                for k in sorted_keys[: len(sorted_keys) - 1000]:
                    del self.deleted_messages[k]

        self._edit_handler = on_edit
        self._delete_handler = on_delete

    def _unregister_monitors(self) -> None:
        """Remove edit/delete event handlers."""
        if self._edit_handler:
            self._client.remove_event_handler(self._edit_handler)
            self._edit_handler = None
        if self._delete_handler:
            self._client.remove_event_handler(self._delete_handler)
            self._delete_handler = None

    @staticmethod
    def extract_deep_metadata(message) -> dict[str, Any]:
        """Extract comprehensive metadata from a Telethon message object.

        Returns raw peer IDs, forward chains, edit history, reactions,
        views, post author, grouped media ID, and TTL period.
        """
        meta: dict[str, Any] = {
            "raw_peer_id": message.peer_id.channel_id
            if hasattr(message.peer_id, "channel_id")
            else getattr(message.peer_id, "user_id", None),
            "raw_message_id": message.id,
            "raw_json": {},
            "forward_from": None,
            "reply_to_msg_id": None,
            "edit_date": None,
            "edit_dates": [],
            "views": getattr(message, "views", None),
            "reactions": None,
            "post_author": getattr(message, "post_author", None),
            "grouped_id": getattr(message, "grouped_id", None),
            "ttl_period": getattr(message, "ttl_period", None),
        }

        # Raw JSON via message.to_dict() — sanitize bytes for JSON safety
        try:
            meta["raw_json"] = _sanitize_for_json(message.to_dict())
        except Exception:
            pass

        # Forward chain
        if message.forward:
            fwd = message.forward
            meta["forward_from"] = {
                "from_id": getattr(fwd, "from_id", None),
                "from_name": getattr(fwd, "from_name", None),
                "channel_post": getattr(fwd, "channel_post", None),
                "date": fwd.date.timestamp() if fwd.date else None,
            }
            # Resolve from_id to something usable
            if hasattr(fwd, "from_id") and fwd.from_id:
                if hasattr(fwd.from_id, "channel_id"):
                    meta["forward_from"]["channel_id"] = fwd.from_id.channel_id
                elif hasattr(fwd.from_id, "user_id"):
                    meta["forward_from"]["user_id"] = fwd.from_id.user_id

        # Reply chain
        if message.reply_to:
            meta["reply_to_msg_id"] = getattr(message.reply_to, "reply_to_msg_id", None)

        # Edit date
        if message.edit_date:
            meta["edit_date"] = message.edit_date.timestamp()

        # Edit history from ghost engine tracker
        instance = GhostEngine.get_instance()
        if instance and message.id in instance.edit_history:
            meta["edit_dates"] = instance.edit_history[message.id]

        # Reactions
        if hasattr(message, "reactions") and message.reactions:
            try:
                reactions_list = []
                for result in message.reactions.results:
                    reaction_data = {
                        "count": result.count,
                    }
                    if hasattr(result.reaction, "emoticon"):
                        reaction_data["emoticon"] = result.reaction.emoticon
                    elif hasattr(result.reaction, "document_id"):
                        reaction_data["custom_emoji_id"] = result.reaction.document_id
                    reactions_list.append(reaction_data)
                meta["reactions"] = reactions_list
            except Exception:
                pass

        return meta

    def get_status(self) -> dict:
        """Return current ghost engine status."""
        return {
            "enabled": self._enabled,
            "suppress_read_receipts": settings.suppress_read_receipts,
            "suppress_online_status": settings.suppress_online_status,
            "tracked_edits": len(self.edit_history),
            "tracked_deletions": len(self.deleted_messages),
        }
