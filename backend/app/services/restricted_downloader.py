"""Restricted Content Downloader — bypasses noforwards using raw MTProto file locations.

Strategy: try normal client.download_media() first (faster). If it fails due to
restrictions, construct InputPhotoFileLocation or InputDocumentFileLocation from
the message's media attributes and use client.download_file() which operates at
the file layer and bypasses the noforwards check.
"""

import json
import logging
from pathlib import Path
from typing import Any

from telethon import TelegramClient
from telethon.tl.types import (
    InputDocumentFileLocation,
    InputPhotoFileLocation,
    MessageMediaDocument,
    MessageMediaPhoto,
)

from app.config import settings

logger = logging.getLogger(__name__)


def _ensure_media_dir() -> Path:
    """Ensure the media download directory exists."""
    media_path = Path(settings.media_dir)
    media_path.mkdir(parents=True, exist_ok=True)
    return media_path


async def download_media(
    client: TelegramClient,
    message,
    prefix: str = "",
) -> tuple[str | None, str]:
    """Download media from a message, bypassing restrictions if needed.

    Args:
        client: Connected Telethon client.
        message: Telethon message object with media.
        prefix: Filename prefix (e.g., "12345_67890").

    Returns:
        Tuple of (local_path or None, file_type: "photo"|"video"|"document").
    """
    media_dir = _ensure_media_dir()
    file_type = _detect_file_type(message)

    # Attempt 1: Normal download (fastest path)
    try:
        local_path = await client.download_media(
            message,
            file=str(media_dir / prefix) if prefix else str(media_dir),
        )
        if local_path:
            logger.info(f"Normal download OK: {local_path}")
            _write_sidecar(local_path, message)
            return str(local_path), file_type
    except Exception as e:
        logger.warning(f"Normal download failed (will try raw MTProto): {e}")

    # Attempt 2: Raw MTProto file-layer download (bypasses noforwards)
    try:
        local_path = await _raw_download(client, message, media_dir, prefix)
        if local_path:
            logger.info(f"Raw MTProto download OK: {local_path}")
            _write_sidecar(local_path, message)
            return local_path, file_type
    except Exception as e:
        logger.error(f"Raw MTProto download also failed: {e}")

    return None, file_type


def _detect_file_type(message) -> str:
    """Determine file type from message media."""
    if isinstance(getattr(message, "media", None), MessageMediaPhoto):
        return "photo"
    if isinstance(getattr(message, "media", None), MessageMediaDocument):
        doc = message.media.document
        if doc and doc.mime_type and doc.mime_type.startswith("video/"):
            return "video"
        return "document"
    if getattr(message, "photo", None):
        return "photo"
    if getattr(message, "video", None):
        return "video"
    return "document"


async def _raw_download(
    client: TelegramClient,
    message,
    media_dir: Path,
    prefix: str,
) -> str | None:
    """Download via raw InputPhotoFileLocation / InputDocumentFileLocation.

    This bypasses server-side noforwards checks since it operates at the
    file layer rather than the message layer.
    """
    media = getattr(message, "media", None)
    if not media:
        return None

    if isinstance(media, MessageMediaPhoto) and media.photo:
        photo = media.photo
        # Get the largest photo size
        if not photo.sizes:
            return None
        largest = photo.sizes[-1]
        # Get the actual size data
        size_type = getattr(largest, "type", "x")

        location = InputPhotoFileLocation(
            id=photo.id,
            access_hash=photo.access_hash,
            file_reference=photo.file_reference,
            thumb_size=size_type,
        )
        ext = ".jpg"
        out_path = str(media_dir / f"{prefix}_restricted{ext}")

        with open(out_path, "wb") as f:
            async for chunk in client.iter_download(location):
                f.write(chunk)

        return out_path

    if isinstance(media, MessageMediaDocument) and media.document:
        doc = media.document

        location = InputDocumentFileLocation(
            id=doc.id,
            access_hash=doc.access_hash,
            file_reference=doc.file_reference,
            thumb_size="",  # Full document, not thumbnail
        )

        # Determine extension from mime type
        mime = doc.mime_type or ""
        ext_map = {
            "video/mp4": ".mp4",
            "video/quicktime": ".mov",
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
            "application/pdf": ".pdf",
        }
        ext = ext_map.get(mime, ".bin")
        out_path = str(media_dir / f"{prefix}_restricted{ext}")

        with open(out_path, "wb") as f:
            async for chunk in client.iter_download(location):
                f.write(chunk)

        return out_path

    return None


def _write_sidecar(local_path: str, message) -> None:
    """Write .meta.json sidecar alongside the downloaded media file.

    Contains full raw metadata for forensic analysis.
    """
    sidecar_path = local_path + ".meta.json"
    try:
        meta: dict[str, Any] = {
            "message_id": message.id,
            "chat_id": getattr(message, "chat_id", None),
            "date": message.date.isoformat() if message.date else None,
            "sender_id": getattr(message, "sender_id", None),
        }

        # Add raw message dict
        try:
            raw = message.to_dict()
            # Convert non-serializable types
            meta["raw"] = _make_serializable(raw)
        except Exception:
            pass

        with open(sidecar_path, "w") as f:
            json.dump(meta, f, indent=2, default=str)

    except Exception as e:
        logger.debug(f"Failed to write sidecar {sidecar_path}: {e}")


def _make_serializable(obj: Any) -> Any:
    """Recursively convert non-JSON-serializable types (bytes, etc.)."""
    if isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_serializable(v) for v in obj]
    if isinstance(obj, bytes):
        return f"<bytes:{len(obj)}>"
    if isinstance(obj, (int, float, str, bool, type(None))):
        return obj
    return str(obj)
