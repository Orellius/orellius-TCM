"""Home Front Command (Pikud HaOref) direct alert poller.

Single-source architecture: polls ``oref.org.il/WarningMessages/alert/alerts.json``
at 500ms intervals with a persistent HTTP connection.  Adaptive mode drops to 300ms
during active alert waves (60s window after the last alert).

No third-party dependencies — Oref is the authoritative and only source.
"""

from __future__ import annotations

import asyncio
import json as _json
import logging
import random
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# ── Category mapping (keyed by matrix_id from alertCategories.json) ────
#
# The HFC API `cat` field uses `matrix_id`, NOT sequential IDs.
# Source: https://www.oref.org.il/alerts/alertCategories.json

HFC_CATEGORIES: dict[str, dict[str, str]] = {
    # ── Real alerts ──
    "1": {"key": "rockets", "name_he": "ירי רקטות וטילים", "emoji": "🚀"},
    "2": {"key": "nonconventional", "name_he": "איום לא קונבנציונלי", "emoji": "☢️"},
    "3": {"key": "earthquake", "name_he": "רעידת אדמה", "emoji": "🌍"},
    "4": {"key": "cbrne", "name_he": "איום כימי ביולוגי רדיולוגי", "emoji": "☣️"},
    "5": {"key": "tsunami", "name_he": "צונאמי", "emoji": "🌊"},
    "6": {"key": "hostile_aircraft", "name_he": "כלי טיס עוין", "emoji": "✈️"},
    "7": {"key": "hazardous_materials", "name_he": "חומרים מסוכנים", "emoji": "☣️"},
    "8": {"key": "warning", "name_he": "התרעה כללית", "emoji": "🔔"},
    "10": {"key": "update", "name_he": "עדכון", "emoji": "ℹ️"},
    "13": {"key": "terror_infiltration", "name_he": "חדירת מחבלים", "emoji": "⚠️"},
    # ── Drills (matrix_id 101+) ──
    "101": {"key": "rockets_drill", "name_he": "תרגיל ירי רקטות וטילים", "emoji": "🔰"},
    "102": {"key": "nonconventional_drill", "name_he": "תרגיל איום לא קונבנציונלי", "emoji": "🔰"},
    "103": {"key": "earthquake_drill", "name_he": "תרגיל רעידת אדמה", "emoji": "🔰"},
    "104": {"key": "cbrne_drill", "name_he": "תרגיל כימי ביולוגי", "emoji": "🔰"},
    "105": {"key": "tsunami_drill", "name_he": "תרגיל צונאמי", "emoji": "🔰"},
    "106": {"key": "hostile_aircraft_drill", "name_he": "תרגיל כלי טיס עוין", "emoji": "🔰"},
    "107": {"key": "hazardous_materials_drill", "name_he": "תרגיל חומרים מסוכנים", "emoji": "🔰"},
    "110": {"key": "update_drill", "name_he": "תרגיל עדכון", "emoji": "🔰"},
    "113": {"key": "terror_infiltration_drill", "name_he": "תרגיל חדירת מחבלים", "emoji": "🔰"},
}

