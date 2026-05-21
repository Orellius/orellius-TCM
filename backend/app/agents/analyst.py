"""Analyst/Translator Agent — two-pass architecture using local Ollama.

Pass 1: Translation — plain-text output, NO JSON mode.  Produces fluent Hebrew.
Pass 2: Analysis    — JSON mode.  Extracts structured intelligence metadata.

Splitting these passes prevents Ollama's constrained JSON decoding from corrupting
the natural-language translation output.
"""

import json
import logging
import re

import httpx

from app.config import settings
from app.orchestrator.state import PipelineState
from app.services.ollama_manager import get_ollama_base, ollama_manager
from app.services.phrase_replacements import apply_replacements
from app.services.taxonomies import get_valid_event_type_keys, get_valid_threat_level_keys
from app.services.templates import suggest_template
from app.services.translator import build_glossary_context, load_glossary

logger = logging.getLogger(__name__)

# ── Pass 1: Translation (plain text, no JSON mode) ─────────────────────

TRANSLATE_PROMPT = """You are a professional Hebrew military intelligence translator.
Translate the following message into fluent, publication-ready Hebrew.

Key requirements:
- Use proper Hebrew military terminology
- Maintain the original meaning and tone
- Keep the translation concise and accurate
- If the message contains coordinates, place names, or military unit designations, preserve them accurately
- You MUST write entirely in Hebrew script

Output ONLY the Hebrew translation, nothing else. No explanations, no JSON, no markdown."""

# ── Pass 2: Analysis (JSON mode) ───────────────────────────────────────


def _build_analysis_prompt() -> str:
    """Build the analysis prompt dynamically from taxonomy keys."""
    event_type_enum = "|".join(get_valid_event_type_keys())
    threat_level_enum = "|".join(get_valid_threat_level_keys())

    return f"""You are a military intelligence analyst. Given an original message and its Hebrew translation, extract structured intelligence metadata.

Return a JSON object with exactly these fields:

{{
  "content_type": "intel|news|editorial|advertisement|spam|other",
  "title": "A punchy 3-5 word Hebrew headline summarizing the event",
  "extracted_facts": [
    {{"fact": "A neutral factual statement in Hebrew", "category": "location|casualty|weapon|unit|timing|action|other"}}
  ],
  "auto_tags": {{
    "event_type": "{event_type_enum}",
    "region": "one of: southern_lebanon|gaza_strip|west_bank|gulf_of_oman|strait_of_hormuz|red_sea|mediterranean|sinai|golan_heights|northern_israel|southern_israel|central_israel|iran|iraq|syria|yemen|libya|sudan|egypt|jordan|turkey|persian_gulf|arabian_sea|indian_ocean|europe|north_america|south_america|africa|asia|lebanon|saudi_arabia|uae|qatar|bahrain|kuwait|oman|united_kingdom|france|germany|ukraine|russia|poland|spain|italy|balkans|scandinavia|eastern_europe|western_europe|china|north_korea|south_korea|japan|india|pakistan|afghanistan|central_asia|southeast_asia|taiwan|united_states|canada|mexico|brazil|caribbean|central_america|north_africa|east_africa|west_africa|south_africa_region|sahel|australia|pacific_islands|global|unknown",
    "threat_level": "{threat_level_enum}",
    "entities": ["named entities mentioned (people, organizations, places, weapons) in original language"]
  }},
  "intel_status": "verified|non_official|foreign_sources|"
}}

Requirements:
- content_type: classify the message content. IMPORTANT — be strict about this:
  * "intel" — military/security intelligence, operational reports, threat alerts
  * "news" — legitimate news reporting about conflicts, politics, events
  * "editorial" — opinion pieces, analysis, commentary on geopolitical events
  * "advertisement" — product/service promotions, channel promotions, affiliate links, commercial offers, crypto/trading signals, VPN/tool promotions, discount codes, paid partnerships
  * "spam" — bot-generated content, engagement bait, forwarded chain messages, repetitive promotional content
  * "other" — anything that doesn't fit the above categories
- title: a short, punchy Hebrew headline (3-5 words max). Think newspaper headline style — dramatic, concise, informative. Examples: "תקיפה אווירית בדרום לבנון", "פריצת סייבר לתשתית אנרגיה"
- Extract 1-5 atomic factual statements in Hebrew
- Each fact: a single verifiable claim with category
- event_type: classify the primary event described. Use the most specific type available from the enum
- region: select the MOST SPECIFIC matching region from the enum list above
- threat_level: assess operational significance (critical = immediate threat, info = background)
- entities: list all named entities in their original language
- intel_status: suggest an intelligence verification status:
  * "verified" — confirmed by multiple credible sources or official statements
  * "non_official" — from a single unverified or unofficial source
  * "foreign_sources" — based on foreign media or intelligence reports
  * "" — cannot determine

Respond ONLY with the JSON object. No explanations, no markdown fences."""


