"""Template library for intelligence reports.

Templates are persisted in a JSON file and editable via the API.
Supports runtime CRUD operations.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from app.services.taxonomies import get_event_type_he_map, get_threat_level_he_map

logger = logging.getLogger(__name__)

# ── Hebrew label maps (dynamic from taxonomies) ─────────────

REGION_HE: dict[str, str] = {
    # ── Israel & Palestinian Territories ──
    "northern_israel": "צפון ישראל",
    "central_israel": "מרכז ישראל",
    "southern_israel": "דרום ישראל",
    "gaza_strip": "רצועת עזה",
    "gaza": "עזה",
    "west_bank": "יהודה ושומרון",
    "golan_heights": "רמת הגולן",
    # ── Lebanon ──
    "lebanon": "לבנון",
    "southern_lebanon": "דרום לבנון",
    "northern_lebanon": "צפון לבנון",
    "beirut": "ביירות",
    # ── Levant & Neighbors ──
    "syria": "סוריה",
    "damascus": "דמשק",
    "aleppo": "חלב",
    "jordan": "ירדן",
    "egypt": "מצרים",
    "cairo": "קהיר",
    "sinai": "סיני",
    "turkey": "טורקיה",
    # ── Iran & Iraq ──
    "iran": "איראן",
    "tehran": "טהראן",
    "iraq": "עיראק",
    "baghdad": "בגדאד",
    # ── Gulf States ──
    "saudi_arabia": "ערב הסעודית",
    "uae": "איחוד האמירויות",
    "qatar": "קטאר",
    "bahrain": "בחריין",
    "kuwait": "כווית",
    "oman": "עומאן",
    "yemen": "תימן",
    # ── Waterways ──
    "persian_gulf": "המפרץ הפרסי",
    "gulf_of_oman": "מפרץ עומאן",
    "strait_of_hormuz": "מצר הורמוז",
    "red_sea": "ים סוף",
    "mediterranean": "הים התיכון",
    "arabian_sea": "הים הערבי",
    "indian_ocean": "האוקיינוס ההודי",
    # ── Europe ──
    "europe": "אירופה",
    "western_europe": "מערב אירופה",
    "eastern_europe": "מזרח אירופה",
    "scandinavia": "סקנדינביה",
    "balkans": "הבלקן",
    "united_kingdom": "בריטניה",
    "france": "צרפת",
    "germany": "גרמניה",
    "italy": "איטליה",
    "spain": "ספרד",
    "poland": "פולין",
    "ukraine": "אוקראינה",
    "russia": "רוסיה",
    "moscow": "מוסקבה",
    # ── Asia ──
    "asia": "אסיה",
    "central_asia": "מרכז אסיה",
    "southeast_asia": "דרום מזרח אסיה",
    "china": "סין",
    "japan": "יפן",
    "north_korea": "צפון קוריאה",
    "south_korea": "דרום קוריאה",
    "taiwan": "טייוואן",
    "india": "הודו",
    "pakistan": "פקיסטן",
    "afghanistan": "אפגניסטן",
    # ── Africa ──
    "africa": "אפריקה",
    "north_africa": "צפון אפריקה",
    "east_africa": "מזרח אפריקה",
    "west_africa": "מערב אפריקה",
    "south_africa_region": "דרום יבשת אפריקה",
    "sahel": "סאהל",
    "horn_of_africa": "קרן אפריקה",
    "libya": "לוב",
    "sudan": "סודאן",
    "somalia": "סומליה",
    # ── Americas ──
    "north_america": "צפון אמריקה",
    "south_america": "דרום אמריקה",
    "central_america": "מרכז אמריקה",
    "caribbean": "הקריביים",
    "united_states": "ארצות הברית",
    "canada": "קנדה",
    "mexico": "מקסיקו",
    "brazil": "ברזיל",
    # ── Other ──
    "australia": "אוסטרליה",
    "pacific_islands": "איי האוקיינוס השקט",
    "global": "גלובלי",
    "unknown": "לא ידוע",
}


INTEL_STATUS_HE: dict[str, str] = {
    "verified": "מאומת ✓",
    "non_official": "לא רשמי",
    "foreign_sources": "מקורות זרים",
}


def _region_to_hebrew(region: str) -> str:
    """Convert snake_case region code to Hebrew display name."""
    if not region:
        return ""
    he = REGION_HE.get(region.lower().strip())
    if he:
        return he
    # Fallback: convert snake_case to readable title case
    return region.replace("_", " ").title()


# ── Template storage ─────────────────────────────────────────

_TEMPLATES_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "templates.json"

# In-memory store
_templates: list[dict[str, Any]] = []
_template_map: dict[str, dict[str, Any]] = {}


def _all_event_type_keys() -> list[str]:
    """Return all event type keys from taxonomies (for wildcard matching)."""
    from app.services.taxonomies import get_event_types

    return [e["key"] for e in get_event_types()]


def _all_threat_level_keys() -> list[str]:
    """Return all threat level keys from taxonomies."""
    from app.services.taxonomies import get_threat_levels

    return [t["key"] for t in get_threat_levels()]


def _default_templates() -> list[dict[str, Any]]:
    """Built-in templates — used when no JSON file exists."""
    all_events = _all_event_type_keys()
    all_threats = _all_threat_level_keys()

    return [
        {
            "id": "flash_alert",
            "name_en": "Flash Alert",
            "name_he": "התרעה מיידית",
            "matching_event_types": ["kinetic_strike", "drone_strike", "assassination", "terrorism", "cyber_breach"],
            "matching_threat_levels": ["critical"],
            "template_body": "\U0001f534 {title}\n\n{translated_text}\n\n\U0001f4cd {region} \u00b7 {timestamp}",
            "priority": 12,
        },
        {
            "id": "kinetic_strike",
            "name_en": "Kinetic Strike Report",
            "name_he": "דו\u05f4ח מתקפה קינטית",
            "matching_event_types": ["kinetic_strike"],
            "matching_threat_levels": ["critical", "high"],
            "template_body": "\U0001f4a5 {title}\n{region} \u00b7 {event_type_he}\n\n{translated_text}\n{intel_status_line}\n\U0001f4cc {entities}",
            "priority": 10,
        },
        {
            "id": "assassination",
            "name_en": "Targeted Killing",
            "name_he": "חיסול ממוקד",
            "matching_event_types": ["assassination"],
            "matching_threat_levels": ["critical", "high"],
            "template_body": "\U0001f3af {title}\n\n{translated_text}\n\n\U0001f539 {entities}\n\U0001f4cd {region} \u00b7 {timestamp}\n{intel_status_line}",
            "priority": 11,
        },
        {
            "id": "terrorism",
            "name_en": "Terror Attack Report",
            "name_he": "דו\u05f4ח פיגוע טרור",
            "matching_event_types": ["terrorism"],
            "matching_threat_levels": ["critical", "high"],
            "template_body": "\U0001f6a8 {title}\n{region}\n\n{translated_text}\n\n\U0001f4cd {timestamp} \u00b7 {threat_level_he}\n{intel_status_line}",
            "priority": 11,
        },
        {
            "id": "drone_strike",
            "name_en": "Drone / UAV Operation",
            "name_he": "תקיפת כטב\u05f4ם",
            "matching_event_types": ["drone_strike"],
            "matching_threat_levels": ["critical", "high", "medium"],
            "template_body": "\U0001f6e9\ufe0f {title}\n{event_type_he} \u2014 {region}\n\n{translated_text}\n{intel_status_line}\n\U0001f4cc {entities}",
            "priority": 9,
        },
        {
            "id": "cyber_breach",
            "name_en": "Cyber Breach Alert",
            "name_he": "התרעת סייבר",
            "matching_event_types": ["cyber_breach"],
            "matching_threat_levels": ["critical", "high", "medium"],
            "template_body": "\U0001f512 {title}\n\n{translated_text}\n\n\U0001f539 {entities}\n{intel_status_line}",
            "priority": 8,
        },
        {
            "id": "border_incident",
            "name_en": "Border Incident",
            "name_he": "אירוע גבול",
            "matching_event_types": ["border_incident"],
            "matching_threat_levels": ["critical", "high", "medium"],
            "template_body": "\U0001f53a {title}\n{region}\n\n{translated_text}\n\n\U0001f4cd {timestamp}\n{intel_status_line}",
            "priority": 7,
        },
        {
            "id": "movement_deployment",
            "name_en": "Movement / Deployment",
            "name_he": "דו\u05f4ח תנועה / פריסה",
            "matching_event_types": ["movement_deployment"],
            "matching_threat_levels": ["critical", "high", "medium", "low"],
            "template_body": "\U0001f504 {title}\n{region}\n\n{translated_text}\n\n{facts_list}",
            "priority": 6,
        },
        {
            "id": "maritime_incident",
            "name_en": "Maritime Incident",
            "name_he": "אירוע ימי",
            "matching_event_types": ["maritime"],
            "matching_threat_levels": ["critical", "high", "medium", "low"],
            "template_body": "\u2693 {title}\n{region}\n\n{translated_text}\n{intel_status_line}",
            "priority": 6,
        },
        {
            "id": "intel_brief",
            "name_en": "Intelligence Brief",
            "name_he": "סיכום מודיעיני",
            "matching_event_types": [
                "kinetic_strike",
                "drone_strike",
                "assassination",
                "cyber_breach",
                "movement_deployment",
                "maritime",
                "geopolitical",
                "diplomatic",
                "border_incident",
                "terrorism",
                "other",
            ],
            "matching_threat_levels": ["critical", "high", "medium", "low", "info"],
            "template_body": "\U0001f4cb {title}\n{event_type_he} \u00b7 {region}\n\n{translated_text}\n\n\u2500\u2500\n{facts_list}\n\n\U0001f539 {entities}\n{intel_status_line}",
            "priority": 4,
        },
        {
            "id": "diplomatic_update",
            "name_en": "Diplomatic Update",
            "name_he": "עדכון דיפלומטי",
            "matching_event_types": ["diplomatic"],
            "matching_threat_levels": ["high", "medium", "low", "info"],
            "template_body": "\U0001f91d {title}\n\n{translated_text}\n\n\U0001f539 {entities}\n\U0001f4cd {region}",
            "priority": 3,
        },
        {
            "id": "humanitarian_report",
            "name_en": "Humanitarian Report",
            "name_he": "דו\u05f4ח הומניטרי",
            "matching_event_types": ["humanitarian"],
            "matching_threat_levels": ["critical", "high", "medium", "low", "info"],
            "template_body": "\U0001f3e5 {title}\n{region}\n\n{translated_text}",
            "priority": 3,
        },
        {
            "id": "protest_unrest",
            "name_en": "Civil Unrest / Protest",
            "name_he": "הפגנה / מהומות",
            "matching_event_types": ["protest"],
            "matching_threat_levels": ["high", "medium", "low", "info"],
            "template_body": "\U0001f4e2 {title}\n{region}\n\n{translated_text}\n\n\U0001f4cd {timestamp}",
            "priority": 3,
        },
        {
            "id": "geopolitical_update",
            "name_en": "Geopolitical Update",
            "name_he": "עדכון גיאופוליטי",
            "matching_event_types": ["geopolitical", "sanctions", "other"],
            "matching_threat_levels": ["critical", "high", "medium", "low", "info"],
            "template_body": "\U0001f310 {title}\n\n{translated_text}\n\n\U0001f539 {entities}\n\U0001f4cd {region}",
            "priority": 2,
        },
        {
            "id": "sanctions_report",
            "name_en": "Sanctions / Economic",
            "name_he": "סנקציות / כלכלי",
            "matching_event_types": ["sanctions"],
            "matching_threat_levels": ["high", "medium", "low", "info"],
            "template_body": "\U0001f4b0 {title}\n\n{translated_text}\n\n\U0001f539 {entities}",
            "priority": 2,
        },
        {
            "id": "fact_check_warning",
            "name_en": "Fact Check Warning",
            "name_he": "אזהרת אימות",
            "matching_event_types": all_events,
            "matching_threat_levels": all_threats,
            "template_body": "\u26a0\ufe0f תוכן לא מאומת\n\n{title}\n\n{translated_text}\n\n\u2757 תוכן זה סומן לבדיקה. יש להתייחס בזהירות ולהמתין לאימות רשמי.\n\U0001f4cd {region} \u00b7 {timestamp}",
            "priority": 13,
        },
        {
            "id": "recycled_media",
            "name_en": "Recycled Media",
            "name_he": "חשד לתוכן ממוחזר",
            "matching_event_types": all_events,
            "matching_threat_levels": all_threats,
            "template_body": "\U0001f501 חשד לתוכן ממוחזר\n\n{title}\n\n{translated_text}\n\n\u2757 תוכן זה עשוי להכיל מדיה ישנה או ממוחזרת. אין אישור שהתוכן עדכני.\n\U0001f4cd {region} \u00b7 {timestamp}",
            "priority": 13,
        },
    ]


def _load_templates() -> None:
    """Load templates from JSON file. If missing, seed defaults once.

    If the file exists (even empty), respect the user's data — never re-inject defaults.
    If the file is corrupted, back it up before falling back to defaults.
    """
    global _templates, _template_map

    if _TEMPLATES_FILE.exists():
        try:
            data = json.loads(_TEMPLATES_FILE.read_text(encoding="utf-8"))
            _templates = data if isinstance(data, list) else []
            logger.info(f"Loaded {len(_templates)} templates from {_TEMPLATES_FILE}")
        except Exception as e:
            # Back up the corrupt file instead of silently overwriting user data
            backup = _TEMPLATES_FILE.with_suffix(".json.bak")
            try:
                _TEMPLATES_FILE.rename(backup)
                logger.error(f"Failed to parse templates: {e}. Backed up to {backup}, using defaults")
            except Exception:
                logger.error(f"Failed to parse templates: {e}, using defaults")
            _templates = _default_templates()
            _save_templates()
    else:
        # First run — no file exists yet, seed with defaults
        _templates = _default_templates()
        _save_templates()
        logger.info(f"Created default templates at {_TEMPLATES_FILE}")

    _template_map = {t["id"]: t for t in _templates}


def _save_templates() -> None:
    """Persist templates to JSON file (atomic write to prevent corruption)."""
    _TEMPLATES_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = _TEMPLATES_FILE.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(_templates, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp.replace(_TEMPLATES_FILE)


def _ensure_loaded() -> None:
    """Lazy-load templates on first access."""
    if not _templates:
        _load_templates()


# ── Public API ────────────────────────────────────────────────


def get_all_templates() -> list[dict[str, Any]]:
    """Return all templates for the frontend (includes template_body for editing)."""
    _ensure_loaded()
    return [
        {
            "id": t["id"],
            "name_en": t.get("name_en", ""),
            "name_he": t.get("name_he", ""),
            "matching_event_types": t.get("matching_event_types", []),
            "matching_threat_levels": t.get("matching_threat_levels", []),
            "priority": t.get("priority", 0),
            "template_body": t.get("template_body", ""),
        }
        for t in _templates
    ]


def get_template(template_id: str) -> dict[str, Any] | None:
    _ensure_loaded()
    return _template_map.get(template_id)


def suggest_template(auto_tags: dict | None) -> str:
    """Score templates against auto_tags and return the best match ID."""
    _ensure_loaded()

    if not auto_tags:
        return ""

    event_type = auto_tags.get("event_type", "other")
    threat_level = auto_tags.get("threat_level", "info")

    best_id = ""
    best_score = -1

    for tpl in _templates:
        score = 0
        if event_type in tpl.get("matching_event_types", []):
            score += 10
        if threat_level in tpl.get("matching_threat_levels", []):
            score += 3
        score += tpl.get("priority", 0) * 0.01

        if score > best_score:
            best_score = score
            best_id = tpl["id"]

    return best_id


def apply_template(
    template_id: str,
    translated_text: str,
    facts: list[dict],
    tags: dict | None,
    timestamp: float | None = None,
    title: str = "",
    intel_status: str = "",
) -> str:
    """Fill a template with extracted data and return formatted report."""
    _ensure_loaded()
    tpl = _template_map.get(template_id)
    if not tpl:
        return translated_text

    tags = tags or {}
    event_type = tags.get("event_type", "other")
    threat_level = tags.get("threat_level", "info")
    region = tags.get("region", "")
    entities = tags.get("entities", [])

    # Format facts as numbered list
    if facts:
        facts_list = "\n".join(f"  {i}. {f.get('fact', '')}" for i, f in enumerate(facts, 1))
    else:
        facts_list = "  אין עובדות שחולצו"

    # Format timestamp
    if timestamp:
        ts_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")
    else:
        ts_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Intel status line — only included if status is selected
    intel_status_he = INTEL_STATUS_HE.get(intel_status, intel_status) if intel_status else ""
    intel_status_line = f"סטטוס: {intel_status_he}\n" if intel_status else ""

    # Translate region to Hebrew
    region_he = _region_to_hebrew(region) if region else ""

    body = tpl["template_body"]

    # If the template uses HTML tags, escape user-generated values to prevent injection
    from app.services.telegram_html import escape as html_escape
    from app.services.telegram_html import is_html_formatted

    if is_html_formatted(body):
        translated_text = html_escape(translated_text)
        title = html_escape(title or "")
        entities_str = html_escape(", ".join(entities) if entities else "לא זוהו")
    else:
        entities_str = ", ".join(entities) if entities else "לא זוהו"

    return body.format(
        event_type_he=get_event_type_he_map().get(event_type, event_type),
        threat_level_he=get_threat_level_he_map().get(threat_level, threat_level),
        region=region_he or "לא צוין",
        timestamp=ts_str,
        facts_list=facts_list,
        entities=entities_str,
        translated_text=translated_text,
        title=title or "",
        intel_status=intel_status_he,
        intel_status_line=intel_status_line,
    )


# ── CRUD operations ──────────────────────────────────────────


def create_template(data: dict[str, Any]) -> dict[str, Any]:
    """Create a new template and persist to file."""
    _ensure_loaded()

    tpl: dict[str, Any] = {
        "id": data.get("id", ""),
        "name_en": data.get("name_en", ""),
        "name_he": data.get("name_he", ""),
        "matching_event_types": data.get("matching_event_types", []),
        "matching_threat_levels": data.get("matching_threat_levels", []),
        "template_body": data.get("template_body", "{translated_text}"),
        "priority": data.get("priority", 0),
    }

    _templates.append(tpl)
    _template_map[tpl["id"]] = tpl
    _save_templates()
    return tpl


def update_template(template_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
    """Update an existing template and persist to file."""
    _ensure_loaded()

    tpl = _template_map.get(template_id)
    if not tpl:
        return None

    for key in ("name_en", "name_he", "matching_event_types", "matching_threat_levels", "template_body", "priority"):
        if key in data:
            tpl[key] = data[key]

    _save_templates()
    return tpl


def delete_template(template_id: str) -> bool:
    """Delete a template and persist to file."""
    _ensure_loaded()

    if template_id not in _template_map:
        return False

    _templates[:] = [t for t in _templates if t["id"] != template_id]
    del _template_map[template_id]
    _save_templates()
    return True


def reset_templates() -> list[dict[str, Any]]:
    """Reset templates to factory defaults. Replaces all user templates."""
    global _templates, _template_map
    _templates = _default_templates()
    _template_map = {t["id"]: t for t in _templates}
    _save_templates()
    logger.info("Templates reset to defaults")
    return list(_templates)


def reorder_templates(ordered_ids: list[str]) -> bool:
    """Reorder templates by assigning priority based on position.

    Position 0 = highest priority.
    """
    _ensure_loaded()
    total = len(ordered_ids)
    for idx, tid in enumerate(ordered_ids):
        tpl = _template_map.get(tid)
        if tpl:
            tpl["priority"] = total - idx
    _save_templates()
    return True
