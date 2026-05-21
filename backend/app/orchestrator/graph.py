"""LangGraph pipeline: defines the agent workflow as a state machine."""

import asyncio
import logging
import os
import time
from collections.abc import Awaitable, Callable
from functools import wraps

from langgraph.graph import END, StateGraph

from app.agents.analyst import translate_node
from app.agents.fact_checker import fact_check_node
from app.agents.geo_enricher import geo_enrich_node
from app.agents.ingestion import ingest_node
from app.agents.media_handler import process_media_node
from app.agents.publisher import publish_node
from app.agents.reviewer import review_node
from app.orchestrator.state import PipelineState

logger = logging.getLogger(__name__)

# Module-level ws_manager reference, set during app startup via set_ws_manager()
_ws_manager = None

# Pending review states: stored when pipeline reaches notify_review,
# retrieved when human approves/rejects so we can resume publishing.
_pending_reviews: dict[str, dict] = {}

# Pre-stamped media: background tasks that stamp media while human reviews.
# When approval comes, we check here first to skip redundant media processing.
_pre_stamp_tasks: dict[str, asyncio.Task] = {}


def get_pending_state(message_id: str) -> dict | None:
    """Retrieve stored pipeline state for a pending review."""
    return _pending_reviews.get(message_id)


def remove_pending_state(message_id: str) -> None:
    """Remove stored pipeline state after approval/rejection."""
    _pending_reviews.pop(message_id, None)
    # Cancel pre-stamp task if still running
    task = _pre_stamp_tasks.pop(message_id, None)
    if task and not task.done():
        task.cancel()


async def await_pre_stamp(message_id: str) -> dict | None:
    """Wait for pre-stamped media result if available. Returns updated state or None."""
    task = _pre_stamp_tasks.pop(message_id, None)
    if task is None:
        return None
    try:
        return await asyncio.wait_for(task, timeout=30)
    except (TimeoutError, asyncio.CancelledError, Exception) as e:
        logger.warning(f"[{message_id}] Pre-stamp await failed: {e}")
        return None


# Map graph node names → frontend agent display names (must match pipelineStore agent.name)
NODE_AGENT_NAMES: dict[str, str] = {
    "ingest": "Ingestion",
    "translate": "Analyst",
    "content_gate": "Analyst",
    "quality_gate": "Analyst",
    "geo_enrich": "Analyst",
    "fact_check": "Fact Checker",
    "review": "Reviewer",
    "process_media": "Media Handler",
    "publish": "Publisher",
}

# Map graph node names → message status strings for the frontend
NODE_MESSAGE_STATUS: dict[str, str] = {
    "translate": "translating",
    "content_gate": "filtering",
    "geo_enrich": "enriching",
    "fact_check": "fact_checking",
    "review": "reviewing",
    "process_media": "processing_media",
    "publish": "publishing",
}


def set_ws_manager(manager) -> None:
    """Called at app startup to inject the WebSocket manager."""
    global _ws_manager
    _ws_manager = manager


def _with_status(node_name: str, node_fn: Callable[[PipelineState], Awaitable[PipelineState]]):
    """Wrap a LangGraph node to broadcast agent_status + message_status events.

    Broadcasts:
      - agent_status: "running" when node starts, "idle" when done, "error" on failure
      - message_update: updates message status on the frontend so the feed shows progress
    """
    agent_name = NODE_AGENT_NAMES.get(node_name)
    if not agent_name:
        return node_fn

    message_status = NODE_MESSAGE_STATUS.get(node_name)

    @wraps(node_fn)
    async def wrapper(state: PipelineState) -> PipelineState:
        message_id = state.get("message_id", "?")

        if _ws_manager:
            await _ws_manager.broadcast(
                {
                    "type": "agent_status",
                    "agent": agent_name,
                    "status": "running",
                    "activity": f"Processing {message_id[:8]}...",
                }
            )

            # Broadcast message progress so the feed shows real-time status
            if message_status:
                await _ws_manager.broadcast(
                    {
                        "type": "message_update",
                        "message_id": message_id,
                        "updates": {"status": message_status},
                    }
                )

        t0 = time.monotonic()
        try:
            result = await node_fn(state)
            elapsed = time.monotonic() - t0

            if _ws_manager:
                await _ws_manager.broadcast(
                    {
                        "type": "agent_status",
                        "agent": agent_name,
                        "status": "idle",
                        "activity": f"Done ({elapsed:.1f}s)",
                        "messagesProcessed": 1,
                    }
                )
            return result

        except Exception as e:
            if _ws_manager:
                await _ws_manager.broadcast(
                    {
                        "type": "agent_status",
                        "agent": agent_name,
                        "status": "error",
                        "activity": str(e)[:120],
                    }
                )
            raise

    return wrapper


# ── Content Gate Node ─────────────────────────────────────────────


async def content_gate_node(state: PipelineState) -> PipelineState:
    """Check if the message is an advertisement or spam based on LLM classification.

    Sets state["content_filtered"] = True for ads/spam so the router can skip review.
    """
    message_id = state["message_id"]
    content_type = state.get("content_type", "other")

    if content_type in ("advertisement", "spam"):
        logger.info(f"[{message_id}] Content gate: filtered as '{content_type}'")
        state["content_filtered"] = True
        return state

    state["content_filtered"] = False
    return state