# Glossary loaded once at module level
_glossary: dict[str, str] | None = None


def _get_glossary_context() -> str:
    global _glossary
    if _glossary is None:
        _glossary = load_glossary()
    return build_glossary_context(_glossary)


# Valid region keys matching frontend regionNames — used for enum validation
VALID_REGIONS = {
    # ── Israel & Palestinian Territories ──
    "northern_israel",
    "central_israel",
    "southern_israel",
    "gaza_strip",
    "west_bank",
    "golan_heights",
    "sinai",
    # ── Conflict zones / sub-regions ──
    "southern_lebanon",
    "gulf_of_oman",
    "strait_of_hormuz",
    "red_sea",
    "mediterranean",
    "persian_gulf",
    "arabian_sea",
    "indian_ocean",
    "sahel",
    # ── Middle East & North Africa ──
    "lebanon",
    "syria",
    "jordan",
    "iraq",
    "iran",
    "turkey",
    "egypt",
    "libya",
    "tunisia",
    "algeria",
    "morocco",
    "saudi_arabia",
    "uae",
    "qatar",
    "bahrain",
    "kuwait",
    "oman",
    "yemen",
    # ── Europe ──
    "united_kingdom",
    "ireland",
    "france",
    "germany",
    "netherlands",
    "belgium",
    "luxembourg",
    "switzerland",
    "austria",
    "spain",
    "portugal",
    "italy",
    "greece",
    "cyprus",
    "malta",
    "poland",
    "czech_republic",
    "slovakia",
    "hungary",
    "romania",
    "bulgaria",
    "croatia",
    "serbia",
    "bosnia",
    "montenegro",
    "north_macedonia",
    "albania",
    "kosovo",
    "slovenia",
    "ukraine",
    "russia",
    "belarus",
    "moldova",
    "estonia",
    "latvia",
    "lithuania",
    "finland",
    "sweden",
    "norway",
    "denmark",
    "iceland",
    "georgia",
    "armenia",
    "azerbaijan",
    "balkans",
    "scandinavia",
    "eastern_europe",
    "western_europe",
    # ── Asia ──
    "china",
    "japan",
    "south_korea",
    "north_korea",
    "taiwan",
    "india",
    "pakistan",
    "bangladesh",
    "sri_lanka",
    "nepal",
    "afghanistan",
    "myanmar",
    "thailand",
    "vietnam",
    "cambodia",
    "laos",
    "malaysia",
    "singapore",
    "indonesia",
    "philippines",
    "brunei",
    "mongolia",
    "kazakhstan",
    "uzbekistan",
    "turkmenistan",
    "tajikistan",
    "kyrgyzstan",
    "central_asia",
    "southeast_asia",
    # ── Africa ──
    "sudan",
    "south_sudan",
    "ethiopia",
    "eritrea",
    "somalia",
    "djibouti",
    "kenya",
    "uganda",
    "tanzania",
    "rwanda",
    "burundi",
    "democratic_republic_congo",
    "republic_of_congo",
    "cameroon",
    "chad",
    "central_african_republic",
    "gabon",
    "equatorial_guinea",
    "nigeria",
    "ghana",
    "senegal",
    "mali",
    "burkina_faso",
    "niger",
    "ivory_coast",
    "guinea",
    "guinea_bissau",
    "sierra_leone",
    "liberia",
    "togo",
    "benin",
    "gambia",
    "mauritania",
    "cape_verde",
    "south_africa",
    "namibia",
    "botswana",
    "zimbabwe",
    "zambia",
    "mozambique",
    "malawi",
    "angola",
    "madagascar",
    "mauritius",
    "north_africa",
    "east_africa",
    "west_africa",
    "south_africa_region",
    # ── Americas ──
    "united_states",
    "canada",
    "mexico",
    "guatemala",
    "belize",
    "honduras",
    "el_salvador",
    "nicaragua",
    "costa_rica",
    "panama",
    "cuba",
    "haiti",
    "dominican_republic",
    "jamaica",
    "puerto_rico",
    "trinidad_and_tobago",
    "colombia",
    "venezuela",
    "ecuador",
    "peru",
    "bolivia",
    "brazil",
    "argentina",
    "chile",
    "uruguay",
    "paraguay",
    "guyana",
    "suriname",
    "caribbean",
    "central_america",
    # ── Oceania ──
    "australia",
    "new_zealand",
    "papua_new_guinea",
    "fiji",
    "pacific_islands",
    # ── Continents / general ──
    "europe",
    "north_america",
    "south_america",
    "africa",
    "asia",
    "global",
    "unknown",
}


