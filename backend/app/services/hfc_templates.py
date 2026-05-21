"""HFC (Home Front Command) alert template system.

Separate from the main intelligence report templates. Manages formatting
for real-time civil defense alerts (rockets, hostile aircraft, etc.).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_HFC_TEMPLATES_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "hfc_templates.json"

# In-memory store: {category_key: template_body_string}
_hfc_templates: dict[str, dict[str, Any]] | None = None


def _default_hfc_templates() -> dict[str, dict[str, Any]]:
    """Built-in HFC alert templates matching the official HFC Telegram format.

    Reference: t.me/PikudHaOref_3
    """
    return {
        "rockets": {
            "name_he": "ירי רקטות וטילים",
            "template_body": (
                "🚨 <b>{category_he}</b> ({timestamp})\n\n{zones_block}\n\nהיכנסו למרחב המוגן ושהו בו 10 דקות"
            ),
        },
        "hostile_aircraft": {
            "name_he": "חדירת כלי טיס עוין",
            "template_body": ("🚨 <b>חדירת כלי טיס עוין</b> ({timestamp})\n\n{zones_block}\n\nהיכנסו למרחב המוגן"),
        },
        "earthquake": {
            "name_he": "רעידת אדמה",
            "template_body": ("🌍 <b>רעידת אדמה</b> ({timestamp})\n\n{zones_block}\n\n{guidance}"),
        },
        "tsunami": {
            "name_he": "צונאמי",
            "template_body": ("🌊 <b>התרעת צונאמי</b> ({timestamp})\n\n{zones_block}\n\n{guidance}"),
        },
        "hazardous_materials": {
            "name_he": "חומרים מסוכנים",
            "template_body": ("☣️ <b>אירוע חומרים מסוכנים</b> ({timestamp})\n\n{zones_block}\n\n{guidance}"),
        },
        "terror_infiltration": {
            "name_he": "חדירת מחבלים",
            "template_body": ("⚠️ <b>חדירת מחבלים</b> ({timestamp})\n\n{zones_block}\n\n{guidance}"),
        },
        "nonconventional": {
            "name_he": "איום לא קונבנציונלי",
            "template_body": (
                "☢️ <b>איום לא קונבנציונלי</b> ({timestamp})\n\n"
                "{zones_block}\n\n"
                "היכנסו למרחב מוגן, סגרו דלתות וחלונות ועקבו אחר הנחיות פיקוד העורף."
            ),
        },
        "cbrne": {
            "name_he": "איום כימי ביולוגי רדיולוגי",
            "template_body": (
                "☣️ <b>איום כימי / ביולוגי / רדיולוגי</b> ({timestamp})\n\n"
                "{zones_block}\n\n"
                "היכנסו למרחב מוגן, סגרו חלונות ודלתות ואטמו את החדר."
            ),
        },
        "warning": {
            "name_he": "התרעה כללית",
            "template_body": ("🔔 <b>{alert_title}</b> ({timestamp})\n\n{zones_block}\n\n{guidance}"),
        },
        "update": {
            "name_he": "עדכון",
            "template_body": ("ℹ️ <b>{alert_title}</b> ({timestamp})\n\n{zones_block}\n\n{guidance}"),
        },
        "general": {
            "name_he": "התרעה כללית",
            "template_body": ("🔔 <b>{alert_title}</b> ({timestamp})\n\n{zones_block}\n\n{guidance}"),
        },
        "all_clear": {
            "name_he": "ניתן לצאת ממרחב מוגן",
            "template_body": (
                "✅ <b>ניתן לצאת ממרחב מוגן</b> ({timestamp})\n\nהשוהים במרחב המוגן יכולים לצאת.\n\n{zones_block}"
            ),
        },
        "early_warning": {
            "name_he": "התרעה מוקדמת",
            "template_body": (
                "🟠 <b>התרעה מוקדמת</b> ({timestamp})\n\n"
                "בדקות הקרובות צפויות להתקבל התרעות באזורך.\n"
                "על תושבי האזורים הבאים לשפר את המיקום למיגון המיטבי בקרבתך. "
                "במקרה של קבלת התרעה, יש להיכנס למרחב המוגן ולשהות בו עד להודעה חדשה.\n\n"
                "{zones_block}"
            ),
        },
        "incident_resolved": {
            "name_he": "האירוע הסתיים",
            "template_body": (
                "🔵 <b>האירוע הסתיים</b> ({timestamp})\n\nהשוהים במרחב המוגן יכולים לצאת.\n\n{zones_block}"
            ),
        },
    }


# ── Persistence ───────────────────────────────────────────────


def _load_hfc_templates() -> None:
    """Load HFC templates from JSON. Seed defaults only on first run (no file)."""
    global _hfc_templates

    if _HFC_TEMPLATES_FILE.exists():
        try:
            data = json.loads(_HFC_TEMPLATES_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                _hfc_templates = data
                logger.info(f"Loaded {len(_hfc_templates)} HFC templates from {_HFC_TEMPLATES_FILE}")
                return
        except Exception as e:
            backup = _HFC_TEMPLATES_FILE.with_suffix(".json.bak")
            try:
                _HFC_TEMPLATES_FILE.rename(backup)
                logger.error(f"Failed to parse HFC templates: {e}. Backed up to {backup}")
            except Exception:
                logger.error(f"Failed to parse HFC templates: {e}")

    # First run — no file exists, seed with defaults
    _hfc_templates = _default_hfc_templates()
    _save_hfc_templates()
    logger.info(f"Created default HFC templates at {_HFC_TEMPLATES_FILE}")


def _save_hfc_templates() -> None:
    """Persist HFC templates to JSON (atomic write)."""
    _HFC_TEMPLATES_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = _HFC_TEMPLATES_FILE.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(_hfc_templates, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp.replace(_HFC_TEMPLATES_FILE)


def _ensure_loaded() -> None:
    """Lazy-load on first access."""
    if _hfc_templates is None:
        _load_hfc_templates()


# ── Public API ────────────────────────────────────────────────


def get_all_hfc_templates() -> dict[str, dict[str, Any]]:
    """Return all HFC templates for the frontend."""
    _ensure_loaded()
    return dict(_hfc_templates)  # type: ignore[arg-type]


def get_hfc_template(key: str) -> dict[str, Any] | None:
    """Return a single HFC template by category key."""
    _ensure_loaded()
    return _hfc_templates.get(key)  # type: ignore[union-attr]


def update_hfc_template(key: str, data: dict[str, Any]) -> dict[str, Any] | None:
    """Update an HFC template's body/name and persist."""
    _ensure_loaded()
    tpl = _hfc_templates.get(key)  # type: ignore[union-attr]
    if tpl is None:
        return None

    if "template_body" in data:
        tpl["template_body"] = data["template_body"]
    if "name_he" in data:
        tpl["name_he"] = data["name_he"]

    _save_hfc_templates()
    return tpl


