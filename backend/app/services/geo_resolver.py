"""Geopolitical entity/region -> country resolution via static lookup tables.

Zero-LLM: all mappings are hardcoded for ~5ms resolution time.
"""

from __future__ import annotations

import logging
from typing import Any, TypedDict

logger = logging.getLogger(__name__)


class GeoCountry(TypedDict):
    code: str  # ISO 3166-1 alpha-2
    name: str  # English name
    flag: str  # Emoji flag


class GeoContext(TypedDict, total=False):
    countries: list[GeoCountry]
    primary_country: GeoCountry | None
    locations: list[str]
    conflict_context: str | None
    conflict_level: str  # active_conflict | regional_tension | strategic_tension | none


# -- Static Lookup Tables -----------------------------------------------------

COUNTRY_NAMES: dict[str, str] = {
    "IL": "Israel",
    "IR": "Iran",
    "LB": "Lebanon",
    "PS": "Palestine",
    "SY": "Syria",
    "IQ": "Iraq",
    "YE": "Yemen",
    "SA": "Saudi Arabia",
    "AE": "UAE",
    "JO": "Jordan",
    "EG": "Egypt",
    "TR": "Turkey",
    "RU": "Russia",
    "UA": "Ukraine",
    "US": "United States",
    "CN": "China",
    "TW": "Taiwan",
    "KP": "North Korea",
    "KR": "South Korea",
    "JP": "Japan",
    "PK": "Pakistan",
    "IN": "India",
    "AF": "Afghanistan",
    "PH": "Philippines",
    "VN": "Vietnam",
    "MM": "Myanmar",
    "SD": "Sudan",
    "LY": "Libya",
    "SO": "Somalia",
    "ET": "Ethiopia",
    "ER": "Eritrea",
    "DJ": "Djibouti",
    "OM": "Oman",
    "BH": "Bahrain",
    "QA": "Qatar",
    "KW": "Kuwait",
    "GB": "United Kingdom",
    "FR": "France",
    "DE": "Germany",
    "BY": "Belarus",
    "PL": "Poland",
    "RO": "Romania",
    "GE": "Georgia",
    "AM": "Armenia",
    "AZ": "Azerbaijan",
}

REGION_TO_COUNTRIES: dict[str, list[str]] = {
    # Levant / Middle East
    "southern_lebanon": ["LB"],
    "northern_israel": ["IL"],
    "gaza_strip": ["PS"],
    "west_bank": ["PS"],
    "gaza": ["PS"],
    "golan_heights": ["IL", "SY"],
    "sinai": ["EG"],
    "negev": ["IL"],
    "galilee": ["IL"],
    "tel_aviv": ["IL"],
    "jerusalem": ["IL", "PS"],
    "beirut": ["LB"],
    "damascus": ["SY"],
    "aleppo": ["SY"],
    "idlib": ["SY"],
    "deir_ez_zor": ["SY"],
    "latakia": ["SY"],
    # Gulf / Arabian Peninsula
    "strait_of_hormuz": ["IR", "OM"],
    "persian_gulf": ["IR", "SA", "AE"],
    "red_sea": ["YE", "SA"],
    "bab_el_mandeb": ["YE", "DJ"],
    "gulf_of_aden": ["YE", "SO"],
    "riyadh": ["SA"],
    "tehran": ["IR"],
    "isfahan": ["IR"],
    "baghdad": ["IQ"],
    "basra": ["IQ"],
    "kurdistan": ["IQ", "TR", "SY"],
    "mosul": ["IQ"],
    "sanaa": ["YE"],
    "aden": ["YE"],
    "marib": ["YE"],
    # Eastern Europe
    "eastern_ukraine": ["UA"],
    "crimea": ["UA"],
    "donbas": ["UA"],
    "donetsk": ["UA"],
    "luhansk": ["UA"],
    "kherson": ["UA"],
    "zaporizhzhia": ["UA"],
    "kharkiv": ["UA"],
    "kyiv": ["UA"],
    "odessa": ["UA"],
    "moscow": ["RU"],
    # East / South Asia
    "south_china_sea": ["CN", "PH", "VN"],
    "taiwan_strait": ["CN", "TW"],
    "east_china_sea": ["CN", "JP"],
    "korean_peninsula": ["KP", "KR"],
    "kashmir": ["IN", "PK"],
    "line_of_control": ["IN", "PK"],
    # Africa
    "sahel": ["SD", "LY"],
    "horn_of_africa": ["SO", "ET", "ER"],
    "tigray": ["ET"],
    "darfur": ["SD"],
    "khartoum": ["SD"],
    # Caucasus
    "nagorno_karabakh": ["AM", "AZ"],
    "south_ossetia": ["GE", "RU"],
    "abkhazia": ["GE", "RU"],
}

