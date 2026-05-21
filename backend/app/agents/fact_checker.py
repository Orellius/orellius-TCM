"""Fact Checker Agent — assesses disinformation risk using local Ollama (qwen2.5:32b).

Runs between geo_enrich and review. Checks for emotional manipulation, unverifiable
claims, inconsistencies, recycled footage indicators, propaganda patterns, and
source reliability.
"""

import json
import logging
import re

import httpx

from app.config import settings
from app.orchestrator.state import FactCheckResult, PipelineState
from app.services.ollama_manager import get_ollama_base, ollama_manager

logger = logging.getLogger(__name__)

FACT_CHECK_PROMPT = """You are an expert disinformation analyst specializing in Middle Eastern, Russian, and Persian-language media.

Analyze the following message for disinformation indicators. Check for:
1. Emotional manipulation — inflammatory language, fear-mongering, outrage-bait
2. Unverifiable claims — extraordinary claims without sources, unnamed officials
3. Internal inconsistencies — contradictory details within the same message
4. Recycled footage indicators — references to old events presented as new
5. Propaganda patterns — one-sided narratives, dehumanizing language, conspiracy theories
6. Source reliability — does the channel have a history of misinformation?

Context:
- Source trust level: {source_trust}
- Number of corroborating reports: {corroboration_count}
- Geo context: {geo_context}

Return a JSON object with exactly these fields:
{{
  "risk_level": "high|medium|low|none",
  "confidence": 0.0-1.0,
  "signals": ["list of specific warning signals in Hebrew"],
  "reasoning": "brief explanation in Hebrew of why this risk level was assigned"
}}

Rules:
- "high" = strong disinformation indicators, multiple red flags
- "medium" = some suspicious elements, needs careful human review
- "low" = minor concerns but generally credible
- "none" = no disinformation indicators detected
- confidence: how sure you are about the assessment (0.0 = uncertain, 1.0 = very confident)
- signals: specific warning signs found, in Hebrew (empty list if none)
- reasoning: 1-2 sentences in Hebrew explaining the assessment

Respond ONLY with the JSON object. No explanations, no markdown fences."""


def _parse_fact_check_output(content: str) -> dict:
    """Parse fact check JSON output with fallback."""
    # Tier 1: direct parse
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            return _validate_fact_check(data)
    except json.JSONDecodeError:
        pass

    # Tier 2: regex extraction
    json_match = re.search(r"\{[\s\S]*\}", content)
    if json_match:
        try:
            data = json.loads(json_match.group())
            if isinstance(data, dict):
                return _validate_fact_check(data)
        except json.JSONDecodeError:
            pass

    # Tier 3: fallback
    logger.warning("Failed to parse fact check JSON, returning safe default")
    return {
        "risk_level": "none",
        "confidence": 0.0,
        "signals": [],
        "reasoning": "",
    }


def _validate_fact_check(data: dict) -> dict:
    """Validate and normalize fact check output."""
    valid_risk_levels = {"high", "medium", "low", "none"}

    risk = data.get("risk_level", "none")
    if risk not in valid_risk_levels:
        risk = "none"

    confidence = data.get("confidence", 0.0)
    try:
        confidence = float(confidence)
        confidence = max(0.0, min(1.0, confidence))
    except (TypeError, ValueError):
        confidence = 0.0

    signals = data.get("signals", [])
    if not isinstance(signals, list):
        signals = []
    signals = [str(s) for s in signals]

    reasoning = str(data.get("reasoning", ""))

    return {
        "risk_level": risk,
        "confidence": confidence,
        "signals": signals,
        "reasoning": reasoning,
    }


def _heuristic_fallback(state: PipelineState) -> FactCheckResult:
    """Quick heuristic checks when LLM fails — based on source trust + corroboration."""
    risk_level = "none"
    confidence = 0.3
    signals: list[str] = []

    # Check source trust
    source_trust = state.get("source_trust")
    if source_trust:
        trust_level = source_trust.get("trust_level", "neutral")
        accuracy = source_trust.get("accuracy_score", 0.5)

        if trust_level in ("suspect", "untrusted") or accuracy < 0.3:
            risk_level = "medium"
            signals.append("מקור בעל אמינות נמוכה")  # Low reliability source
            confidence = 0.5

    # Check for corroboration
    related = state.get("related_messages", [])
    if not related and risk_level != "none":
        signals.append("אין דיווחים מאמתים")  # No corroborating reports
        confidence = min(confidence + 0.1, 1.0)

    flagged = risk_level in ("high", "medium")

    return FactCheckResult(
        risk_level=risk_level,
        confidence=confidence,
        signals=signals,
        reasoning="הערכה היוריסטית — מודל AI לא זמין" if signals else "",
        flagged=flagged,
        override_acknowledged=False,
    )


