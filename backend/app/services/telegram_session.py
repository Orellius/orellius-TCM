"""Telegram session manager — handles authentication, connection, and channel discovery."""

import logging

from telethon import TelegramClient
from telethon.errors import FloodWaitError, SessionPasswordNeededError
from telethon.tl.types import Channel

from app.config import settings

logger = logging.getLogger(__name__)

_client: TelegramClient | None = None
_connected: bool = False
_auth_state: str = "disconnected"  # disconnected, awaiting_code, awaiting_2fa, connected
_user_info: dict | None = None  # Cached user info for get_status()
_phones: dict[str, str] = {}  # Phone numbers keyed by session name to avoid race conditions


async def get_client() -> TelegramClient:
    """Get or create the Telegram client (does NOT start it)."""
    global _client
    if _client is None:
        _client = TelegramClient(
            settings.telegram_session_name,
            settings.telegram_api_id,
            settings.telegram_api_hash,
        )
    return _client


def _mask_phone(phone: str) -> str:
    """Mask phone number for safe display: +972***2233."""
    if not phone or len(phone) < 6:
        return "***"
    return phone[:4] + "***" + phone[-4:]


def _build_user_dict(me) -> dict:
    """Build a safe user info dict from a Telethon User object."""
    return {
        "id": me.id,
        "first_name": me.first_name or "",
        "last_name": me.last_name or "",
        "phone": _mask_phone(me.phone or ""),
        "username": me.username or "",
    }


async def connect(phone: str = "") -> dict:
    """Initiate Telegram connection. Returns auth state.

    Args:
        phone: Phone number in international format (e.g. +1234567890).
               Falls back to TELEGRAM_PHONE env var if empty.
    """
    global _connected, _auth_state, _user_info

    if not settings.telegram_api_id or not settings.telegram_api_hash:
        return {"status": "error", "message": "Telegram API credentials not configured in .env"}

    # Store phone keyed by session name for later use in submit_code / sign_in
    resolved_phone = phone.strip() if phone else settings.telegram_phone
    _phones[settings.telegram_session_name] = resolved_phone

    client = await get_client()
    await client.connect()

    if await client.is_user_authorized():
        _connected = True
        _auth_state = "connected"
        me = await client.get_me()
        _user_info = _build_user_dict(me)

        # Attach Ghost Engine if enabled
        if settings.ghost_mode_enabled:
            try:
                from app.services.ghost_engine import GhostEngine

                ghost = GhostEngine.init(client)
                await ghost.enable()
                logger.info("Ghost Engine attached on connect")
            except Exception as e:
                logger.warning(f"Ghost Engine failed to attach: {e}")

        return {"status": "connected", "user": _user_info}

    # Validate phone before attempting auth
    if not resolved_phone:
        _auth_state = "disconnected"
        return {"status": "error", "message": "Phone number is required"}

    # Need to authenticate — disconnect and reconnect for clean state
    if client.is_connected():
        await client.disconnect()
        await client.connect()

    try:
        await client.send_code_request(resolved_phone)
        _auth_state = "awaiting_code"
        return {"status": "awaiting_code"}
    except FloodWaitError as e:
        _auth_state = "disconnected"
        return {"status": "error", "message": f"Rate limited by Telegram. Try again in {e.seconds} seconds"}
    except Exception as e:
        _auth_state = "disconnected"
        logger.exception("Failed to send Telegram auth code")
        return {"status": "error", "message": str(e)}


async def submit_code(code: str) -> dict:
    """Submit the authentication code received via Telegram."""
    global _connected, _auth_state, _user_info

    if not code or not code.strip():
        return {"status": _auth_state, "message": "Code cannot be empty"}

    client = await get_client()

    stored_phone = _phones.get(settings.telegram_session_name, "")
    if not stored_phone:
        return {"status": "error", "message": "No phone number on file. Call connect() first."}

    try:
        await client.sign_in(stored_phone, code.strip())
        _connected = True
        _auth_state = "connected"
        me = await client.get_me()
        _user_info = _build_user_dict(me)
        return {"status": "connected", "user": _user_info}
    except SessionPasswordNeededError:
        _auth_state = "awaiting_2fa"
        return {"status": "awaiting_2fa"}
    except Exception as e:
        _auth_state = "disconnected"
        logger.exception("Failed to submit Telegram auth code")
        return {"status": "error", "message": str(e)}