def apply_hfc_template(key: str, alert_data: dict[str, Any]) -> str:
    """Format an HFC alert using the template for the given category.

    alert_data keys:
        timestamp, zones_block, cities_list, city_count,
        min_migun_time, max_migun_time, guidance, alert_title, category_he
    """
    _ensure_loaded()
    tpl = _hfc_templates.get(key)  # type: ignore[union-attr]
    # For drill categories, fall back to the parent real-alert template
    if not tpl and key.endswith("_drill"):
        parent_key = key.removesuffix("_drill")
        tpl = _hfc_templates.get(parent_key)  # type: ignore[union-attr]
    if not tpl:
        # Fallback: generic format
        return f"🔔 {alert_data.get('alert_title', 'התרעה')}\n{alert_data.get('zones_block', '')}\n🕐 {alert_data.get('timestamp', '')}"

    body = tpl["template_body"]

    # Safe format — skip missing keys gracefully
    try:
        return body.format(**alert_data)
    except KeyError as e:
        logger.warning(f"HFC template '{key}' missing placeholder: {e}")
        # Fill with what we can
        for k, v in alert_data.items():
            body = body.replace(f"{{{k}}}", str(v))
        return body


def _build_zones_block(grouped_cities: dict[str, dict]) -> str:
    """Build compact zones block — single line per zone with bullet.

    Format:  • <b>zone_name</b>: city1, city2 (migun_time)
    Receives: {zone: {"cities": [...], "migun_time": int}}
    """
    if not grouped_cities:
        return ""
    from app.services.hfc_alerts import _format_migun

    lines = []
    for zone, info in grouped_cities.items():
        cities = info.get("cities", [])
        migun = info.get("migun_time")
        migun_str = f" ({_format_migun(migun)})" if migun else ""
        lines.append(f"• <b>{zone}</b>: {', '.join(cities)}{migun_str}")
    return "\n".join(lines)
