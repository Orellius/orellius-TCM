"""Media processing utilities — shared FFmpeg and Pillow helpers."""

import asyncio
import logging

logger = logging.getLogger(__name__)


async def get_video_info(file_path: str) -> dict:
    """Get video metadata using ffprobe."""
    cmd = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        file_path,
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await process.communicate()

    import json

    return json.loads(stdout)


async def compress_video(input_path: str, output_path: str, max_size_mb: int = 50) -> str:
    """Compress video using FFmpeg with M4 hardware acceleration."""
    cmd = [
        "ffmpeg",
        "-y",
        "-hwaccel",
        "videotoolbox",
        "-i",
        input_path,
        "-c:v",
        "hevc_videotoolbox",
        "-q:v",
        "60",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        output_path,
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()

    if process.returncode != 0:
        raise RuntimeError(f"Compression failed: {stderr.decode()}")

    return output_path
