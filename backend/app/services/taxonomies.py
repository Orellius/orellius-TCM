"""Taxonomy persistence for event types and threat levels.

Follows the same lazy-load + atomic-write pattern as templates.py.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_TAXONOMIES_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "taxonomies.json"

# In-memory store
_taxonomies: dict[str, list[dict[str, Any]]] | None = None


def _default_taxonomies() -> dict[str, list[dict[str, Any]]]:
    """Seed from the original hardcoded EVENT_TYPE_HE / THREAT_LEVEL_HE."""
    return {
        "event_types": [
            {"key": "kinetic_strike", "name_en": "Kinetic Strike", "name_he": "מתקפה קינטית"},
            {"key": "drone_strike", "name_en": "Drone / UAV", "name_he": "תקיפת כטב״ם"},
            {"key": "assassination", "name_en": "Assassination", "name_he": "חיסול ממוקד"},
            {"key": "border_incident", "name_en": "Border Incident", "name_he": "אירוע גבול"},
            {"key": "terrorism", "name_en": "Terror Attack", "name_he": "פיגוע טרור"},
            {"key": "cyber_breach", "name_en": "Cyber Breach", "name_he": "פריצת סייבר"},
            {"key": "movement_deployment", "name_en": "Movement / Deployment", "name_he": "תנועה / פריסה"},
            {"key": "maritime", "name_en": "Maritime", "name_he": "אירוע ימי"},
            {"key": "geopolitical", "name_en": "Geopolitical", "name_he": "גיאופוליטי"},
            {"key": "diplomatic", "name_en": "Diplomatic", "name_he": "דיפלומטי"},
            {"key": "humanitarian", "name_en": "Humanitarian", "name_he": "הומניטרי"},
            {"key": "protest", "name_en": "Protest / Unrest", "name_he": "הפגנה / מהומות"},
            {"key": "sanctions", "name_en": "Sanctions", "name_he": "סנקציות"},
            {"key": "other", "name_en": "Other", "name_he": "אחר"},
            {"key": "fact_check", "name_en": "Fact Check Warning", "name_he": "אזהרת אימות"},
            {"key": "recycled_media", "name_en": "Recycled Media", "name_he": "מדיה ממוחזרת"},
        ],
        "threat_levels": [
            {"key": "critical", "name_en": "Critical", "name_he": "קריטי"},
            {"key": "high", "name_en": "High", "name_he": "גבוה"},
            {"key": "medium", "name_en": "Medium", "name_he": "בינוני"},
            {"key": "low", "name_en": "Low", "name_he": "נמוך"},
            {"key": "info", "name_en": "Info", "name_he": "מידע"},
        ],
    }


def _load_taxonomies() -> None:
    """Load taxonomies from JSON. Seed defaults only on first run (no file)."""
    global _taxonomies

    if _TAXONOMIES_FILE.exists():
        try:
            data = json.loads(_TAXONOMIES_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "event_types" in data and "threat_levels" in data:
                _taxonomies = data
                logger.info(f"Loaded taxonomies from {_TAXONOMIES_FILE}")
                return
        except Exception as e:
            backup = _TAXONOMIES_FILE.with_suffix(".json.bak")
            try:
                _TAXONOMIES_FILE.rename(backup)
                logger.error(f"Failed to parse taxonomies: {e}. Backed up to {backup}, using defaults")
            except Exception:
                logger.error(f"Failed to parse taxonomies: {e}, using defaults")

    # First run — no file exists, seed with defaults
    _taxonomies = _default_taxonomies()
    _save_taxonomies()
    logger.info(f"Created default taxonomies at {_TAXONOMIES_FILE}")


def _save_taxonomies() -> None:
    _TAXONOMIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = _TAXONOMIES_FILE.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(_taxonomies, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp.replace(_TAXONOMIES_FILE)


def _ensure_loaded() -> None:
    if _taxonomies is None:
        _load_taxonomies()


# ── Read ──────────────────────────────────────────────────────


def get_event_types() -> list[dict[str, Any]]:
    _ensure_loaded()
    return _taxonomies["event_types"]  # type: ignore[index]


def get_threat_levels() -> list[dict[str, Any]]:
    _ensure_loaded()
    return _taxonomies["threat_levels"]  # type: ignore[index]


# ── Convenience maps (replace old hardcoded dicts) ────────────


def get_event_type_he_map() -> dict[str, str]:
    """Return {key: name_he} — drop-in replacement for old EVENT_TYPE_HE."""
    _ensure_loaded()
    return {e["key"]: e["name_he"] for e in _taxonomies["event_types"]}  # type: ignore[index]


def get_threat_level_he_map() -> dict[str, str]:
    """Return {key: name_he} — drop-in replacement for old THREAT_LEVEL_HE."""
    _ensure_loaded()
    return {t["key"]: t["name_he"] for t in _taxonomies["threat_levels"]}  # type: ignore[index]


def get_valid_event_type_keys() -> set[str]:
    _ensure_loaded()
    return {e["key"] for e in _taxonomies["event_types"]}  # type: ignore[index]


def get_valid_threat_level_keys() -> set[str]:
    _ensure_loaded()
    return {t["key"] for t in _taxonomies["threat_levels"]}  # type: ignore[index]


# ── CRUD: Event Types ─────────────────────────────────────────


def create_event_type(data: dict[str, Any]) -> dict[str, Any]:
    _ensure_loaded()
    entry = {
        "key": data["key"],
        "name_en": data.get("name_en", ""),
        "name_he": data.get("name_he", ""),
    }
    _taxonomies["event_types"].append(entry)  # type: ignore[index]
    _save_taxonomies()
    return entry


def update_event_type(key: str, data: dict[str, Any]) -> dict[str, Any] | None:
    _ensure_loaded()
    for entry in _taxonomies["event_types"]:  # type: ignore[index]
        if entry["key"] == key:
            if "name_en" in data:
                entry["name_en"] = data["name_en"]
            if "name_he" in data:
                entry["name_he"] = data["name_he"]
            _save_taxonomies()
            return entry
    return None


def delete_event_type(key: str) -> bool:
    _ensure_loaded()
    before = len(_taxonomies["event_types"])  # type: ignore[index]
    _taxonomies["event_types"] = [  # type: ignore[index]
        e
        for e in _taxonomies["event_types"]
        if e["key"] != key  # type: ignore[index]
    ]
    if len(_taxonomies["event_types"]) < before:  # type: ignore[index]
        _save_taxonomies()
        return True
    return False


# ── CRUD: Threat Levels ───────────────────────────────────────


def create_threat_level(data: dict[str, Any]) -> dict[str, Any]:
    _ensure_loaded()
    entry = {
        "key": data["key"],
        "name_en": data.get("name_en", ""),
        "name_he": data.get("name_he", ""),
    }
    _taxonomies["threat_levels"].append(entry)  # type: ignore[index]
    _save_taxonomies()
    return entry


def update_threat_level(key: str, data: dict[str, Any]) -> dict[str, Any] | None:
    _ensure_loaded()
    for entry in _taxonomies["threat_levels"]:  # type: ignore[index]
        if entry["key"] == key:
            if "name_en" in data:
                entry["name_en"] = data["name_en"]
            if "name_he" in data:
                entry["name_he"] = data["name_he"]
            _save_taxonomies()
            return entry
    return None


def delete_threat_level(key: str) -> bool:
    _ensure_loaded()
    before = len(_taxonomies["threat_levels"])  # type: ignore[index]
    _taxonomies["threat_levels"] = [  # type: ignore[index]
        t
        for t in _taxonomies["threat_levels"]
        if t["key"] != key  # type: ignore[index]
    ]
    if len(_taxonomies["threat_levels"]) < before:  # type: ignore[index]
        _save_taxonomies()
        return True
    return False


def reset_taxonomies() -> dict:
    """Reset all event types and threat levels to factory defaults."""
    global _taxonomies
    _taxonomies = _default_taxonomies()
    _save_taxonomies()
    logger.info("Taxonomies reset to defaults")
    return dict(_taxonomies)