async def fact_check_node(state: PipelineState) -> PipelineState:
    """LangGraph node: assess disinformation risk of the message."""
    message_id = state["message_id"]

    # Skip if fact checking is disabled
    if not settings.fact_check_enabled:
        state["fact_check"] = None
        return state

    original_text = state.get("original_text", "")
    translated_text = state.get("translated_text", "")

    # Skip empty messages
    if not original_text.strip() and not translated_text.strip():
        state["fact_check"] = FactCheckResult(
            risk_level="none",
            confidence=1.0,
            signals=[],
            reasoning="",
            flagged=False,
            override_acknowledged=False,
        )
        return state

    logger.info(f"[{message_id}] Running fact check assessment")

    try:
        model = await ollama_manager.ensure_model_loaded("translator")

        # Build context from state
        source_trust = state.get("source_trust")
        trust_str = "unknown"
        if source_trust:
            trust_str = (
                f"{source_trust.get('trust_level', 'unknown')} (accuracy: {source_trust.get('accuracy_score', 'N/A')})"
            )

        related = state.get("related_messages", [])
        corroboration_count = len(related)

        geo_ctx = state.get("geo_context")
        geo_str = "unknown"
        if geo_ctx:
            countries = [c.get("name", "") for c in geo_ctx.get("countries", [])]
            geo_str = ", ".join(countries) if countries else "unknown"
            if geo_ctx.get("conflict_level"):
                geo_str += f" ({geo_ctx['conflict_level']})"

        # Build analysis input
        analysis_input_parts = []
        if original_text:
            analysis_input_parts.append(f"Original text:\n{original_text}")
        if translated_text:
            analysis_input_parts.append(f"Hebrew translation:\n{translated_text}")

        facts = state.get("extracted_facts", [])
        if facts:
            facts_str = "\n".join(f"- {f['fact']} [{f['category']}]" for f in facts)
            analysis_input_parts.append(f"Extracted facts:\n{facts_str}")

        tags = state.get("auto_tags")
        if tags:
            analysis_input_parts.append(
                f"Auto tags: event={tags.get('event_type', '?')}, "
                f"region={tags.get('region', '?')}, "
                f"threat={tags.get('threat_level', '?')}"
            )

        analysis_input = "\n\n".join(analysis_input_parts)

        prompt = FACT_CHECK_PROMPT.format(
            source_trust=trust_str,
            corroboration_count=corroboration_count,
            geo_context=geo_str,
        )

        # Call Ollama
        payload: dict = {
            "model": model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": analysis_input},
            ],
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.1,
                "num_predict": 512,
            },
            "keep_alive": settings.ollama_keep_alive,
        }

        async with httpx.AsyncClient(timeout=settings.ollama_inference_timeout) as client:
            resp = await client.post(f"{get_ollama_base()}/api/chat", json=payload)
            resp.raise_for_status()
            raw_output = resp.json()["message"]["content"]

        result = _parse_fact_check_output(raw_output)
        flagged = result["risk_level"] in ("high", "medium")

        state["fact_check"] = FactCheckResult(
            risk_level=result["risk_level"],
            confidence=result["confidence"],
            signals=result["signals"],
            reasoning=result["reasoning"],
            flagged=flagged,
            override_acknowledged=False,
        )

        logger.info(
            f"[{message_id}] Fact check complete — "
            f"risk={result['risk_level']}, confidence={result['confidence']:.2f}, "
            f"flagged={flagged}, signals={len(result['signals'])}"
        )

    except Exception as e:
        logger.error(f"[{message_id}] Fact check LLM failed, using heuristic: {e}")
        state["fact_check"] = _heuristic_fallback(state)

    return state
