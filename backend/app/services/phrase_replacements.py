"""Phrase replacement service for post-translation text correction.

Applies configurable find→replace rules to translated text, fixing systematic
AI translation errors (e.g. "ציוני" → "ישראלי").

Replacements are persisted in a JSON file and editable via the API.
Applied automatically after analyst Pass 1 (translation) and before review.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_REPLACEMENTS_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "phrase_replacements.json"

_replacements: list[dict[str, Any]] = []


def _default_replacements() -> list[dict[str, Any]]:
    """Built-in defaults — common AI translation mistakes."""
    return [
        {"find": "ציוני", "replace": "ישראלי", "enabled": True},
        {"find": "ציונים", "replace": "ישראלים", "enabled": True},
        {"find": "הציוני", "replace": "הישראלי", "enabled": True},
        {"find": "הציונים", "replace": "הישראלים", "enabled": True},
        {"find": "הישות הציונית", "replace": "ישראל", "enabled": True},
        {"find": "הכיבוש", "replace": "ישראל", "enabled": True},
    ]


def _load() -> None:
    global _replacements

    if _REPLACEMENTS_FILE.exists():
        try:
            data = json.loads(_REPLACEMENTS_FILE.read_text(encoding="utf-8"))
            _replacements = data if isinstance(data, list) else []
            logger.info(f"Loaded {len(_replacements)} phrase replacements from {_REPLACEMENTS_FILE}")
            return
        except Exception as e:
            backup = _REPLACEMENTS_FILE.with_suffix(".json.bak")
            try:
                _REPLACEMENTS_FILE.rename(backup)
            except Exception:
                pass
            logger.error(f"Failed to parse phrase replacements: {e}, using defaults")

    _replacements = _default_replacements()
    _save()
    logger.info(f"Created default phrase replacements at {_REPLACEMENTS_FILE}")


def _save() -> None:
    _REPLACEMENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = _REPLACEMENTS_FILE.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(_replacements, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp.replace(_REPLACEMENTS_FILE)


def _ensure_loaded() -> None:
    if not _replacements:
        _load()


# ── Public API ────────────────────────────────────────────────


def get_all() -> list[dict[str, Any]]:
    """Return all phrase replacements."""
    _ensure_loaded()
    return list(_replacements)


def apply_replacements(text: str) -> str:
    """Apply all enabled phrase replacements to the given text.

    Returns the modified text. Case-sensitive whole-word matching is NOT used —
    this is plain substring replacement to handle Hebrew morphology correctly
    (prefixes like ה, ב, ל, מ attach directly to words).
    """
    _ensure_loaded()
    if not text:
        return text

    count = 0
    for rule in _replacements:
        if not rule.get("enabled", True):
            continue
        find = rule.get("find", "")
        replace = rule.get("replace", "")
        if find and find in text:
            text = text.replace(find, replace)
            count += 1

    if count > 0:
        logger.info(f"Applied {count} phrase replacement(s)")

    return text


def add_replacement(find: str, replace: str, enabled: bool = True) -> dict[str, Any]:
    """Add a new replacement rule."""
    _ensure_loaded()
    rule: dict[str, Any] = {"find": find, "replace": replace, "enabled": enabled}
    _replacements.append(rule)
    _save()
    return rule


def update_replacement(index: int, data: dict[str, Any]) -> dict[str, Any] | None:
    """Update a replacement rule by index."""
    _ensure_loaded()
    if index < 0 or index >= len(_replacements):
        return None
    for key in ("find", "replace", "enabled"):
        if key in data:
            _replacements[index][key] = data[key]
    _save()
    return _replacements[index]


def delete_replacement(index: int) -> bool:
    """Delete a replacement rule by index."""
    _ensure_loaded()
    if index < 0 or index >= len(_replacements):
        return False
    _replacements.pop(index)
    _save()
    return True