def should_route_after_content_gate(state: PipelineState) -> str:
    """Route ads/spam to auto-archive, everything else to quality gate."""
    if state.get("content_filtered"):
        return "auto_archive"
    return "quality_gate"


async def auto_archive_node(state: PipelineState) -> PipelineState:
    """Auto-archive filtered content and notify frontend."""
    message_id = state["message_id"]
    content_type = state.get("content_type", "spam")

    if _ws_manager:
        await _ws_manager.broadcast(
            {
                "type": "message_update",
                "message_id": message_id,
                "updates": {
                    "status": "archived",
                    "reviewNotes": f"Auto-filtered: {content_type}",
                    "contentType": content_type,
                },
            }
        )

    logger.info(f"[{message_id}] Auto-archived ({content_type})")
    return state


# ── Quality Gate Node ──────────────────────────────────────────────


async def quality_gate_node(state: PipelineState) -> PipelineState:
    """Validate translation quality with fast heuristics.

    On failure: retry translation once with a stricter prompt, then proceed
    regardless (never blocks the pipeline — just adds warnings).
    """
    from app.agents.analyst import TRANSLATE_PROMPT, _call_ollama, _get_glossary_context
    from app.services.ollama_manager import ollama_manager
    from app.services.quality_gate import validate_translation

    message_id = state["message_id"]
    original = state["original_text"]
    translated = state.get("translated_text", "")

    # Skip gate for error messages or empty text
    if translated.startswith("[TRANSLATION ERROR:") or not original.strip():
        return state

    result = validate_translation(original, translated)

    if result.passed:
        logger.info(f"[{message_id}] Quality gate PASSED")
        return state

    logger.warning(f"[{message_id}] Quality gate FAILED: {result.summary}")

    # ── Retry once with stricter prompt ───────────────────────
    try:
        model = await ollama_manager.ensure_model_loaded("translator")
        glossary_ctx = _get_glossary_context()
        retry_input = f"Translate the following message:\n\n{original}"
        if glossary_ctx:
            retry_input = f"{glossary_ctx}\n\n{retry_input}"

        stricter_prompt = (
            TRANSLATE_PROMPT
            + "\n\nIMPORTANT: You MUST write in Hebrew script only. Do NOT use Chinese, Latin, or any other script."
        )

        retried = await _call_ollama(
            model,
            stricter_prompt,
            retry_input,
            json_mode=False,
            temperature=0.2,
        )
        retried = retried.strip()

        retry_result = validate_translation(original, retried)
        if retry_result.passed:
            logger.info(f"[{message_id}] Quality gate retry PASSED")
            state["translated_text"] = retried
            return state

        logger.warning(f"[{message_id}] Quality gate retry also FAILED: {retry_result.summary}")
        # Use the retry if it's better (more Hebrew), otherwise keep original
        from app.services.quality_gate import _count_script_chars

        orig_hebrew = _count_script_chars(translated).get("hebrew", 0)
        retry_hebrew = _count_script_chars(retried).get("hebrew", 0)
        if retry_hebrew > orig_hebrew:
            state["translated_text"] = retried

    except Exception as e:
        logger.error(f"[{message_id}] Quality gate retry failed: {e}")

    # Always proceed — add warnings for human reviewer
    state["review_notes"] = f"QUALITY WARNING: {result.summary}"
    return state


# ── Notify Review Node ─────────────────────────────────────────────


async def _pre_stamp_media(state: dict) -> dict:
    """Background task: stamp media while human reviews the message."""
    from app.agents.media_handler import process_media_node

    message_id = state["message_id"]
    try:
        stamped_state = await process_media_node(dict(state))
        logger.info(f"[{message_id}] Pre-stamp complete")
        return stamped_state
    except Exception as e:
        logger.warning(f"[{message_id}] Pre-stamp failed (will retry on approve): {e}")
        return state