# Reverse mapping: Hebrew title → category info.
# The API `title` field is authoritative — use it to correct any cat-ID mismatch.
_TITLE_TO_CATEGORY: dict[str, dict[str, str]] = {
    "ירי רקטות וטילים": {"key": "rockets", "emoji": "🚀"},
    "התראת טילים": {"key": "rockets", "emoji": "🚀"},
    "חדירת כלי טיס עוין": {"key": "hostile_aircraft", "emoji": "✈️"},
    "כלי טיס עוין": {"key": "hostile_aircraft", "emoji": "✈️"},
    "כלי טייס עוין": {"key": "hostile_aircraft", "emoji": "✈️"},
    "כלי טייס עויין": {"key": "hostile_aircraft", "emoji": "✈️"},
    "רחפן": {"key": "hostile_aircraft", "emoji": "✈️"},
    "רעידת אדמה": {"key": "earthquake", "emoji": "🌍"},
    "צונאמי": {"key": "tsunami", "emoji": "🌊"},
    "חומרים מסוכנים": {"key": "hazardous_materials", "emoji": "☣️"},
    "חדירת מחבלים": {"key": "terror_infiltration", "emoji": "⚠️"},
    "התרעה כללית": {"key": "warning", "emoji": "🔔"},
    "איום לא קונבנציונלי": {"key": "nonconventional", "emoji": "☢️"},
    "איום כימי ביולוגי רדיולוגי": {"key": "cbrne", "emoji": "☣️"},
    "ניתן לצאת ממרחב מוגן": {"key": "all_clear", "emoji": "✅"},
    "האירוע הסתיים": {"key": "incident_resolved", "emoji": "🔵"},
    "התרעה מוקדמת": {"key": "early_warning", "emoji": "🟠"},
    "הודעה זריזה": {"key": "update", "emoji": "ℹ️"},
}


def _format_migun(seconds: int | None) -> str:
    """Format migun time like the official HFC channel.

    - ``None`` or ``0`` → "מיידי"
    - < 60s → "X שניות"
    - 60s   → "דקה"
    - 90s   → "דקה וחצי"
    - 120s  → "2 דקות"
    - 180s  → "3 דקות"
    """
    if not seconds:
        return "מיידי"
    if seconds < 60:
        return f"{seconds} שניות"
    if seconds == 60:
        return "דקה"
    if seconds == 90:
        return "דקה וחצי"
    m = seconds // 60
    remainder = seconds % 60
    if remainder == 0:
        return f"{m} דקות"
    if remainder == 30:
        return f"{m} וחצי דקות"
    return f"{m} דקות"


