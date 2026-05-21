"""Geo-enrichment pipeline node -- zero-LLM geopolitical intelligence enrichment.

Inserted between quality_gate and review in the LangGraph pipeline.
Runs 4 operations: geo resolution, source trust lookup, post indexing/correlation, escalation detection.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.orchestrator.state import PipelineState

logger = logging.getLogger(__name__)


async def geo_enrich_node(state: PipelineState) -> PipelineState:
    """Enrich pipeline state with geopolitical context, source trust, and situational awareness.

    Performance: ~10-30ms total (static lookups + Redis queries). Zero LLM calls.

    Operations:
    1. resolve_geo_context() -- entity/region -> country codes + flags + conflict context
    2. get_channel_trust() -- PostgreSQL lookup for source reliability
    3. index_post() + find_related_posts() -- Redis write + read for correlation
    4. detect_escalation() -- 3+ posts in same region within window = "developing situation"
    """
    from app.config import settings
    from app.services.geo_resolver import resolve_geo_context
    from app.services.situation_engine import (
        detect_escalation,
        find_related_posts,
        generate_situation_brief,
        index_post,
    )
    from app.services.source_trust import get_channel_trust

    message_id = state.get("message_id", "?")

    # Check if geo enrichment is enabled
    if not getattr(settings, "geo_enrichment_enabled", True):
        logger.info(f"[{message_id[:8]}] Geo enrichment disabled, skipping")
        state.setdefault("geo_context", None)
        state.setdefault("source_trust", None)
        state.setdefault("related_messages", [])
        state.setdefault("situation_brief", "")
        return state

    t0 = time.monotonic()

    try:
        # 1. Resolve geo context from auto_tags + extracted_facts
        auto_tags = state.get("auto_tags") or {}
        extracted_facts = state.get("extracted_facts") or []
        geo_context = resolve_geo_context(auto_tags, extracted_facts)
        state["geo_context"] = dict(geo_context)

        # 2. Get source trust
        source_channel = state.get("source_channel", "")
        try:
            trust_info = await get_channel_trust(source_channel)
            state["source_trust"] = trust_info
        except Exception as e:
            logger.warning(f"[{message_id[:8]}] Source trust lookup failed: {e}")
            state["source_trust"] = None

        # 3. Index post + find related
        region = auto_tags.get("region", "")
        event_type = auto_tags.get("event_type", "")
        timestamp = state.get("timestamp", 0.0)
        title = state.get("title", "")
        threat_level = auto_tags.get("threat_level", "medium")
        country_codes = [c["code"] for c in geo_context.get("countries", [])]

        related: list[dict] = []
        escalation = None

        if region and event_type:
            await index_post(
                message_id=message_id,
                region=region,
                event_type=event_type,
                title=title,
                source_channel=source_channel,
                timestamp=timestamp,
                countries=country_codes,
                threat_level=threat_level,
            )

            related = await find_related_posts(
                region=region,
                event_type=event_type,
                timestamp=timestamp,
                exclude_id=message_id,
            )

            # 4. Detect escalation
            escalation = await detect_escalation(
                region=region,
                event_type=event_type,
            )

        state["related_messages"] = related[:5]

        # Generate situation brief
        brief = generate_situation_brief(related, geo_context, escalation)
        state["situation_brief"] = brief

        elapsed = time.monotonic() - t0
        logger.info(
            f"[{message_id[:8]}] Geo enrichment complete in {elapsed * 1000:.1f}ms -- "
            f"{len(geo_context.get('countries', []))} countries, "
            f"{len(related)} related, "
            f"conflict={geo_context.get('conflict_level', 'none')}"
        )

    except Exception as e:
        logger.error(f"[{message_id[:8]}] Geo enrichment failed: {e}", exc_info=True)
        state.setdefault("geo_context", None)
        state.setdefault("source_trust", None)
        state.setdefault("related_messages", [])
        state.setdefault("situation_brief", "")

    return state
