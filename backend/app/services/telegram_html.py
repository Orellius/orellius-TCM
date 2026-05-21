"""Telegram HTML formatting utilities.

Provides safe escaping and detection for Telegram's supported HTML subset:
<b>, <i>, <u>, <s>, <code>, <pre>, <a>, <tg-spoiler>.
"""

from __future__ import annotations

import re

# Regex matching any Telegram-supported HTML tag (opening or closing)
_HTML_TAG_RE = re.compile(
    r"</?(?:b|i|u|s|code|pre|a(?:\s|>)|tg-spoiler)[^>]*>",
    re.IGNORECASE,
)


def escape(text: str) -> str:
    """Escape &, <, > for safe embedding inside Telegram HTML.

    Does NOT escape quotes since Telegram only requires these three
    to be escaped in message text.
    """
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def is_html_formatted(text: str) -> bool:
    """Return True if text contains any Telegram HTML tags."""
    return bool(_HTML_TAG_RE.search(text))


def safe_parse_mode(text: str) -> str | None:
    """Return 'html' if text contains HTML tags, None otherwise.

    Used to conditionally set parse_mode on Telegram send calls so
    plain-text messages are not affected.
    """
    return "html" if is_html_formatted(text) else None