ENTITY_TO_COUNTRY: dict[str, str] = {
    # Organizations -- Levant
    "Hezbollah": "LB",
    "Hizballah": "LB",
    "\u062d\u0632\u0628 \u0627\u0644\u0644\u0647": "LB",
    "\u05d7\u05d9\u05d6\u05d1\u05d0\u05dc\u05dc\u05d4": "LB",
    "Hamas": "PS",
    "\u062d\u0645\u0627\u0633": "PS",
    "\u05d7\u05de\u05d0\u05e1": "PS",
    "Islamic Jihad": "PS",
    "PIJ": "PS",
    "\u0627\u0644\u062c\u0647\u0627\u062f \u0627\u0644\u0625\u0633\u0644\u0627\u0645\u064a": "PS",
    "IDF": "IL",
    "Tzahal": "IL",
    '\u05e6\u05d4"\u05dc': "IL",
    "\u0627\u0644\u062c\u064a\u0634 \u0627\u0644\u0625\u0633\u0631\u0627\u0626\u064a\u0644\u064a": "IL",
    "Mossad": "IL",
    "\u05de\u05d5\u05e1\u05d3": "IL",
    "Shin Bet": "IL",
    '\u05e9\u05d1"\u05db': "IL",
    "Iron Dome": "IL",
    "\u05db\u05d9\u05e4\u05ea \u05d1\u05e8\u05d6\u05dc": "IL",
    "SDF": "SY",
    "YPG": "SY",
    "HTS": "SY",
    # Organizations -- Iran
    "IRGC": "IR",
    "\u0627\u0644\u062d\u0631\u0633 \u0627\u0644\u062b\u0648\u0631\u064a": "IR",
    "\u05de\u05e9\u05de\u05e8\u05d5\u05ea \u05d4\u05de\u05d4\u05e4\u05db\u05d4": "IR",
    "Quds Force": "IR",
    "\u0641\u064a\u0644\u0642 \u0627\u0644\u0642\u062f\u0633": "IR",
    "Iranian Army": "IR",
    "Iranian Navy": "IR",
    # Organizations -- Yemen/Gulf
    "Houthis": "YE",
    "Ansar Allah": "YE",
    "\u0627\u0644\u062d\u0648\u062b\u064a\u064a\u0646": "YE",
    "\u05d7\u05d5\u05ea'\u05d9\u05dd": "YE",
    "Saudi Coalition": "SA",
    # Organizations -- Eastern Europe
    "Wagner": "RU",
    "Wagner Group": "RU",
    "\u0432\u0430\u0433\u043d\u0435\u0440": "RU",
    "FSB": "RU",
    "GRU": "RU",
    "\u0424\u0421\u0411": "RU",
    "Russian Army": "RU",
    "Russian Navy": "RU",
    "Azov": "UA",
    "AFU": "UA",
    "Ukrainian Army": "UA",
    # Organizations -- East Asia
    "PLA": "CN",
    "PLAN": "CN",
    "PLA Navy": "CN",
    "KPA": "KP",
    "ROK Army": "KR",
    # Organizations -- Turkey
    "PKK": "TR",
    "TAF": "TR",
    "MIT": "TR",
    # Countries -- English
    "Iran": "IR",
    "Israel": "IL",
    "Lebanon": "LB",
    "Palestine": "PS",
    "Syria": "SY",
    "Iraq": "IQ",
    "Yemen": "YE",
    "Saudi Arabia": "SA",
    "UAE": "AE",
    "Jordan": "JO",
    "Egypt": "EG",
    "Turkey": "TR",
    "Russia": "RU",
    "Ukraine": "UA",
    "China": "CN",
    "Taiwan": "TW",
    "North Korea": "KP",
    "South Korea": "KR",
    "Japan": "JP",
    "Pakistan": "PK",
    "India": "IN",
    "Afghanistan": "AF",
    "United States": "US",
    "USA": "US",
    # Countries -- Arabic
    "\u0625\u064a\u0631\u0627\u0646": "IR",
    "\u0627\u064a\u0631\u0627\u0646": "IR",
    "\u0625\u0633\u0631\u0627\u0626\u064a\u0644": "IL",
    "\u0627\u0633\u0631\u0627\u0626\u064a\u0644": "IL",
    "\u0644\u0628\u0646\u0627\u0646": "LB",
    "\u0641\u0644\u0633\u0637\u064a\u0646": "PS",
    "\u0633\u0648\u0631\u064a\u0627": "SY",
    "\u0633\u0648\u0631\u064a\u0629": "SY",
    "\u0627\u0644\u0639\u0631\u0627\u0642": "IQ",
    "\u0627\u0644\u064a\u0645\u0646": "YE",
    "\u0627\u0644\u0633\u0639\u0648\u062f\u064a\u0629": "SA",
    "\u0627\u0644\u0625\u0645\u0627\u0631\u0627\u062a": "AE",
    "\u0627\u0644\u0623\u0631\u062f\u0646": "JO",
    "\u0645\u0635\u0631": "EG",
    "\u062a\u0631\u0643\u064a\u0627": "TR",
    "\u0631\u0648\u0633\u064a\u0627": "RU",
    "\u0623\u0648\u0643\u0631\u0627\u0646\u064a\u0627": "UA",
    "\u0627\u0644\u0635\u064a\u0646": "CN",
    # Countries -- Hebrew
    "\u05d0\u05d9\u05e8\u05d0\u05df": "IR",
    "\u05d9\u05e9\u05e8\u05d0\u05dc": "IL",
    "\u05dc\u05d1\u05e0\u05d5\u05df": "LB",
    "\u05e4\u05dc\u05e1\u05d8\u05d9\u05df": "PS",
    "\u05e1\u05d5\u05e8\u05d9\u05d4": "SY",
    "\u05e2\u05d9\u05e8\u05d0\u05e7": "IQ",
    "\u05ea\u05d9\u05de\u05df": "YE",
    "\u05e1\u05e2\u05d5\u05d3\u05d9\u05d4": "SA",
    "\u05d0\u05d9\u05d7\u05d5\u05d3 \u05d4\u05d0\u05de\u05d9\u05e8\u05d5\u05d9\u05d5\u05ea": "AE",
    "\u05d9\u05e8\u05d3\u05df": "JO",
    "\u05de\u05e6\u05e8\u05d9\u05dd": "EG",
    "\u05d8\u05d5\u05e8\u05e7\u05d9\u05d4": "TR",
    "\u05e8\u05d5\u05e1\u05d9\u05d4": "RU",
    "\u05d0\u05d5\u05e7\u05e8\u05d0\u05d9\u05e0\u05d4": "UA",
    "\u05e1\u05d9\u05df": "CN",
    "\u05d8\u05d9\u05d9\u05d5\u05d5\u05d0\u05df": "TW",
    "\u05e6\u05e4\u05d5\u05df \u05e7\u05d5\u05e8\u05d9\u05d0\u05d4": "KP",
    "\u05d3\u05e8\u05d5\u05dd \u05e7\u05d5\u05e8\u05d9\u05d0\u05d4": "KR",
    "\u05d0\u05e8\u05e6\u05d5\u05ea \u05d4\u05d1\u05e8\u05d9\u05ea": "US",
    '\u05d0\u05e8\u05d4"\u05d1': "US",
    # Countries -- Russian
    "\u0418\u0440\u0430\u043d": "IR",
    "\u0418\u0437\u0440\u0430\u0438\u043b\u044c": "IL",
    "\u041b\u0438\u0432\u0430\u043d": "LB",
    "\u0421\u0438\u0440\u0438\u044f": "SY",
    "\u0418\u0440\u0430\u043a": "IQ",
    "\u0419\u0435\u043c\u0435\u043d": "YE",
    "\u0420\u043e\u0441\u0441\u0438\u044f": "RU",
    "\u0423\u043a\u0440\u0430\u0438\u043d\u0430": "UA",
    "\u041a\u0438\u0442\u0430\u0439": "CN",
}