async def notify_review_node(state: PipelineState) -> PipelineState:
    """Terminal node: update message with enriched data and notify frontend for human review."""
    message_id = state["message_id"]
    logger.info(f"[{message_id}] Sending enriched data to frontend for human review")

    # Store pipeline state so approve/reject can resume the pipeline
    _pending_reviews[message_id] = dict(state)

    # Pre-stamp media in background while human reviews (saves 5-20s on approval)
    if state.get("media_items"):
        _pre_stamp_tasks[message_id] = asyncio.create_task(_pre_stamp_media(dict(state)))

    try:
        if _ws_manager is not None:
            # Mark reviewer as waiting for human
            await _ws_manager.broadcast(
                {
                    "type": "agent_status",
                    "agent": "Reviewer",
                    "status": "waiting_review",
                    "activity": f"Awaiting human review ({message_id[:8]})",
                }
            )

            # Build media URLs from local/stamped paths
            media_urls = [
                os.path.basename(m["stamped_path"] or m["local_path"])
                for m in state.get("media_items", [])
                if m.get("stamped_path") or m.get("local_path")
            ]

            # Build the enriched message payload
            enriched = {
                "status": "reviewing",
                "translatedText": state.get("translated_text", ""),
                "contentType": state.get("content_type", "other"),
                "extractedFacts": state.get("extracted_facts", []),
                "autoTags": state.get("auto_tags"),
                "title": state.get("title", ""),
                "suggestedTemplateId": state.get("suggested_template_id", ""),
                "formattedOutput": state.get("formatted_output", ""),
                "reviewNotes": state.get("review_notes", ""),
                "geoContext": state.get("geo_context"),
                "sourceTrust": state.get("source_trust"),
                "relatedMessages": state.get("related_messages", []),
                "situationBrief": state.get("situation_brief", ""),
                "rawMetadata": state.get("raw_metadata"),
                "preprocessMeta": state.get("preprocess_meta"),
                "factCheck": state.get("fact_check"),
                "suggestedIntelStatus": state.get("suggested_intel_status", ""),
                "mediaUrls": media_urls,
            }

            # Update the existing message in the frontend store with enriched data
            await _ws_manager.broadcast(
                {
                    "type": "message_update",
                    "message_id": message_id,
                    "updates": enriched,
                }
            )

            # Also broadcast review_request for explicit notification handling
            await _ws_manager.broadcast(
                {
                    "type": "review_request",
                    "message_id": message_id,
                    "message": {
                        "id": message_id,
                        "sourceChannel": state["source_channel"],
                        "originalText": state["original_text"],
                        "translatedText": state.get("translated_text", ""),
                        "mediaUrls": media_urls,
                        "status": "reviewing",
                        "timestamp": state["timestamp"],
                        "extractedFacts": state.get("extracted_facts", []),
                        "autoTags": state.get("auto_tags"),
                        "title": state.get("title", ""),
                        "suggestedTemplateId": state.get("suggested_template_id", ""),
                        "formattedOutput": state.get("formatted_output", ""),
                        "suggestedIntelStatus": state.get("suggested_intel_status", ""),
                        "factCheck": state.get("fact_check"),
                    },
                }
            )

            logger.info(f"[{message_id}] Review request broadcast OK")
        else:
            logger.warning(f"[{message_id}] No ws_manager set — review_request not broadcast")

    except Exception as e:
        logger.error(f"[{message_id}] Failed to broadcast review_request: {e}", exc_info=True)

    return state


def should_route_after_review(state: PipelineState) -> str:
    """After review, either proceed to media processing + publish, or notify the human operator."""
    if state["approved"]:
        return "process_media"
    return "notify_review"


def create_pipeline_graph():
    """Build and compile the LangGraph agent pipeline.

    Flow:
        ingest → translate → content_gate ─┬─(ad/spam)──→ auto_archive → END
                                            └─(ok)──→ quality_gate → geo_enrich → fact_check → review ─┬─(approved)──→ process_media → publish → END
                                                                                          └─(rejected)──→ notify_review → END

    Each agent node is wrapped with _with_status() to broadcast running/idle/error
    status and message progress to the frontend via WebSocket.
    """
    graph = StateGraph(PipelineState)

    # Add agent nodes — each wrapped with status broadcasting
    graph.add_node("ingest", _with_status("ingest", ingest_node))
    graph.add_node("translate", _with_status("translate", translate_node))
    graph.add_node("content_gate", _with_status("content_gate", content_gate_node))
    graph.add_node("auto_archive", auto_archive_node)
    graph.add_node("quality_gate", _with_status("quality_gate", quality_gate_node))
    graph.add_node("geo_enrich", _with_status("geo_enrich", geo_enrich_node))
    graph.add_node("fact_check", _with_status("fact_check", fact_check_node))
    graph.add_node("review", _with_status("review", review_node))
    graph.add_node("notify_review", notify_review_node)
    graph.add_node("process_media", _with_status("process_media", process_media_node))
    graph.add_node("publish", _with_status("publish", publish_node))

    # Sequential edges
    graph.set_entry_point("ingest")
    graph.add_edge("ingest", "translate")
    graph.add_edge("translate", "content_gate")

    # Content gate: ads/spam → auto_archive, everything else → quality_gate
    graph.add_conditional_edges(
        "content_gate",
        should_route_after_content_gate,
        {"auto_archive": "auto_archive", "quality_gate": "quality_gate"},
    )

    graph.add_edge("auto_archive", END)
    graph.add_edge("quality_gate", "geo_enrich")
    graph.add_edge("geo_enrich", "fact_check")
    graph.add_edge("fact_check", "review")

    # Conditional routing after review — explicit path_map ensures LangGraph knows both targets
    graph.add_conditional_edges(
        "review",
        should_route_after_review,
        {"process_media": "process_media", "notify_review": "notify_review"},
    )

    # Approved path: process media, then publish
    graph.add_edge("process_media", "publish")
    graph.add_edge("publish", END)

    # Rejected path: notify human, terminate
    graph.add_edge("notify_review", END)

    return graph.compile()
