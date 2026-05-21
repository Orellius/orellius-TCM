"""Media Handler Agent — downloads, stamps, and processes media files."""

import asyncio
import logging
from pathlib import Path

from PIL import Image

from app.config import settings
from app.orchestrator.state import MediaItem, PipelineState
from app.services.watermark_manager import process_image as wm_process_image
from app.services.watermark_manager import process_video as wm_process_video

logger = logging.getLogger(__name__)

# Position mapping for image stamping (returns (x, y) given base and stamp dimensions)
_POSITION_MAP = {
    "center": lambda bw, bh, sw, sh: ((bw - sw) // 2, (bh - sh) // 2),
    "bottom-right": lambda bw, bh, sw, sh: (bw - sw - int(bw * 0.03), bh - sh - int(bh * 0.03)),
    "bottom-left": lambda bw, bh, sw, sh: (int(bw * 0.03), bh - sh - int(bh * 0.03)),
    "top-right": lambda bw, bh, sw, sh: (bw - sw - int(bw * 0.03), int(bh * 0.03)),
    "top-left": lambda bw, bh, sw, sh: (int(bw * 0.03), int(bh * 0.03)),
}

# FFmpeg overlay position expressions
_FFMPEG_OVERLAY_MAP = {
    "center": "(W-w)/2:(H-h)/2",
    "bottom-right": "W-w-W*0.03:H-h-H*0.03",
    "bottom-left": "W*0.03:H-h-H*0.03",
    "top-right": "W-w-W*0.03:H*0.03",
    "top-left": "W*0.03:H*0.03",
}


def _get_media_dir() -> Path:
    """Return the media directory from settings, ensuring it exists."""
    d = Path(settings.media_dir)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _resolve_stamp_path() -> Path | None:
    """Resolve the stamp image path; return None if stamping is disabled or file missing."""
    if not settings.stamp_enabled:
        logger.debug("Stamping disabled in settings")
        return None

    raw = settings.stamp_image_path
    if not raw:
        logger.warning("stamp_image_path is empty")
        return None

    p = Path(raw)
    # If relative, resolve against backend working directory
    if not p.is_absolute():
        p = Path.cwd() / p

    if not p.exists():
        logger.error(f"Stamp image NOT FOUND at {p} (configured: {raw})")
        return None

    logger.info(f"Stamp image resolved: {p}")
    return p


async def process_media_node(state: PipelineState) -> PipelineState:
    """LangGraph node: download and stamp all media items."""
    message_id = state["message_id"]
    media_items = state["media_items"]

    if not media_items:
        state["media_processed"] = True
        return state

    stamp_path = _resolve_stamp_path()
    media_dir = _get_media_dir()

    logger.info(f"[{message_id}] Processing {len(media_items)} media items (stamp={'YES' if stamp_path else 'NO'})")

    for item in media_items:
        try:
            local = item.get("local_path")
            if not local:
                logger.warning(f"[{message_id}] No local_path for {item['file_id']}, skipping")
                continue

            if not Path(local).exists():
                logger.error(f"[{message_id}] local_path does not exist: {local}")
                continue

            # Watermark removal (before stamping) — photos and videos
            if settings.watermark_removal_enabled and item["file_type"] in ("photo", "video"):
                try:
                    if item["file_type"] == "photo":
                        wm_result = await wm_process_image(
                            item,
                            message_id,
                            media_dir,
                            state.get("source_channel", ""),
                        )
                    else:
                        wm_result = await wm_process_video(
                            item,
                            message_id,
                            media_dir,
                            state.get("source_channel", ""),
                        )
                    item["watermark_detected"] = wm_result.confidence >= settings.watermark_confidence_threshold
                    item["watermark_confidence"] = wm_result.confidence
                    if wm_result.success:
                        item["watermark_original_path"] = item["local_path"]
                        item["local_path"] = wm_result.cleaned_path
                        logger.info(
                            f"[{message_id}] Watermark removed from {item['file_type']}, feeding cleaned file to stamper"
                        )
                except Exception as wm_err:
                    logger.warning(f"[{message_id}] Watermark removal failed: {wm_err}")

            if stamp_path:
                if item["file_type"] == "photo":
                    await _stamp_image(item, message_id, media_dir, stamp_path)
                elif item["file_type"] == "video":
                    await _stamp_video(item, message_id, media_dir, stamp_path)
            else:
                # No stamping — use the raw file as-is
                item["stamped_path"] = item["local_path"]
        except Exception as e:
            logger.error(f"[{message_id}] Media processing failed for {item['file_id']}: {e}", exc_info=True)
            # Fallback: use raw file so publishing still works
            item["stamped_path"] = item.get("local_path")

    state["media_processed"] = True
    logger.info(f"[{message_id}] Media processing complete")
    return state


async def _stamp_image(item: MediaItem, message_id: str, media_dir: Path, stamp_path: Path) -> None:
    """Burn a branded watermark onto an image using Pillow."""
    input_path = Path(item["local_path"])
    output_path = media_dir / f"{message_id}_{item['file_id']}_stamped.png"

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _apply_image_stamp, input_path, output_path, stamp_path)

    item["stamped_path"] = str(output_path)
    logger.info(f"[{message_id}] Image stamped: {output_path}")