# Conflict/alliance pair rules: (country_set, level, description)
CONFLICT_PAIRS: list[tuple[frozenset[str], str, str]] = [
    # Active conflicts
    (frozenset({"IL", "IR"}), "active_conflict", "Israel-Iran proxy and direct confrontation"),
    (frozenset({"IL", "LB"}), "active_conflict", "Israel-Hezbollah border conflict"),
    (frozenset({"IL", "PS"}), "active_conflict", "Israeli-Palestinian conflict"),
    (frozenset({"IL", "SY"}), "active_conflict", "Israel-Syria hostilities"),
    (frozenset({"IL", "YE"}), "active_conflict", "Israel-Houthi conflict"),
    (frozenset({"UA", "RU"}), "active_conflict", "Russia-Ukraine war"),
    (frozenset({"IR", "IL", "LB"}), "active_conflict", "Iran-Israel-Lebanon triangle"),
    (frozenset({"YE", "SA"}), "active_conflict", "Yemen-Saudi conflict"),
    # Regional tensions
    (frozenset({"IR", "SA"}), "regional_tension", "Iran-Saudi regional rivalry"),
    (frozenset({"IR", "AE"}), "regional_tension", "Iran-UAE tensions"),
    (frozenset({"TR", "SY"}), "regional_tension", "Turkey-Syria tensions"),
    (frozenset({"TR", "IQ"}), "regional_tension", "Turkey-Iraq/Kurdistan tensions"),
    (frozenset({"IN", "PK"}), "regional_tension", "India-Pakistan rivalry"),
    (frozenset({"ET", "ER"}), "regional_tension", "Ethiopia-Eritrea tensions"),
    (frozenset({"AM", "AZ"}), "regional_tension", "Armenia-Azerbaijan conflict"),
    (frozenset({"SD", "ET"}), "regional_tension", "Sudan-Ethiopia border dispute"),
    # Strategic tensions
    (frozenset({"CN", "TW"}), "strategic_tension", "Cross-strait tensions"),
    (frozenset({"CN", "US"}), "strategic_tension", "US-China strategic competition"),
    (frozenset({"CN", "PH"}), "strategic_tension", "South China Sea disputes"),
    (frozenset({"CN", "JP"}), "strategic_tension", "East China Sea disputes"),
    (frozenset({"KP", "KR"}), "strategic_tension", "Korean Peninsula tensions"),
    (frozenset({"KP", "US"}), "strategic_tension", "US-North Korea tensions"),
    (frozenset({"RU", "US"}), "strategic_tension", "US-Russia strategic rivalry"),
    (frozenset({"IR", "US"}), "strategic_tension", "US-Iran tensions"),
    (frozenset({"RU", "PL"}), "strategic_tension", "Russia-NATO eastern flank"),
    (frozenset({"RU", "GE"}), "strategic_tension", "Russia-Georgia tensions"),
]


