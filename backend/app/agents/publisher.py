"""Publisher Agent — manages the publishing queue and pushes to target channel."""

import asyncio
import logging

from app.config import settings
from app.orchestrator.state import PipelineState

logger = logging.getLogger(__name__)


async def publish_node(state: PipelineState) -> PipelineState:
    """LangGraph node: publish the approved, stamped message to the target channel."""
    message_id = state["message_id"]

    if not state["approved"]:
        logger.info(f"[{message_id}] Not approved, skipping publish")
        state["published"] = False
        return state

    if not settings.target_channel:
        logger.error(f"[{message_id}] No target channel configured")
        state["publish_error"] = "No target channel configured"
        state["published"] = False
        return state

    logger.info(f"[{message_id}] Publishing to {settings.target_channel}")

    try:
        # Rate limiting: wait before publishing
        await asyncio.sleep(settings.publish_delay_seconds)

        # Reuse the shared Telegram client (already connected)
        from app.services.telegram_session import get_client, resolve_peer

        client = await get_client()
        target = resolve_peer(settings.target_channel)

        # Prefer formatted report over raw translation
        text = state.get("formatted_output") or state["translated_text"]

        # Append channel signature if configured
        if settings.channel_signature:
            text += "\n\n" + settings.channel_signature

        # Detect HTML formatting for parse_mode
        from app.services.telegram_html import safe_parse_mode

        parse_mode = safe_parse_mode(text)

        # Send media if available
        stamped_media = [item["stamped_path"] for item in state["media_items"] if item.get("stamped_path")]

        # Telegram caption limit: 1024 chars for media, 4096 for text messages
        CAPTION_LIMIT = 1024

        if stamped_media:
            if len(text) <= CAPTION_LIMIT:
                await client.send_file(
                    target,
                    stamped_media,
                    caption=text,
                    parse_mode=parse_mode,
                )
            else:
                # Text too long for caption — send media first, then text separately
                await client.send_file(
                    target,
                    stamped_media,
                )
                await client.send_message(
                    target,
                    text,
                    parse_mode=parse_mode,
                )
        else:
            await client.send_message(
                target,
                text,
                parse_mode=parse_mode,
            )

        state["published"] = True
        logger.info(f"[{message_id}] Published successfully")

    except Exception as e:
        logger.error(f"[{message_id}] Publish failed: {e}")
        state["publish_error"] = str(e)
        state["published"] = False

    return state
