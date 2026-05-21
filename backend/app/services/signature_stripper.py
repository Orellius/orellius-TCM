"""Channel signature stripper — detects and removes branding footers from Telegram posts.

Telegram channels commonly append a signature block to every post:
    "לפרסום ב-301: https://t.me/yossi301
     יהונתן חמיאס 301
     העולם הערבי בטלגרם
     https://t.me/arabworld301news"

These signatures pollute translations and waste LLM tokens. This module
detects the boundary between real content and the signature, strips the
signature, and returns both parts.

Works bottom-up: scans from the last line upward, scoring each line for
"signature-likeness". Stops at the first line that looks like real content.
"""

import logging
import re

logger = logging.getLogger(__name__)

# ── Signature indicator patterns ─────────────────────────────

# Strong indicators — a single match marks the line as signature
_STRONG_INDICATORS = [
    # "For advertising" in Hebrew, Arabic, Russian, English
    re.compile(r"לפרסום\b", re.IGNORECASE),
    re.compile(r"للإعلان|للتواصل|للاشتراك", re.IGNORECASE),
    re.compile(r"для\s*рекламы|по\s*рекламе", re.IGNORECASE),
    re.compile(r"\bfor\s+(?:ads?|advertising|promo|contact)\b", re.IGNORECASE),
    # Bare t.me link as the whole line (or nearly)
    re.compile(r"^\s*(?:https?://)?t\.me/\S+\s*$", re.IGNORECASE),
    # Bare @username as the whole line
    re.compile(r"^\s*@\w{3,}\s*$"),
    # "Join us" / "Follow us" patterns
    re.compile(r"(?:הצטרפו|עקבו|انضم|تابع|подписывайтесь|follow\s+us)\b", re.IGNORECASE),
    # "Our channel" patterns
    re.compile(r"(?:הערוץ שלנו|قناتنا|наш канал|our\s+channel)\b", re.IGNORECASE),
]

# Medium indicators — contribute to a score
_MEDIUM_INDICATORS = [
    # t.me link anywhere in the line
    re.compile(r"(?:https?://)?t\.me/\S+", re.IGNORECASE),
    # @username mention (not at start of sentence with content after)
    re.compile(r"@\w{3,}"),
    # Phone number patterns
    re.compile(r"[\+]?\d{1,3}[-.\s]?\(?\d{2,4}\)?[-.\s]?\d{3,}"),
    # "Telegram" as a standalone reference
    re.compile(r"\bבטלגרם\b|\bтелеграм\b|\btelegram\b", re.IGNORECASE),
]

# Separator line patterns — mark the START of a signature block
_SEPARATOR_RE = re.compile(
    r"^\s*["
    r"\u2500-\u257F"  # Box drawing chars (─, ═, etc.)
    r"\u2014\u2015"  # Em dash, horizontal bar
    r"\u23AF"  # Horizontal line extension
    r"\u2E3A\u2E3B"  # Two/three-em dash
    r"=\-_~*•◈◆◇▪▫"  # Common ASCII/symbol separators
    r"]{3,}\s*$"  # At least 3 repeated
)

# Lines that are just emoji / decorative (no real text content)
_DECORATIVE_RE = re.compile(
    r"^\s*["
    r"\U0001F300-\U0001FAFF"  # Emoji
    r"\U00002702-\U000027B0"  # Dingbats
    r"\U0000FE00-\U0000FE0F"  # Variation selectors
    r"\U0000200D"  # ZWJ
    r"\s"
    r"]{2,}\s*$"
)


def _is_signature_line(line: str) -> tuple[bool, int]:
    """Score a single line for signature-likeness.

    Returns (is_definite_signature, score).
    score >= 2 → likely signature line.
    """
    stripped = line.strip()

    # Empty / whitespace-only lines don't break the signature block
    if not stripped:
        return False, 0

    # Separator line → definite signature boundary marker
    if _SEPARATOR_RE.match(stripped):
        return True, 10

    # Decorative emoji line
    if _DECORATIVE_RE.match(stripped):
        return False, 1

    score = 0

    # Strong indicators
    for pattern in _STRONG_INDICATORS:
        if pattern.search(stripped):
            return True, 10

    # Medium indicators
    for pattern in _MEDIUM_INDICATORS:
        if pattern.search(stripped):
            score += 1

    # Very short line (< 40 chars) with a link → more likely signature
    if len(stripped) < 40 and score > 0:
        score += 1

    # Line is just a name / handle (short, no verbs, few words)
    words = stripped.split()
    if 1 <= len(words) <= 4 and len(stripped) < 50:
        # Short lines in a signature context are likely part of the block
        score += 1

    return False, score


def strip_signature(text: str) -> tuple[str, str]:
    """Detect and strip channel signature from the end of a message.

    Returns:
        (clean_text, stripped_signature)

    If no signature is detected, returns (original_text, "").
    """
    if not text or not text.strip():
        return text, ""

    lines = text.split("\n")

    # Don't strip messages that are too short to have real content + signature
    if len(lines) <= 2:
        return text, ""

    # ── Pass 1: Find the topmost strong signature indicator in the bottom half ──
    # Only look in the bottom 60% of the message to avoid false positives
    search_start = max(1, len(lines) * 2 // 5)  # Don't scan top 40%
    topmost_strong = -1

    for i in range(search_start, len(lines)):
        is_definite, _ = _is_signature_line(lines[i])
        if is_definite:
            topmost_strong = i
            break  # First (topmost) strong indicator

    if topmost_strong < 0:
        # No strong indicators found → no signature
        return text, ""

    # ── Pass 2: Expand upward from the strong indicator ──
    # Include blank lines and weak-score lines directly above the strong match
    sig_start = topmost_strong

    for i in range(topmost_strong - 1, max(0, search_start - 1) - 1, -1):
        stripped = lines[i].strip()

        if not stripped:
            # Blank line — check if there's more signature above it
            # Only skip if the line above is also signature-like
            continue

        _, score = _is_signature_line(lines[i])
        if score >= 2:
            sig_start = i
            continue

        # Hit a non-blank, non-signature line → this is where content ends
        break

    # Trim: if the line above sig_start is blank, include it in the sig
    while sig_start > 0 and not lines[sig_start - 1].strip():
        sig_start -= 1

    # Safety: don't strip if it would remove most of the message
    # (signature should be a minority of the text)
    if sig_start <= 1:
        return text, ""

    content_lines = lines[:sig_start]
    sig_lines = lines[sig_start:]

    # Strip trailing blank lines from content
    while content_lines and not content_lines[-1].strip():
        sig_lines.insert(0, content_lines.pop())

    clean_text = "\n".join(content_lines).strip()
    signature = "\n".join(sig_lines).strip()

    # Final safety: if stripping leaves nothing meaningful, don't strip
    if len(clean_text) < 20:
        return text, ""

    if signature:
        logger.debug(f"Stripped signature ({len(signature)} chars): {signature[:80]}...")

    return clean_text, signature