def _validate_analysis_output(data: dict) -> dict:
    """Ensure the parsed analysis output has correct types and valid enum values."""
    valid_categories = {"location", "casualty", "weapon", "unit", "timing", "action", "other"}
    valid_event_types = get_valid_event_type_keys()
    valid_threat_levels = get_valid_threat_level_keys()
    valid_content_types = {"intel", "news", "editorial", "advertisement", "spam", "other"}

    # Validate content_type
    ct = data.get("content_type", "other")
    if not isinstance(ct, str) or ct not in valid_content_types:
        ct = "other"
    data["content_type"] = ct

    # Validate title
    title = data.get("title", "")
    if not isinstance(title, str):
        title = ""
    data["title"] = title.strip()

    # Validate extracted_facts
    facts = data.get("extracted_facts")
    if not isinstance(facts, list):
        data["extracted_facts"] = []
    else:
        clean_facts = []
        for f in facts:
            if isinstance(f, dict) and "fact" in f:
                cat = f.get("category", "other")
                if cat not in valid_categories:
                    cat = "other"
                clean_facts.append({"fact": str(f["fact"]), "category": cat})
        data["extracted_facts"] = clean_facts

    # Validate auto_tags
    tags = data.get("auto_tags")
    if isinstance(tags, dict):
        et = tags.get("event_type", "other")
        if et not in valid_event_types:
            et = "other"
        tl = tags.get("threat_level", "info")
        if tl not in valid_threat_levels:
            tl = "info"
        entities = tags.get("entities", [])
        if not isinstance(entities, list):
            entities = []
        region = str(tags.get("region", "unknown")).lower().strip()
        if region not in VALID_REGIONS:
            region = "unknown"
        data["auto_tags"] = {
            "event_type": et,
            "region": region,
            "threat_level": tl,
            "entities": [str(e) for e in entities],
        }
    else:
        data["auto_tags"] = None

    # Validate intel_status
    valid_intel_statuses = {"verified", "non_official", "foreign_sources", ""}
    intel_status = data.get("intel_status", "")
    if not isinstance(intel_status, str) or intel_status not in valid_intel_statuses:
        intel_status = ""
    data["intel_status"] = intel_status

    return data


def _parse_analysis_output(content: str) -> dict:
    """Parse Pass 2 JSON output with fallback.

    Tier 1: Direct JSON parse
    Tier 2: Regex extraction of JSON from surrounding text
    Tier 3: Empty fallback
    """
    # Tier 1: direct parse
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            return _validate_analysis_output(data)
    except json.JSONDecodeError:
        pass

    # Tier 2: regex extraction
    json_match = re.search(r"\{[\s\S]*\}", content)
    if json_match:
        try:
            data = json.loads(json_match.group())
            if isinstance(data, dict):
                return _validate_analysis_output(data)
        except json.JSONDecodeError:
            pass

    # Tier 3: fallback
    logger.warning("Failed to parse analysis JSON, returning empty metadata")
    return {
        "title": "",
        "extracted_facts": [],
        "auto_tags": None,
    }