class HfcAlertService:
    """Direct Oref poller — single-source HFC alert service."""

    ALERT_URL = "https://www.oref.org.il/WarningMessages/alert/alerts.json"
    HEADERS = {
        "Referer": "https://www.oref.org.il/",
        "X-Requested-With": "XMLHttpRequest",
        "User-Agent": "Mozilla/5.0 (compatible; OrelliusMonitor/1.0)",
        "Accept": "application/json",
        "Accept-Language": "he-IL,he;q=0.9",
    }

    # Adaptive polling constants
    _BASE_INTERVAL = 0.5    # 500ms default
    _ACTIVE_INTERVAL = 0.3  # 300ms during alert waves
    _ACTIVE_WINDOW = 60.0   # seconds after last alert to stay in active mode
    _JITTER_MS = 50         # +/-50ms random offset

    def __init__(
        self,
        ws_manager: Any,
        poll_interval: float = 0.5,
        dedup_ttl: int = 300,
        zone_filter: set[str] | None = None,
    ):
        self._ws_manager = ws_manager
        self._poll_interval = poll_interval
        self._dedup_ttl = dedup_ttl
        self._zone_filter = zone_filter

        self._running = False
        self._poll_task: asyncio.Task | None = None
        self._http_client: httpx.AsyncClient | None = None
        self._seen_ids: dict[str, float] = {}
        self._seen_ttl = dedup_ttl
        self._consecutive_errors = 0
        self._geo_blocked = False
        self._last_poll: float | None = None
        self._alert_count = 0
        self._start_time: float | None = None

        # Adaptive mode: track when last alert was seen
        self._active_alert_until: float = 0

        # Health tracking: rolling avg of last 20 poll response times
        self._poll_times: deque[float] = deque(maxlen=20)
        self._polls_total = 0

        # Wave coalescing state — merge rapid-fire alerts into one message
        self._wave_msg_id: int | None = None
        self._wave_zones: dict[str, dict] = {}
        self._wave_cities: list[str] = []
        self._wave_category: str | None = None
        self._wave_time: float = 0
        self._wave_alert: dict[str, Any] | None = None
        self._wave_feed_id: str | None = None

    # ── Lifecycle ─────────────────────────────────────────────

    def start(self) -> None:
        """Launch the Oref direct poller."""
        if self._running:
            return
        self._running = True
        self._consecutive_errors = 0
        self._start_time = time.time()
        self._poll_task = asyncio.create_task(self._poll_loop())
        # Pre-warm geo/zone data so first alert has zero cold-start penalty
        asyncio.create_task(self._prewarm())
        logger.info("HFC alert service started (direct Oref poller, %.0fms interval)", self._poll_interval * 1000)

    async def _prewarm(self) -> None:
        """Pre-load zone DB and geo data in background so first alert is instant."""
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._prewarm_sync)
        except Exception as e:
            logger.warning(f"HFC prewarm failed (non-fatal): {e}")

    @staticmethod
    def _prewarm_sync() -> None:
        from app.services.hfc_zones import _load_zones_db, _fetch_remote_cities
        from app.services.hfc_map_generator import _load_geo_data, prewarm_tiles
        _load_zones_db()
        _fetch_remote_cities()
        _load_geo_data()
        logger.info("HFC: geo/zone data pre-warmed")
        # Pre-download Israel map tiles (zoom 10-14) to disk cache
        prewarm_tiles()

    async def stop(self) -> None:
        """Cancel the poller and close the persistent HTTP client."""
        self._running = False
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        self._poll_task = None
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        logger.info("HFC alert service stopped")

    @property
    def _avg_response_ms(self) -> float:
        if not self._poll_times:
            return 0.0
        return sum(self._poll_times) / len(self._poll_times)

    @property
    def _poller_healthy(self) -> bool:
        """Healthy = running, recent successful poll, avg response < 2s."""
        if not self._running or self._last_poll is None:
            return False
        stale = (time.time() - self._last_poll) > 10
        return not stale and self._avg_response_ms < 2000

    @property
    def status(self) -> dict[str, Any]:
        return {
            "running": self._running,
            "geo_blocked": self._geo_blocked,
            "last_poll": self._last_poll,
            "alert_count": self._alert_count,
            "consecutive_errors": self._consecutive_errors,
            "poller_healthy": self._poller_healthy,
            "avg_response_ms": round(self._avg_response_ms, 1),
            "polls_total": self._polls_total,
        }

    # ── Poll loop ─────────────────────────────────────────────

    def _get_client(self) -> httpx.AsyncClient:
        """Lazy-init persistent httpx client with connection reuse."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=3,
                limits=httpx.Limits(max_connections=2, max_keepalive_connections=1),
                http2=False,
            )
        return self._http_client

    def _record_poll_time(self, ms: float) -> None:
        """Track rolling average of last 20 poll response times."""
        self._poll_times.append(ms)
        self._polls_total += 1

    def _current_interval(self) -> float:
        """Adaptive interval: faster during active alert waves."""
        now = time.time()
        if now < self._active_alert_until:
            base = self._ACTIVE_INTERVAL
        else:
            base = self._poll_interval
        # Add jitter: +/-50ms
        jitter = random.uniform(-self._JITTER_MS, self._JITTER_MS) / 1000
        return max(0.1, base + jitter)

    async def _poll_loop(self) -> None:
        """Main polling loop with adaptive interval and exponential backoff."""
        while self._running:
            try:
                t0 = time.monotonic()
                alerts = await self._fetch_alerts()
                elapsed_ms = (time.monotonic() - t0) * 1000
                self._record_poll_time(elapsed_ms)
                self._last_poll = time.time()
                self._consecutive_errors = 0
                self._geo_blocked = False

                if alerts:
                    new_alerts = self._deduplicate(alerts)
                    for raw in new_alerts:
                        alert = self._parse_alert(raw)
                        if alert:
                            self._active_alert_until = time.time() + self._ACTIVE_WINDOW
                            await self._process_alert(alert)

                await asyncio.sleep(self._current_interval())

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._consecutive_errors += 1
                backoff = min(self._poll_interval * (2**self._consecutive_errors), 30.0)
                logger.error(f"HFC poll error ({self._consecutive_errors}): {e}")

                if self._consecutive_errors >= 10:
                    logger.error("HFC: 10 consecutive errors — auto-stopping")
                    self._running = False
                    await self._ws_manager.broadcast(
                        {
                            "type": "hfc_status",
                            "running": False,
                            "error": f"Auto-stopped after 10 errors: {e}",
                        }
                    )
                    break

                await asyncio.sleep(backoff)

    # ── Fetch ─────────────────────────────────────────────────

    async def _fetch_alerts(self) -> list[dict]:
        """Fetch alerts from the HFC API using persistent connection."""
        client = self._get_client()
        resp = await client.get(self.ALERT_URL, headers=self.HEADERS)

        if resp.status_code == 403:
            self._geo_blocked = True
            await self._ws_manager.broadcast(
                {
                    "type": "hfc_status",
                    "running": True,
                    "geo_blocked": True,
                }
            )
            await asyncio.sleep(30)
            return []

        resp.raise_for_status()

        # HFC API returns UTF-8 BOM (\ufeff) + \r\n when no alerts — strip both
        text = resp.text.strip().lstrip("\ufeff").strip()
        if not text:
            return []

        try:
            data = _json.loads(text)
        except (_json.JSONDecodeError, ValueError):
            return []

        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return [data]
        return []

    # ── Dedup ─────────────────────────────────────────────────

    def _deduplicate(self, alerts: list[dict]) -> list[dict]:
        """Filter out already-seen alerts and evict expired entries."""
        now = time.time()

        # Evict expired IDs
        expired = [k for k, ts in self._seen_ids.items() if now - ts > self._seen_ttl]
        for k in expired:
            del self._seen_ids[k]

        new = []
        for alert in alerts:
            alert_id = alert.get("id") or alert.get("notificationId") or str(alert)
            alert_id = str(alert_id)
            if alert_id not in self._seen_ids:
                self._seen_ids[alert_id] = now
                new.append(alert)

        return new

    # ── Parse ─────────────────────────────────────────────────

    def _parse_alert(self, raw: dict) -> dict[str, Any] | None:
        """Normalize raw HFC JSON into a typed dict.

        Resolution priority for category:
        1. API ``title`` field → reverse-lookup in _TITLE_TO_CATEGORY (authoritative)
        2. ``cat`` field → HFC_CATEGORIES mapping (matrix_id)
        3. Fallback to generic "warning" category
        """
        try:
            from app.services.hfc_zones import group_cities_by_zone

            cat_id = str(raw.get("cat", "8"))
            cat_category = HFC_CATEGORIES.get(cat_id, HFC_CATEGORIES["8"])

            # API title is authoritative — use it to resolve the correct category
            raw_title = raw.get("title", "")
            title_category = _TITLE_TO_CATEGORY.get(raw_title) if raw_title else None

            if title_category:
                category_key = title_category["key"]
                emoji = title_category["emoji"]
                category_he = raw_title  # use API's own Hebrew name
            else:
                category_key = cat_category["key"]
                emoji = cat_category["emoji"]
                category_he = raw_title or cat_category["name_he"]

            cities = raw.get("data", [])
            if isinstance(cities, str):
                cities = [c.strip() for c in cities.split(",") if c.strip()]

            enriched_labels = raw.get("cities_labels")

            title = raw_title or category_he
            desc = raw.get("desc", "")
            # milesec can be 0 for border areas — don't use `or` which skips 0
            migun_raw = raw.get("milesec")
            if migun_raw is None:
                migun_raw = raw.get("migun_time")
            migun_time = int(migun_raw) if migun_raw is not None else None

            # Parse timestamp from raw alert (Unix epoch), fallback to now
            ts_raw = raw.get("timestamp")
            if ts_raw is not None:
                try:
                    ts = datetime.fromtimestamp(int(ts_raw))
                except (ValueError, TypeError, OSError):
                    ts = datetime.now()
            else:
                ts = datetime.now()

            return {
                "id": str(raw.get("id") or raw.get("notificationId", "")),
                "category_key": category_key,
                "category_he": category_he,
                "emoji": emoji,
                "title": title,
                "description": desc,
                "cities": cities,
                "grouped_cities": group_cities_by_zone(cities, enriched_labels),
                "migun_time": migun_time,
                "timestamp": ts.strftime("%H:%M:%S %d/%m/%Y"),
                "raw": raw,
            }
        except Exception as e:
            logger.warning(f"HFC: malformed alert skipped: {e}")
            return None

    # ── Process (with wave coalescing) ─────────────────────────

    def _format_from_wave(self, alert: dict[str, Any]) -> str:
        """Re-format the template using accumulated wave state."""
        from app.services.hfc_templates import apply_hfc_template

        grouped = self._wave_zones
        zones_block = self._build_zones_block(grouped)

        zone_miguns = [z["migun_time"] for z in grouped.values() if z.get("migun_time")]
        if zone_miguns:
            min_migun = min(zone_miguns)
            max_migun = max(zone_miguns)
        else:
            min_migun = alert["migun_time"]
            max_migun = alert["migun_time"]

        migun_display = _format_migun(min_migun)
        template_data = {
            "timestamp": alert["timestamp"],
            "zones_block": zones_block,
            "cities_list": ", ".join(self._wave_cities),
            "city_count": len(self._wave_cities),
            "min_migun_time": _format_migun(min_migun),
            "max_migun_time": _format_migun(max_migun),
            "migun_display": migun_display,
            "guidance": alert["description"],
            "alert_title": alert["title"],
            "category_he": alert["category_he"],
        }

        return apply_hfc_template(alert["category_key"], template_data)

    async def _process_alert(self, alert: dict[str, Any]) -> None:
        """Format, publish/edit on Telegram, and broadcast to frontend.

        Text-first architecture: publishes the alert text IMMEDIATELY, then
        generates the map image in the background and edits the message to add it.
        This keeps the critical path (text delivery) under 500ms.

        Coalesces rapid-fire alerts of the same category within 120s into a
        single Telegram message (edit) and a single frontend WS entry.
        """
        t_start = time.monotonic()
        now = time.time()
        same_wave = (
            self._wave_category == alert["category_key"]
            and (now - self._wave_time) < 120
            and self._wave_msg_id is not None
        )

        if same_wave:
            # Merge new zones into existing wave
            for zone, data in alert["grouped_cities"].items():
                if zone in self._wave_zones:
                    existing_cities = set(self._wave_zones[zone]["cities"])
                    for city in data["cities"]:
                        if city not in existing_cities:
                            self._wave_zones[zone]["cities"].append(city)
                else:
                    self._wave_zones[zone] = {
                        "cities": list(data["cities"]),
                        "migun_time": data.get("migun_time", 0),
                    }
            existing_set = set(self._wave_cities)
            for city in alert["cities"]:
                if city not in existing_set:
                    self._wave_cities.append(city)
            self._wave_time = now
            self._wave_alert = alert

            formatted = self._format_from_wave(alert)
            self._alert_count += 1

            # Edit existing Telegram message with updated TEXT immediately (no map wait)
            edited = False
            try:
                edited = await self._edit_telegram_message(self._wave_msg_id, formatted)
            except Exception as e:
                logger.error(f"HFC: Telegram edit failed: {e}")

            critical_ms = (time.monotonic() - t_start) * 1000
            logger.info(f"HFC: wave merge → Telegram edit in {critical_ms:.0f}ms (text-first)")

            # Broadcast updated entry with same feed ID
            await self._broadcast_to_feed(
                alert,
                formatted,
                edited,
                feed_id=self._wave_feed_id,
            )

            # Background: regenerate map with ALL accumulated cities, send as separate message
            asyncio.create_task(
                self._send_map_later(self._wave_cities[:], alert["category_key"])
            )
        else:
            # New wave — reset state
            self._wave_zones = {}
            for zone, data in alert["grouped_cities"].items():
                self._wave_zones[zone] = {
                    "cities": list(data["cities"]),
                    "migun_time": data.get("migun_time", 0),
                }
            self._wave_cities = list(alert["cities"])
            self._wave_category = alert["category_key"]
            self._wave_time = now
            self._wave_alert = alert
            self._wave_feed_id = f"hfc-{alert['id']}-{int(now)}"

            formatted = self._format_from_wave(alert)
            self._alert_count += 1

            # Publish TEXT immediately (no map) — critical path
            msg_id = None
            try:
                msg_id = await self._publish_to_telegram(formatted)
            except Exception as e:
                logger.error(f"HFC: Telegram publish failed: {e}")
            if msg_id is None:
                # Immediate retry — no sleep, civil defense alerts must go through
                try:
                    msg_id = await self._publish_to_telegram(formatted)
                    if msg_id:
                        logger.info("HFC: retry succeeded")
                except Exception as e:
                    logger.error(f"HFC: Telegram retry also failed: {e}")

            critical_ms = (time.monotonic() - t_start) * 1000
            logger.info(f"HFC: new alert → Telegram publish in {critical_ms:.0f}ms (text-first, map deferred)")
            self._wave_msg_id = msg_id

            # Broadcast to frontend feed
            await self._broadcast_to_feed(
                alert,
                formatted,
                msg_id is not None,
                feed_id=self._wave_feed_id,
            )

            # Background: generate map and send as separate message
            asyncio.create_task(
                self._send_map_later(self._wave_cities[:], alert["category_key"])
            )

    async def _send_map_later(self, cities: list[str], category_key: str) -> None:
        """Background task: generate map image, then send it as a separate message."""
        try:
            map_path = await self._generate_map(cities, category_key)
            if map_path:
                await self._publish_map_to_telegram(map_path)
                logger.info(f"HFC: map sent as separate message ({map_path.name})")
        except Exception as e:
            logger.warning(f"HFC: background map send failed (non-critical): {e}")

    async def _publish_map_to_telegram(self, image_path: Path) -> int | None:
        """Send a map image as a standalone photo message (no caption)."""
        if not settings.target_channel:
            return None
        try:
            from app.services.telegram_session import get_client, resolve_peer

            client = await get_client()
            target = resolve_peer(settings.target_channel)
            msg = await client.send_file(target, str(image_path))
            return msg.id
        except Exception as e:
            logger.error(f"HFC: failed to send map to Telegram: {e}")
            return None

    @staticmethod
    def _build_zones_block(grouped_cities: dict[str, dict]) -> str:
        """Build compact zones block — single line per zone with bullet.

        Format:  • <b>zone_name</b>: city1, city2 (migun_time)
        Compact layout fits more zones in Telegram's 4096-char limit.
        """
        if not grouped_cities:
            return ""
        lines = []
        for zone, info in grouped_cities.items():
            cities = info.get("cities", [])
            migun = info.get("migun_time")
            migun_str = f" ({_format_migun(migun)})" if migun is not None else ""
            lines.append(f"• <b>{zone}</b>: {', '.join(cities)}{migun_str}")
        return "\n".join(lines)

    _NO_MAP_CATEGORIES = {"incident_resolved", "update"}

    @staticmethod
    async def _generate_map(cities: list[str], category_key: str) -> Path | None:
        """Generate a map image for the given cities and alert category."""
        if category_key in HfcAlertService._NO_MAP_CATEGORIES:
            return None
        try:
            from app.services.hfc_map_generator import generate_alert_map
            return await generate_alert_map(cities, category_key)
        except Exception as e:
            logger.error(f"HFC: map generation failed: {e}")
            return None

    async def _publish_to_telegram(self, text: str, image_path: Path | None = None) -> int | None:
        """Send formatted alert to the target Telegram channel.

        If ``image_path`` is provided, sends as a photo with caption.
        Telegram captions are limited to 1024 chars — if exceeded, the image
        is sent first without caption, then the text follows as a separate message.

        Returns the Telegram message ID on success, None on failure.
        """
        if not settings.target_channel:
            return None

        try:
            from app.services.telegram_html import safe_parse_mode
            from app.services.telegram_session import get_client, resolve_peer

            client = await get_client()
            target = resolve_peer(settings.target_channel)

            if settings.channel_signature:
                text = f"{text}\n\n{settings.channel_signature}"

            parse_mode = safe_parse_mode(text)

            if image_path and image_path.exists():
                if len(text) <= 1024:
                    # Image + caption in one message
                    msg = await client.send_file(
                        target,
                        str(image_path),
                        caption=text,
                        parse_mode=parse_mode,
                    )
                else:
                    # Caption too long — send image first, then text separately
                    await client.send_file(
                        target,
                        str(image_path),
                    )
                    msg = await client.send_message(
                        target,
                        text,
                        parse_mode=parse_mode,
                    )
            else:
                msg = await client.send_message(
                    target,
                    text,
                    parse_mode=parse_mode,
                )
            return msg.id
        except Exception as e:
            logger.error(f"HFC: failed to send to Telegram: {e}")
            return None

    async def _edit_telegram_message(self, msg_id: int, text: str, image_path: Path | None = None) -> bool:
        """Edit an existing Telegram message with updated alert text and optional map."""
        if not settings.target_channel or not msg_id:
            return False

        try:
            from app.services.telegram_html import safe_parse_mode
            from app.services.telegram_session import get_client, resolve_peer

            client = await get_client()
            target = resolve_peer(settings.target_channel)

            if settings.channel_signature:
                text = f"{text}\n\n{settings.channel_signature}"

            parse_mode = safe_parse_mode(text)

            if image_path and image_path.exists():
                # Edit with new image + text
                await client.edit_message(
                    target,
                    msg_id,
                    text,
                    file=str(image_path),
                    parse_mode=parse_mode,
                )
            else:
                await client.edit_message(
                    target,
                    msg_id,
                    text,
                    parse_mode=parse_mode,
                )
            return True
        except Exception as e:
            logger.error(f"HFC: failed to edit Telegram message {msg_id}: {e}")
            return False

    async def _broadcast_to_feed(
        self,
        alert: dict[str, Any],
        formatted: str,
        published: bool,
        feed_id: str | None = None,
    ) -> None:
        """Broadcast the alert as a new_message event to the WS frontend.

        When ``feed_id`` is provided (wave coalescing), the frontend should
        upsert the entry so that repeated broadcasts with the same ID update
        the existing card instead of creating duplicates.
        """
        msg_id = feed_id or f"hfc-{alert['id']}-{int(time.time())}"
        # HFC alerts are auto-published (no human review) — status is never "reviewing"
        status = "published" if published else "publish_failed"
        await self._ws_manager.broadcast(
            {
                "type": "new_message",
                "message": {
                    "id": msg_id,
                    "sourceChannel": "pikud_haoref",
                    "originalText": formatted,
                    "translatedText": formatted,
                    "formattedOutput": formatted,
                    "status": status,
                    "timestamp": alert["timestamp"],
                    "contentType": "hfc_alert",
                    "hfcAlert": True,
                    "hfcAutoPublished": True,
                    "hfcCategory": alert["category_key"],
                    "title": f"{alert['emoji']} {alert['category_he']}",
                    "cities": self._wave_cities if feed_id else alert["cities"],
                },
            }
        )
