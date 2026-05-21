"""HFC zone database — maps Israeli cities to Pikud HaOref defense zones.

Loads a static JSON database of ~350 cities, then enriches it on first use
by fetching the full Oref cities database (~1,250+ entries) from:
  https://alerts-history.oref.org.il/Shared/Ajax/GetCitiesMix.aspx?lang=he

The remote data provides zone names (from the ``mixname`` HTML field) and
migun times for every city the HFC system can alert on, eliminating
"Unknown Location" results.
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "hfc_zones.json"

# Remote cities database from Oref
_OREF_CITIES_URL = "https://alerts-history.oref.org.il/Shared/Ajax/GetCitiesMix.aspx?lang=he"
_OREF_HEADERS = {
    "Referer": "https://www.oref.org.il/",
    "X-Requested-With": "XMLHttpRequest",
}

# Refresh remote data every 24 hours
_REMOTE_REFRESH_INTERVAL = 86400

# Lazy singletons
_zones_db: dict[str, Any] | None = None
_remote_cities: dict[str, dict[str, Any]] | None = None  # {city: {"zone": str, "migun_time": int}}
_remote_last_fetch: float = 0

# Regex to extract zone name from mixname HTML: "City | <span>ZoneName</span>"
_MIXNAME_RE = re.compile(r"<span>(.*?)</span>")


def _load_zones_db() -> dict[str, Any]:
    """Load hfc_zones.json on first access."""
    global _zones_db
    if _zones_db is not None:
        return _zones_db
    try:
        _zones_db = json.loads(_DB_PATH.read_text(encoding="utf-8"))
        logger.info(f"Loaded HFC zones DB: {len(_zones_db.get('cities', {}))} cities")
    except Exception as e:
        logger.error(f"Failed to load HFC zones DB: {e}")
        _zones_db = {"zones": {}, "cities": {}}
    return _zones_db


def _fetch_remote_cities() -> dict[str, dict[str, Any]]:
    """Fetch the full Oref cities database and parse it into a lookup dict.

    Returns: {city_name: {"zone": str, "migun_time": int}}
    """
    global _remote_cities, _remote_last_fetch

    now = time.time()
    if _remote_cities is not None and (now - _remote_last_fetch) < _REMOTE_REFRESH_INTERVAL:
        return _remote_cities

    try:
        resp = httpx.get(_OREF_CITIES_URL, headers=_OREF_HEADERS, timeout=15)
        resp.raise_for_status()

        text = resp.text.strip().lstrip("\ufeff").strip()
        if not text:
            logger.warning("Oref cities API returned empty response")
            return _remote_cities or {}

        data = json.loads(text)
        if not isinstance(data, list):
            logger.warning(f"Oref cities API returned unexpected type: {type(data)}")
            return _remote_cities or {}

        result: dict[str, dict[str, Any]] = {}
        for entry in data:
            label = entry.get("label_he") or entry.get("label") or ""
            if not label:
                continue

            # Extract zone name from mixname HTML: "City | <span>ZoneName</span>"
            mixname = entry.get("mixname", "")
            zone_match = _MIXNAME_RE.search(mixname)
            zone = zone_match.group(1) if zone_match else ""

            # migun_time from the API is in seconds
            migun_raw = entry.get("migun_time")
            try:
                migun = int(migun_raw) if migun_raw is not None else 0
            except (ValueError, TypeError):
                migun = 0

            if zone:
                result[label] = {"zone": zone, "migun_time": migun}

        _remote_cities = result
        _remote_last_fetch = now
        logger.info(f"Fetched {len(result)} cities from Oref API")
        return result

    except Exception as e:
        logger.warning(f"Failed to fetch Oref cities database: {e}")
        _remote_last_fetch = now  # avoid hammering on error
        return _remote_cities or {}


def get_city_zone(city_name: str) -> str | None:
    """Return the zone name for a city, or None if unknown."""
    # Try remote database first (most comprehensive) — use cached only to avoid blocking
    remote = _fetch_remote_cities_cached()
    entry = remote.get(city_name)
    if entry:
        return entry["zone"]

    # Fall back to static database
    db = _load_zones_db()
    return db["cities"].get(city_name)


def get_zone_migun_time(zone_name: str) -> int | None:
    """Return the migun time in seconds for a zone, or None if unknown."""
    db = _load_zones_db()
    zone = db["zones"].get(zone_name)
    return zone["migun_time"] if zone else None


def _fetch_remote_cities_cached() -> dict[str, dict[str, Any]]:
    """Return the cached remote cities dict without making any HTTP requests.

    If the cache is empty (never fetched), returns {} — the caller falls back
    to the static DB.  The full fetch is done during HFC prewarm or via
    ``_fetch_remote_cities()`` in a thread pool.
    """
    return _remote_cities or {}


def group_cities_by_zone(
    cities: list[str],
    enriched_labels: list[dict] | None = None,
) -> dict[str, dict[str, Any]]:
    """Group cities by defense zone with per-zone migun time.

    Returns: {zone_name: {"cities": [str], "migun_time": int}}

    Resolution order:
    1. Enriched ``cities_labels`` from the API (each has areaname + migun_time)
    2. Remote Oref cities database (~1,250+ cities with zone + migun)
    3. Static ``hfc_zones.json`` fallback (~350 cities)
    4. "אזור לא מזוהה" for truly unknown cities
    """
    if not cities:
        return {}

    db = _load_zones_db()
    remote = _fetch_remote_cities_cached()
    grouped: dict[str, dict[str, Any]] = {}

    # Build a lookup from enriched labels if available
    label_map: dict[str, dict] = {}
    if enriched_labels:
        for lbl in enriched_labels:
            name = lbl.get("name") or lbl.get("name_he") or ""
            if name:
                label_map[name] = lbl

    for city in cities:
        zone_name: str | None = None
        migun: int | None = None

        # 1. Try enriched label from API response
        lbl = label_map.get(city)
        if lbl:
            zone_name = lbl.get("areaname") or lbl.get("area")
            raw_migun = lbl.get("migun_time") or lbl.get("countdown")
            if raw_migun is not None:
                try:
                    migun = int(raw_migun)
                except (ValueError, TypeError):
                    pass

        # 2. Try remote Oref cities database
        if not zone_name:
            remote_entry = remote.get(city)
            if remote_entry:
                zone_name = remote_entry["zone"]
                if migun is None:
                    migun = remote_entry["migun_time"]

        # 3. Fall back to static DB
        if not zone_name:
            zone_name = db["cities"].get(city)
        if zone_name and migun is None:
            zone_info = db["zones"].get(zone_name)
            if zone_info:
                migun = zone_info["migun_time"]

        # 4. Unknown city
        if not zone_name:
            zone_name = "אזור לא מזוהה"
        if migun is None:
            migun = 0

        if zone_name not in grouped:
            grouped[zone_name] = {"cities": [], "migun_time": migun}
        grouped[zone_name]["cities"].append(city)

    return grouped
