"""Translation Quality Gate — fast heuristic validation to catch hallucinations.

No LLM call — pure Unicode analysis and string heuristics for speed.
Runs between the translate and review nodes in the pipeline.
"""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class QualityResult:
    passed: bool
    reasons: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        return "; ".join(self.reasons) if self.reasons else "OK"


def _count_script_chars(text: str) -> dict[str, int]:
    """Count characters by Unicode script block."""
    counts: dict[str, int] = {}
    for ch in text:
        if not ch.isalpha():
            continue
        cp = ord(ch)
        # Hebrew: U+0590–U+05FF, U+FB1D–U+FB4F (presentation forms)
        if 0x0590 <= cp <= 0x05FF or 0xFB1D <= cp <= 0xFB4F:
            script = "hebrew"
        # Arabic: U+0600–U+06FF, U+0750–U+077F, U+FB50–U+FDFF, U+FE70–U+FEFF
        elif 0x0600 <= cp <= 0x06FF or 0x0750 <= cp <= 0x077F or 0xFB50 <= cp <= 0xFDFF or 0xFE70 <= cp <= 0xFEFF:
            script = "arabic"
        # CJK: U+4E00–U+9FFF, U+3400–U+4DBF, U+F900–U+FAFF
        elif 0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF or 0xF900 <= cp <= 0xFAFF:
            script = "cjk"
        # Cyrillic: U+0400–U+04FF
        elif 0x0400 <= cp <= 0x04FF:
            script = "cyrillic"
        # Latin: U+0041–U+024F
        elif 0x0041 <= cp <= 0x024F:
            script = "latin"
        else:
            script = "other"
        counts[script] = counts.get(script, 0) + 1
    return counts


def validate_translation(original: str, translated: str, source_lang_hint: str = "") -> QualityResult:
    """Validate a translation with fast heuristic checks.

    Returns QualityResult with pass/fail and list of failure reasons.
    """
    reasons: list[str] = []

    # ── Check 1: Emptiness ──────────────────────────────────
    if not translated or not translated.strip():
        return QualityResult(passed=False, reasons=["Translation is empty"])

    orig_len = len(original.strip())
    trans_len = len(translated.strip())

    if orig_len > 0 and trans_len < orig_len * 0.1:
        reasons.append(f"Translation too short ({trans_len} chars vs {orig_len} original)")

    # ── Check 2: Wrong-language detection ───────────────────
    script_counts = _count_script_chars(translated)
    total_alpha = sum(script_counts.values())

    if total_alpha > 0:
        hebrew_ratio = script_counts.get("hebrew", 0) / total_alpha
        cjk_count = script_counts.get("cjk", 0)
        cyrillic_count = script_counts.get("cyrillic", 0)

        if hebrew_ratio < 0.4:
            dominant = max(script_counts, key=script_counts.get)  # type: ignore[arg-type]
            reasons.append(f"Low Hebrew content ({hebrew_ratio:.0%} Hebrew, dominant script: {dominant})")

        # Hard fail if CJK or Cyrillic dominate (clear hallucination signal)
        if cjk_count > total_alpha * 0.3:
            reasons.append(f"CJK characters detected ({cjk_count}/{total_alpha} alpha chars)")
        if cyrillic_count > total_alpha * 0.3 and source_lang_hint != "russian":
            reasons.append(f"Unexpected Cyrillic characters ({cyrillic_count}/{total_alpha} alpha chars)")

    # ── Check 3: Echo detection ─────────────────────────────
    # If the "translation" is just the original text echoed back
    if translated.strip() == original.strip():
        reasons.append("Translation is identical to original (echo)")

    # ── Check 4: Repetition detection ───────────────────────
    # Look for any 10+ char substring that repeats 3+ times
    if len(translated) >= 30:
        for length in range(10, min(50, len(translated) // 3)):
            seen: dict[str, int] = {}
            for i in range(len(translated) - length + 1):
                substr = translated[i : i + length]
                seen[substr] = seen.get(substr, 0) + 1
                if seen[substr] >= 3:
                    reasons.append(f"Repetitive text detected ('{substr[:20]}...' repeated {seen[substr]}x)")
                    break
            else:
                continue
            break

    # ── Check 5: Length ratio ───────────────────────────────
    if orig_len > 0:
        ratio = trans_len / orig_len
        if ratio > 5.0:
            reasons.append(f"Translation {ratio:.1f}x longer than original (possible hallucination)")
        elif ratio < 0.1:
            reasons.append(f"Translation {ratio:.1f}x shorter than original")

    passed = len(reasons) == 0
    return QualityResult(passed=passed, reasons=reasons)
