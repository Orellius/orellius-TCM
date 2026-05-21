"""Translation service utilities — glossary management and prompt helpers."""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

GLOSSARY_PATH = Path("docs/glossary.json")


def load_glossary() -> dict[str, str]:
    """Load the military jargon glossary (source term → Hebrew translation)."""
    if not GLOSSARY_PATH.exists():
        logger.warning(f"Glossary not found at {GLOSSARY_PATH}")
        return {}

    with open(GLOSSARY_PATH) as f:
        return json.load(f)


def build_glossary_context(glossary: dict[str, str]) -> str:
    """Format the glossary as context for the LLM prompt."""
    if not glossary:
        return ""

    lines = ["Known military terms and their Hebrew translations:"]
    for term, translation in glossary.items():
        lines.append(f"  - {term} → {translation}")

    return "\n".join(lines)