async def _call_ollama(
    model: str, system: str, user: str, *, json_mode: bool = False, temperature: float = 0.3, max_tokens: int = 2048
) -> str:
    """Make a single Ollama chat completion call and return the content string."""
    payload: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
        "keep_alive": settings.ollama_keep_alive,
    }
    if json_mode:
        payload["format"] = "json"

    async with httpx.AsyncClient(timeout=settings.ollama_inference_timeout) as client:
        resp = await client.post(f"{get_ollama_base()}/api/chat", json=payload)
        resp.raise_for_status()
        return resp.json()["message"]["content"]


async def translate_node(state: PipelineState) -> PipelineState:
    """LangGraph node: translate and analyze the original text using local qwen2.5:32b.

    Two-pass architecture:
      Pass 1 — Translation (plain text, no JSON mode) → fluent Hebrew
      Pass 2 — Analysis (JSON mode) → extracted_facts + auto_tags
    """
    message_id = state["message_id"]
    original_text = state["original_text"]

    if not original_text.strip():
        logger.info(f"[{message_id}] Empty text, skipping translation")
        state["translated_text"] = ""
        state["content_type"] = "other"
        state["translation_approved"] = True
        state["extracted_facts"] = []
        state["auto_tags"] = None
        state["title"] = ""
        state["suggested_template_id"] = ""
        state["formatted_output"] = ""
        state["suggested_intel_status"] = ""
        return state

    logger.info(f"[{message_id}] Translating and analyzing text ({len(original_text)} chars)")

    try:
        model = await ollama_manager.ensure_model_loaded("translator")

        # Build user content with optional glossary
        glossary_ctx = _get_glossary_context()
        translate_input = f"Translate the following message:\n\n{original_text}"
        if glossary_ctx:
            translate_input = f"{glossary_ctx}\n\n{translate_input}"

        # ── Pass 1: Translation (plain text) ──────────────────
        logger.info(f"[{message_id}] Pass 1: translating to Hebrew (plain text mode)")
        translated_text = await _call_ollama(
            model,
            TRANSLATE_PROMPT,
            translate_input,
            json_mode=False,
            temperature=0.3,
            max_tokens=600,
        )
        translated_text = translated_text.strip()

        # ── Phrase replacements (fix systematic AI mistakes) ──
        translated_text = apply_replacements(translated_text)

        logger.info(f"[{message_id}] Pass 1 complete — {len(translated_text)} chars")

        # ── Pass 2: Analysis (JSON mode) ──────────────────────
        logger.info(f"[{message_id}] Pass 2: extracting intelligence metadata (JSON mode)")
        analysis_input = f"Original message:\n{original_text}\n\nHebrew translation:\n{translated_text}"
        analysis_raw = await _call_ollama(
            model,
            _build_analysis_prompt(),
            analysis_input,
            json_mode=True,
            temperature=0.1,
            max_tokens=400,
        )
        analysis = _parse_analysis_output(analysis_raw)

        # ── Populate state ────────────────────────────────────
        state["translated_text"] = translated_text
        state["content_type"] = analysis.get("content_type", "other")
        state["extracted_facts"] = analysis["extracted_facts"]
        state["auto_tags"] = analysis["auto_tags"]
        state["title"] = analysis.get("title", "")
        state["translation_approved"] = False

        # Suggest a template based on auto_tags
        state["suggested_template_id"] = suggest_template(analysis["auto_tags"])
        state["formatted_output"] = ""
        state["suggested_intel_status"] = analysis.get("intel_status", "")

        logger.info(
            f"[{message_id}] Analysis complete — "
            f"{len(analysis['extracted_facts'])} facts, "
            f"tags={analysis['auto_tags']}, "
            f"suggested_template={state['suggested_template_id']}"
        )

    except Exception as e:
        logger.error(f"[{message_id}] Translation/analysis failed: {e}")
        state["translated_text"] = f"[TRANSLATION ERROR: {e}]"
        state["content_type"] = "other"
        state["translation_approved"] = False
        state["extracted_facts"] = []
        state["auto_tags"] = None
        state["title"] = ""
        state["suggested_template_id"] = ""
        state["formatted_output"] = ""
        state["suggested_intel_status"] = ""

    return state
