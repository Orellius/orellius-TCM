"""Fast heuristic spam/advertisement filter for Telegram messages.

Runs BEFORE the LLM pipeline (~1ms) to discard obvious promotional content
and save 15-30s of model time per junk message.

Categories:
  - ads: Telegram channel/bot promotions, affiliate links
  - spam: Repetitive forwarded content, engagement bait
  - promo: Sales, discounts, commercial offers

Returns a FilterResult with `is_spam` bool and `reason` string.
"""

import logging
import re

logger = logging.getLogger(__name__)

# ── Pattern sets ──────────────────────────────────────────────

# Telegram self-promotion patterns
_TG_PROMO_PATTERNS = [
    # Join/subscribe channel invitations
    r"(?:join|subscribe|הצטרפו|اشترك|انضم)\s*(?:to|our|ל)?\s*(?:@|t\.me/|https?://t\.me/)",
    # Multiple Telegram links in short text (link farm)
    r"(t\.me/\S+.*?){3,}",
    # Bot links
    r"t\.me/\S+bot\b",
]

# Commercial / advertising patterns
_COMMERCIAL_PATTERNS = [
    # Price patterns (USD, EUR, ₪, currencies)
    r"[\$€₪]\s*\d+[\.,]?\d*",
    r"\d+[\.,]?\d*\s*[\$€₪]",
    r"\d+\s*(?:USD|EUR|ILS|USDT|BTC)\b",
    # Discount / sale language
    r"(?:\d+%\s*(?:off|discount|הנחה|خصم|скидка))",
    r"(?:sale|promo(?:tion)?|deal|offer|מבצע|הנחה|عرض|акция)\b",
    # Casino / betting / crypto scam
    r"(?:casino|betting|bet\b|poker|slot|jackpot|crypto\s*(?:trading|signal))",
    r"(?:guaranteed\s*(?:profit|return|income))",
    # VPN / tool promotion
    r"(?:use\s*(?:my|our)\s*(?:code|link|referral))",
]

# Engagement bait patterns
_BAIT_PATTERNS = [
    # Excessive emoji (8+ emoji in the message)
    r"(?:[\U0001F300-\U0001FAFF\U00002702-\U000027B0].*?){8,}",
    # "Like and share" type bait
    r"(?:like|share|repost|comment|שתפו|שלחו|лайк|репост)\s.*?(?:like|share|repost|comment|שתפו|שלחו)",
]

# URL spam (many links in short text)
_URL_SPAM_PATTERN = re.compile(r"https?://\S+", re.IGNORECASE)

# Compile all patterns for speed
_COMPILED_TG_PROMO = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in _TG_PROMO_PATTERNS]
_COMPILED_COMMERCIAL = [re.compile(p, re.IGNORECASE) for p in _COMMERCIAL_PATTERNS]
_COMPILED_BAIT = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in _BAIT_PATTERNS]


class FilterResult:
    __slots__ = ("category", "is_spam", "reason")

    def __init__(self, is_spam: bool, reason: str = "", category: str = ""):
        self.is_spam = is_spam
        self.reason = reason
        self.category = category  # "ad", "spam", "promo", ""


def check_message(text: str, media_count: int = 0) -> FilterResult:
    """Run fast heuristic checks on a raw message.

    Returns FilterResult with is_spam=True if the message is likely
    an advertisement or spam that should be auto-discarded.
    """
    if not text.strip():
        return FilterResult(False)

    text_stripped = text.strip()
    text_len = len(text_stripped)

    # Very short text with only links → likely ad
    urls = _URL_SPAM_PATTERN.findall(text_stripped)
    text_without_urls = _URL_SPAM_PATTERN.sub("", text_stripped).strip()

    # Message is mostly URLs with no real content
    if urls and len(text_without_urls) < 30 and len(urls) >= 2:
        return FilterResult(True, f"Link farm ({len(urls)} URLs, minimal text)", "spam")

    # Check Telegram self-promotion
    for pattern in _COMPILED_TG_PROMO:
        if pattern.search(text_stripped):
            return FilterResult(True, f"Telegram promotion: {pattern.pattern[:60]}", "ad")

    # Check commercial patterns — require 2+ matches to avoid false positives
    commercial_hits = sum(1 for p in _COMPILED_COMMERCIAL if p.search(text_stripped))
    if commercial_hits >= 2:
        return FilterResult(True, f"Commercial content ({commercial_hits} indicators)", "promo")

    # Single commercial pattern in very short text → likely ad
    if commercial_hits >= 1 and text_len < 100:
        return FilterResult(True, "Short commercial message", "promo")

    # Check engagement bait
    for pattern in _COMPILED_BAIT:
        if pattern.search(text_stripped):
            return FilterResult(True, f"Engagement bait: {pattern.pattern[:60]}", "spam")

    return FilterResult(False)