async def submit_2fa(password: str) -> dict:
    """Submit 2FA password."""
    global _connected, _auth_state, _user_info

    if not password:
        return {"status": _auth_state, "message": "Password cannot be empty"}

    client = await get_client()

    try:
        await client.sign_in(password=password)
        _connected = True
        _auth_state = "connected"
        me = await client.get_me()
        _user_info = _build_user_dict(me)
        return {"status": "connected", "user": _user_info}
    except Exception as e:
        _auth_state = "disconnected"
        logger.exception("Failed to submit 2FA password")
        return {"status": "error", "message": str(e)}


async def disconnect() -> dict:
    """Disconnect from Telegram."""
    global _client, _connected, _auth_state, _user_info

    # Disable Ghost Engine before disconnecting
    try:
        from app.services.ghost_engine import GhostEngine

        ghost = GhostEngine.get_instance()
        if ghost:
            await ghost.disable()
            GhostEngine.destroy()
            logger.info("Ghost Engine disabled on disconnect")
    except Exception as e:
        logger.warning(f"Ghost Engine disable failed: {e}")

    if _client and _client.is_connected():
        await _client.disconnect()

    _connected = False
    _auth_state = "disconnected"
    _user_info = None
    _phones.pop(settings.telegram_session_name, None)
    return {"status": "disconnected"}


async def list_channels() -> list[dict]:
    """List all channels/groups the user is a member of."""
    client = await get_client()

    if not _connected or not await client.is_user_authorized():
        return []

    dialogs = await client.get_dialogs(limit=settings.telegram_dialog_limit)
    channels = []

    for dialog in dialogs:
        if isinstance(dialog.entity, Channel):
            channels.append(
                {
                    "id": dialog.entity.id,
                    "title": dialog.entity.title,
                    "username": dialog.entity.username or "",
                    "participants": getattr(dialog.entity, "participants_count", 0) or 0,
                    "is_megagroup": dialog.entity.megagroup,
                    "is_creator": getattr(dialog.entity, "creator", False),
                    "is_admin": bool(getattr(dialog.entity, "admin_rights", None)),
                }
            )

    return channels


def resolve_peer(channel: str) -> str | int:
    """Normalize a channel identifier for Telethon.

    Usernames pass through as-is.  Bare numeric IDs (from the channel picker)
    get the ``-100`` prefix that Telethon expects for channels/supergroups.
    """
    stripped = channel.strip().lstrip("@")
    if stripped.isdigit():
        return int(f"-100{stripped}")
    return channel


async def send_test_message(channel: str, text: str) -> dict:
    """Send a test message to a channel to verify publishing works."""
    client = await get_client()

    if not _connected:
        return {"ok": False, "error": "Not connected to Telegram"}

    try:
        result = await client.send_message(resolve_peer(channel), text)
        return {"ok": True, "message_id": result.id}
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def get_status() -> dict:
    """Get current connection status, including user info if connected."""
    global _user_info, _connected, _auth_state

    # If connected but user_info is missing (e.g., backend restarted with saved session),
    # fetch user info from the live session.
    if _connected and _user_info is None:
        try:
            client = await get_client()
            if client.is_connected() and await client.is_user_authorized():
                me = await client.get_me()
                _user_info = _build_user_dict(me)
        except Exception:
            pass

    result: dict = {
        "connected": _connected,
        "auth_state": _auth_state,
    }
    if _user_info and _connected:
        result["user"] = _user_info
    return result
