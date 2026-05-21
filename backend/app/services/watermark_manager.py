"""Watermark Manager — async orchestrator for detection + removal pipeline."""

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

import cv2

from app.orchestrator.state import MediaItem
from app.services.watermark_detector import get_detector
from app.services.watermark_remover import remove_watermark, save_cleaned_image

logger = logging.getLogger(__name__)


@dataclass
class WatermarkProcessResult:
    success: bool
    cleaned_path: str = ""
    original_path: str = ""
    confidence: float = 0.0
    reason: str = ""


def _process_sync(
    local_path: str,
    message_id: str,
    file_id: str,
    media_dir: Path,
    source_channel: str,
) -> WatermarkProcessResult:
    """Synchronous processing — runs in executor to avoid blocking the event loop."""
    image = cv2.imread(local_path)
    if image is None:
        return WatermarkProcessResult(
            success=False,
            original_path=local_path,
            reason=f"Failed to read image: {local_path}",
        )

    detector = get_detector()
    match = detector.detect(image, source_channel=source_channel)

    if not match.found:
        return WatermarkProcessResult(
            success=False,
            original_path=local_path,
            confidence=match.confidence,
            reason="No watermark detected",
        )

    logger.info(
        f"[{message_id}] Watermark detected: {match.template_name} confidence={match.confidence:.2f} bbox={match.bbox}"
    )

    # Attempt removal
    removal = remove_watermark(image, match.mask)

    if not removal.success:
        logger.info(f"[{message_id}] Watermark removal skipped: {removal.reason}")
        return WatermarkProcessResult(
            success=False,
            original_path=local_path,
            confidence=match.confidence,
            reason=removal.reason,
        )

    # Save cleaned image
    cleaned_path = save_cleaned_image(
        removal.cleaned_image,
        message_id,
        file_id,
        media_dir,
    )

    logger.info(f"[{message_id}] Watermark removed: quality={removal.quality_score:.2f} saved={cleaned_path}")

    return WatermarkProcessResult(
        success=True,
        cleaned_path=cleaned_path,
        original_path=local_path,
        confidence=match.confidence,
    )


async def process_image(
    item: MediaItem,
    message_id: str,
    media_dir: Path,
    source_channel: str,
) -> WatermarkProcessResult:
    """Async entry point: detect and remove watermarks from a single image.

    Runs the synchronous OpenCV work in an executor to stay non-blocking.
    """
    local_path = item.get("local_path", "")
    file_id = item.get("file_id", "unknown")

    if not local_path:
        return WatermarkProcessResult(success=False, reason="No local_path")

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        _process_sync,
        local_path,
        message_id,
        file_id,
        media_dir,
        source_channel,
    )
    return result


def _detect_video_watermark_sync(
    local_path: str,
    source_channel: str,
) -> tuple[bool, float, tuple[int, int, int, int], str]:
    """Sample 3 frames (first, middle, last) and return the highest-confidence detection.

    Returns (found, confidence, bbox, template_name).
    """
    cap = cv2.VideoCapture(local_path)
    if not cap.isOpened():
        return (False, 0.0, (0, 0, 0, 0), "")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    sample_positions = [0]
    if total_frames > 2:
        sample_positions.append(total_frames // 2)
        sample_positions.append(total_frames - 1)

    detector = get_detector()
    best = (False, 0.0, (0, 0, 0, 0), "")

    for pos in sample_positions:
        cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
        ret, frame = cap.read()
        if not ret or frame is None:
            continue

        match = detector.detect(frame, source_channel=source_channel)
        if match.confidence > best[1]:
            best = (match.found, match.confidence, match.bbox, match.template_name)

    cap.release()
    return best


async def process_video(
    item: MediaItem,
    message_id: str,
    media_dir: Path,
    source_channel: str,
) -> WatermarkProcessResult:
    """Async entry point: detect watermark on video first frame, remove via FFmpeg delogo.

    Uses FFmpeg's delogo filter which interpolates the specified region from
    surrounding pixels — purpose-built for removing static logos from video.
    """
    local_path = item.get("local_path", "")
    file_id = item.get("file_id", "unknown")

    if not local_path:
        return WatermarkProcessResult(success=False, reason="No local_path")

    loop = asyncio.get_event_loop()
    found, confidence, bbox, template_name = await loop.run_in_executor(
        None,
        _detect_video_watermark_sync,
        local_path,
        source_channel,
    )

    if not found:
        return WatermarkProcessResult(
            success=False,
            original_path=local_path,
            confidence=confidence,
            reason="No watermark detected in video",
        )

    x, y, w, h = bbox
    logger.info(
        f"[{message_id}] Video watermark detected: {template_name} confidence={confidence:.2f} bbox=({x},{y},{w},{h})"
    )

    # Use FFmpeg delogo to remove the watermark region
    output_path = str(media_dir / f"{message_id}_{file_id}_delogo.mp4")

    cmd = [
        "ffmpeg",
        "-y",
        "-hwaccel",
        "videotoolbox",
        "-i",
        local_path,
        "-vf",
        f"delogo=x={x}:y={y}:w={w}:h={h}:show=0",
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
        err_msg = stderr.decode()[-300:]
        logger.warning(f"[{message_id}] FFmpeg delogo failed: {err_msg}")
        return WatermarkProcessResult(
            success=False,
            original_path=local_path,
            confidence=confidence,
            reason="FFmpeg delogo failed",
        )

    logger.info(f"[{message_id}] Video watermark removed via delogo: {output_path}")
    return WatermarkProcessResult(
        success=True,
        cleaned_path=output_path,
        original_path=local_path,
        confidence=confidence,
    )


# Module-level convenience
_manager_initialized = False


def ensure_initialized() -> None:
    """Ensure the detector has loaded templates. Safe to call multiple times."""
    global _manager_initialized
    if not _manager_initialized:
        get_detector()  # triggers template loading
        _manager_initialized = True


def reload_templates() -> None:
    """Reload reference templates (after operator adds new references)."""
    global _manager_initialized
    get_detector().reload()
    _manager_initialized = True
