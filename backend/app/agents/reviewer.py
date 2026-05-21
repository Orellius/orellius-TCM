"""Reviewer Agent — fast-pass to human review.

Skips the slow LLM quality review (deepseek-r1:32b was adding 10-20s per message).
For OSINT speed, the human operator IS the reviewer. The quality_gate heuristics
already catch bad translations, and the translation quality from qwen2.5:32b is
high enough that LLM-based review is unnecessary overhead.
"""

import logging

from app.config import settings
from app.orchestrator.state import PipelineState

logger = logging.getLogger(__name__)


async def review_node(state: PipelineState) -> PipelineState:
    """LangGraph node: route directly to human review (fast path).

    Previously used deepseek-r1:32b for LLM-based QA, which added 10-20s per message.
    Now skips the LLM call entirely for OSINT speed — human operator reviews directly.
    Auto-approve is available when settings.auto_publish is enabled.
    """
    message_id = state["message_id"]

    if not state["translated_text"].strip():
        logger.info(f"[{message_id}] Empty translation — routing to human review (media-only post?)")
        state["approved"] = False
        state["review_notes"] = "Media-only post — no text content to translate."
        return state

    # Auto-approve path: if auto_publish is enabled, skip human review entirely
    if settings.auto_publish:
        state["approved"] = True
        logger.info(f"[{message_id}] Auto-approved (auto_publish enabled)")
        return state

    # Route to human review (fast — no LLM call)
    state["approved"] = False
    logger.info(f"[{message_id}] Routed to human review (fast path)")

    return state