def country_to_flag(code: str) -> str:
    """Convert ISO alpha-2 country code to emoji flag. E.g. 'IR' -> '\U0001f1ee\U0001f1f7'."""
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in code.upper())


def _make_geo_country(code: str) -> GeoCountry:
    return GeoCountry(
        code=code,
        name=COUNTRY_NAMES.get(code, code),
        flag=country_to_flag(code),
    )


def _find_conflict(country_codes: set[str]) -> tuple[str, str]:
    """Find the highest-severity conflict among a set of countries.

    Returns (conflict_level, conflict_context) or ("none", None).
    """
    # Priority order
    level_priority = {"active_conflict": 0, "regional_tension": 1, "strategic_tension": 2}
    best_level = "none"
    best_desc: str | None = None
    best_priority = 999

    for pair_set, level, desc in CONFLICT_PAIRS:
        if pair_set.issubset(country_codes) and level_priority.get(level, 99) < best_priority:
            best_level = level
            best_desc = desc
            best_priority = level_priority[level]

    return best_level, best_desc


def resolve_geo_context(
    auto_tags: dict[str, Any] | None,
    extracted_facts: list[dict[str, Any]] | None,
) -> GeoContext:
    """Resolve entities + region + facts into structured geo context.

    Performance: ~5ms (pure dict lookups, no I/O).
    """
    country_codes: set[str] = set()
    locations: list[str] = []

    if auto_tags:
        # Resolve region
        region = auto_tags.get("region", "")
        if region:
            region_lower = region.lower().replace(" ", "_")
            if region_lower in REGION_TO_COUNTRIES:
                country_codes.update(REGION_TO_COUNTRIES[region_lower])
                locations.append(region)

        # Resolve entities
        for entity in auto_tags.get("entities", []):
            entity_stripped = entity.strip()
            if entity_stripped in ENTITY_TO_COUNTRY:
                country_codes.add(ENTITY_TO_COUNTRY[entity_stripped])

    # Resolve location facts
    if extracted_facts:
        for fact in extracted_facts:
            if fact.get("category") == "location":
                fact_text = fact.get("fact", "")
                if fact_text and fact_text not in locations:
                    locations.append(fact_text)
                # Try to match the fact text against entities/regions
                for token in fact_text.replace(",", " ").split():
                    token = token.strip()
                    if token in ENTITY_TO_COUNTRY:
                        country_codes.add(ENTITY_TO_COUNTRY[token])
                    token_lower = token.lower().replace(" ", "_")
                    if token_lower in REGION_TO_COUNTRIES:
                        country_codes.update(REGION_TO_COUNTRIES[token_lower])

    # Build country objects
    countries = [_make_geo_country(code) for code in sorted(country_codes)]

    # Determine primary country (first one, heuristic: most relevant)
    primary = countries[0] if countries else None

    # Find conflict context
    conflict_level, conflict_context = _find_conflict(country_codes)

    result = GeoContext(
        countries=countries,
        primary_country=primary,
        locations=locations,
        conflict_context=conflict_context,
        conflict_level=conflict_level,
    )

    if countries:
        flags = " ".join(c["flag"] for c in countries)
        logger.info(f"Geo resolved: {flags} | conflict={conflict_level}")

    return result
