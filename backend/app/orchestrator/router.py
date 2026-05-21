"""Routes incoming Telegram messages through the pipeline."""

import asyncio
import logging
import os
import traceback
import uuid

from app.config import settings
from app.orchestrator.graph import create_pipeline_graph
from app.orchestrator.state import PipelineState
from app.services.preprocess import preprocess_message
from app.services.signature_stripper import strip_signature
from app.services.spam_filter import check_message as spam_check
from app.ws_server import ConnectionManager

logger = logging.getLogger(__name__)


class PipelineRouter:
    """Manages pipeline execution for incoming messages."""

    def __init__(self, ws_manager: ConnectionManager, daemon=None):
        self.ws_manager = ws_manager
        self.daemon = daemon
        self.graph = create_pipeline_graph()
        self._tasks: dict[str, asyncio.Task] = {}
        self._semaphore = asyncio.Semaphore(settings.pipeline_max_concurrent)

    async def process_message(
        self,
        source_channel: str,
        text: str,
        media_items: list[dict],
        timestamp: float,
        raw_metadata: dict | None = None,
    ) -> None:
        """Process a new incoming message through the pipeline."""
        # Early-discard truly empty messages (no text AND no media)
        if not text.strip() and not media_items:
            logger.info(f"Discarding empty message from {source_channel} (no text, no media)")
            return

        # Strip channel signature/footer before any processing
        clean_text, signature = strip_signature(text)
        if signature:
            logger.info(f'Stripped signature from {source_channel} ({len(signature)} chars): "{signature[:60]}..."')

        # Fast heuristic spam/ad filter — runs on CLEAN text (signature already removed)
        spam_result = spam_check(clean_text, len(media_items))
        if spam_result.is_spam:
            logger.info(
                f'Filtered {spam_result.category} from {source_channel}: {spam_result.reason} — "{clean_text[:80]}..."'
            )
            return

        # After signature stripping, re-check if message is now empty
        if not clean_text.strip() and not media_items:
            logger.info(f"Discarding message from {source_channel} (only contained a signature)")
            return

        message_id = str(uuid.uuid4())

        # Run pre-processing pipeline (language detect, dedup, keyword filter)
        preprocess_meta = preprocess_message(clean_text, message_id)

        initial_state: PipelineState = {
            "message_id": message_id,
            "source_channel": source_channel,
            "timestamp": timestamp,
            "original_text": clean_text,
            "media_items": media_items,
            "translated_text": "",
            "content_type": "other",
            "translation_approved": False,
            "extracted_facts": [],
            "auto_tags": None,
            "title": "",
            "suggested_template_id": "",
            "formatted_output": "",
            "suggested_intel_status": "",
            "content_filtered": False,
            "review_notes": "",
            "approved": False,
            "human_edited": False,
            "media_processed": False,
            "published": False,
            "publish_error": "",
            "geo_context": None,
            "source_trust": None,
            "related_messages": [],
            "situation_brief": "",
            "raw_metadata": raw_metadata,
            "preprocess_meta": preprocess_meta,
            "fact_check": None,
        }

        logger.info(f"[{message_id}] New message from {source_channel} ({len(clean_text)} chars)")

        # Notify frontend of new message
        await self.ws_manager.broadcast(
            {
                "type": "new_message",
                "message": {
                    "id": message_id,
                    "sourceChannel": source_channel,
                    "originalText": clean_text,
                    "translatedText": None,
                    "mediaUrls": [os.path.basename(m["local_path"]) for m in media_items if m.get("local_path")],
                    "status": "ingested",
                    "timestamp": timestamp,
                    "contentType": None,
                    "extractedFacts": None,
                    "autoTags": None,
                    "title": None,
                    "suggestedTemplateId": None,
                    "formattedOutput": None,
                },
            }
        )

        # Run pipeline asynchronously
        task = asyncio.create_task(self._run_pipeline(initial_state))
        self._tasks[message_id] = task

    async def _run_pipeline(self, state: PipelineState) -> None:
        """Execute the LangGraph pipeline for a single message (concurrency-limited)."""
        message_id = state["message_id"]
        try:
            async with self._semaphore:
                result = await asyncio.wait_for(
                    self.graph.ainvoke(state),
                    timeout=settings.pipeline_timeout_seconds,
                )
                logger.info(f"[{message_id}] Pipeline completed: published={result.get('published')}")
        except TimeoutError:
            logger.error(f"[{message_id}] Pipeline timed out after {settings.pipeline_timeout_seconds}s")

            await self.ws_manager.broadcast(
                {
                    "type": "message_update",
                    "message_id": message_id,
                    "updates": {"status": "failed"},
                }
            )

            if self.daemon:
                try:
                    await self.daemon.report_error(
                        "Pipeline",
                        TimeoutError(f"Pipeline {message_id} timed out after {settings.pipeline_timeout_seconds}s"),
                    )
                except Exception:
                    pass
        except Exception as e:
            tb = traceback.format_exc()
            logger.error(f"[{message_id}] Pipeline failed: {e}\n{tb}")

            await self.ws_manager.broadcast(
                {
                    "type": "message_update",
                    "message_id": message_id,
                    "updates": {"status": "failed"},
                }
            )

            # Report to daemon for analysis
            if self.daemon:
                try:
                    await self.daemon.report_error("Pipeline", e)
                except Exception:
                    pass
        finally:
            self._tasks.pop(message_id, None)
