"""Pre-Processing Pipeline — stream processing between Telethon events and LangGraph.

Runs inside PipelineRouter.process_message() BEFORE creating PipelineState.
Provides language detection, deduplication, and keyword filtering with zero
external dependencies.
"""

import hashlib
import logging
import time
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

# ── Dedup Cache ───────────────────────────────────────────────

_dedup_cache: dict[str, tuple[str, float]] = {}  # hash → (message_id, timestamp)
_DEDUP_WINDOW = 3600  # 1 hour


def _cleanup_dedup_cache() -> None:
    """Remove expired entries from dedup cache."""
    now = time.time()
    expired = [k for k, (_, ts) in _dedup_cache.items() if now - ts > _DEDUP_WINDOW]
    for k in expired:
        del _dedup_cache[k]


# ── Language Detection ────────────────────────────────────────

# Unicode script ranges for fast heuristic detection
_SCRIPT_RANGES = {
    "arabic": (0x0600, 0x06FF),
    "hebrew": (0x0590, 0x05FF),
    "cyrillic": (0x0400, 0x04FF),
    "cjk": (0x4E00, 0x9FFF),
    "latin": (0x0041, 0x024F),
}


def detect_language(text: str) -> str:
    """Fast Unicode-script-range heuristic for language detection.

    Returns the dominant script name: "arabic", "hebrew", "cyrillic",
    "cjk", "latin", or "unknown". ~0.1ms per call, no LLM needed.
    """
    if not text:
        return "unknown"

    counts: dict[str, int] = {k: 0 for k in _SCRIPT_RANGES}

    for ch in text:
        cp = ord(ch)
        for script, (lo, hi) in _SCRIPT_RANGES.items():
            if lo <= cp <= hi:
                counts[script] += 1
                break

    total = sum(counts.values())
    if total == 0:
        return "unknown"

    dominant = max(counts, key=counts.get)  # type: ignore
    if counts[dominant] / total < 0.3:
        return "mixed"
    return dominant


# ── Keyword Matching ──────────────────────────────────────────


def _get_keywords() -> list[str]:
    """Parse comma-separated keyword list from settings."""
    raw = settings.priority_keywords
    if not raw:
        return []
    return [kw.strip().lower() for kw in raw.split(",") if kw.strip()]


def match_keywords(text: str) -> list[str]:
    """Check text against configured priority keywords.

    Returns list of matched keywords. Case-insensitive.
    """
    if not settings.keyword_filter_enabled:
        return []

    keywords = _get_keywords()
    if not keywords:
        return []

    text_lower = text.lower()
    return [kw for kw in keywords if kw in text_lower]


# ── Deduplication ─────────────────────────────────────────────


def _normalize_text(text: str) -> str:
    """Normalize text for dedup comparison: strip whitespace, lowercase."""
    return " ".join(text.lower().split())


def check_duplicate(text: str, message_id: str) -> tuple[bool, str | None]:
    """Check if text is a duplicate within the dedup window.

    Args:
        text: Message text to check.
        message_id: Current message's UUID.

    Returns:
        Tuple of (is_duplicate, original_message_id or None).
        Duplicates are flagged but NOT discarded — they're corroboration signals.
    """
    if not settings.dedup_enabled:
        return False, None

    _cleanup_dedup_cache()

    normalized = _normalize_text(text)
    if not normalized:
        return False, None

    text_hash = hashlib.sha256(normalized.encode()).hexdigest()

    if text_hash in _dedup_cache:
        original_id, _ = _dedup_cache[text_hash]
        logger.info(f"Duplicate detected: {message_id[:8]} duplicates {original_id[:8]}")
        return True, original_id

    # Store in cache
    _dedup_cache[text_hash] = (message_id, time.time())
    return False, None


# ── Main Pre-Processing Entry Point ──────────────────────────


def preprocess_message(
    text: str,
    message_id: str,
) -> dict[str, Any]:
    """Run the full pre-processing pipeline on a message.

    Called by PipelineRouter.process_message() BEFORE creating PipelineState.

    Returns a PreprocessMeta dict with:
        - language: detected script/language
        - keyword_matches: list of matched keywords
        - priority_score: float (base 0.0, +1.0 per keyword match)
        - is_duplicate: bool
        - duplicate_of: original message_id if duplicate
    """
    # Language detection
    language = detect_language(text)

    # Keyword matching
    keyword_matches = match_keywords(text)
    priority_score = float(len(keyword_matches))

    # Deduplication
    is_duplicate, duplicate_of = check_duplicate(text, message_id)

    result = {
        "language": language,
        "keyword_matches": keyword_matches,
        "priority_score": priority_score,
        "is_duplicate": is_duplicate,
        "duplicate_of": duplicate_of,
    }

    if keyword_matches:
        logger.info(f"[{message_id[:8]}] Keywords matched: {keyword_matches} (priority={priority_score})")

    if is_duplicate:
        logger.info(f"[{message_id[:8]}] Duplicate of {duplicate_of[:8] if duplicate_of else '?'}")

    return result


def get_keywords() -> list[str]:
    """Return the current keyword list (for API exposure)."""
    return _get_keywords()


def set_keywords(keywords_csv: str) -> None:
    """Update the keyword list in settings."""
    settings.priority_keywords = keywords_csv