def _apply_image_stamp(input_path: Path, output_path: Path, stamp_path: Path) -> None:
    """Synchronous image stamping with Pillow — config-driven size, opacity, position."""
    base = Image.open(input_path).convert("RGBA")
    stamp = Image.open(stamp_path).convert("RGBA")

    size_pct = settings.stamp_size_pct / 100.0
    opacity = settings.stamp_opacity / 100.0
    position = settings.stamp_position

    # Resize stamp to configured percentage of the base image width
    stamp_width = int(base.width * size_pct)
    stamp_ratio = stamp_width / stamp.width
    stamp_height = int(stamp.height * stamp_ratio)
    stamp = stamp.resize((stamp_width, stamp_height), Image.LANCZOS)

    # Apply configured opacity to the stamp's alpha channel
    r, g, b, a = stamp.split()
    a = a.point(lambda x: int(x * opacity))
    stamp = Image.merge("RGBA", (r, g, b, a))

    # Position the stamp
    pos_fn = _POSITION_MAP.get(position, _POSITION_MAP["center"])
    x, y = pos_fn(base.width, base.height, stamp_width, stamp_height)

    # Composite
    base.paste(stamp, (x, y), stamp)
    base.save(output_path, "PNG")


async def _stamp_video(item: MediaItem, message_id: str, media_dir: Path, stamp_path: Path) -> None:
    """Burn a branded watermark onto a video using FFmpeg with M4 hardware acceleration."""
    input_path = item["local_path"]
    output_path = str(media_dir / f"{message_id}_{item['file_id']}_stamped.mp4")

    # FFmpeg command with Apple VideoToolbox hardware acceleration
    size_pct = settings.stamp_size_pct / 100.0
    opacity = settings.stamp_opacity / 100.0
    overlay_pos = _FFMPEG_OVERLAY_MAP.get(settings.stamp_position, "(W-w)/2:(H-h)/2")

    filter_complex = (
        f"[1:v]scale=iw*{size_pct}:-1,format=rgba,"
        f"colorchannelmixer=aa={opacity}[stamp];"
        f"[0:v][stamp]overlay={overlay_pos}"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-hwaccel",
        "videotoolbox",
        "-i",
        input_path,
        "-i",
        str(stamp_path),
        "-filter_complex",
        filter_complex,
        "-c:v",
        "hevc_videotoolbox",
        "-q:v",
        "65",
        "-c:a",
        "copy",
        output_path,
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()

    if process.returncode != 0:
        raise RuntimeError(f"FFmpeg failed: {stderr.decode()}")

    item["stamped_path"] = output_path
    logger.info(f"[{message_id}] Video stamped: {output_path}")
