"""HFC Alert Map Generator — high-resolution map images with styled overlays.

Renders Google Maps tiles (Hebrew labels) at 3200x2400 via ``staticmap``,
composites supersampled pin markers with hand-drawn category icons, and
fills city boundary polygons from Pikud HaOref polygon data.

Zoom strategy:
  - Compute geographic span of all alerted cities
  - Pick zoom level that tightly frames the cluster on a phone screen
  - Small clusters (< 15km) → zoom 12-13, medium → 11, wide → 10, country → 9

Rendering modes:
  - **Early warning** → convex hull around all city boundaries (Tzofar-style)
  - **All others**    → individual city boundary fills + icon pin markers

No API keys, no headless browser.
"""

from __future__ import annotations

import asyncio
import hashlib
import json as _json
import logging
import math
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests as _requests
from PIL import Image, ImageDraw
from shapely.geometry import MultiPoint, Polygon as ShapelyPolygon
from staticmap import CircleMarker, StaticMap
from staticmap.staticmap import _lat_to_y, _lon_to_x

from app.config import settings

logger = logging.getLogger(__name__)

# ── Tile cache ────────────────────────────────────────────────────
# Disk-cached subclass of StaticMap — eliminates repeated HTTP tile downloads.
# After first fetch (or pre-warm), map rendering is purely local I/O + PIL.

_TILE_CACHE_DIR: Path | None = None
_TILE_URL_RE = re.compile(r"x=(\d+)&y=(\d+)&z=(\d+)")

# Israel bounding box for pre-warming
_IL_LAT_MIN, _IL_LAT_MAX = 29.4, 33.4
_IL_LNG_MIN, _IL_LNG_MAX = 34.1, 35.95
_PREWARM_ZOOMS = range(10, 15)  # zoom 10-14 covers most HFC alert maps


def _get_tile_cache_dir() -> Path:
    global _TILE_CACHE_DIR
    if _TILE_CACHE_DIR is None:
        _TILE_CACHE_DIR = Path(settings.media_dir) / "tile_cache"
        _TILE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return _TILE_CACHE_DIR


def _tile_cache_path(z: int, x: int, y: int) -> Path:
    d = _get_tile_cache_dir() / str(z) / str(x)
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{y}.png"


class CachedStaticMap(StaticMap):
    """StaticMap with disk-backed tile cache — zero network on cache hit."""

    def get(self, url, **kwargs):
        m = _TILE_URL_RE.search(url)
        if m:
            x, y, z = int(m.group(1)), int(m.group(2)), int(m.group(3))
            cached = _tile_cache_path(z, x, y)
            if cached.exists():
                return 200, cached.read_bytes()

        # Cache miss — fetch from network
        res = _requests.get(url, **kwargs)
        if res.status_code == 200 and m:
            x, y, z = int(m.group(1)), int(m.group(2)), int(m.group(3))
            p = _tile_cache_path(z, x, y)
            p.write_bytes(res.content)

        return res.status_code, res.content


def _lng_to_tile(lng: float, z: int) -> int:
    return int((lng + 180) / 360 * (1 << z))


def _lat_to_tile(lat: float, z: int) -> int:
    r = math.radians(lat)
    n = 1 << z
    return int((1 - math.log(math.tan(r) + 1 / math.cos(r)) / math.pi) / 2 * n)


def prewarm_tiles() -> None:
    """Download all Israel tiles at zoom 10-14 to disk cache.

    Called from HFC prewarm in a thread pool. Skips tiles already on disk.
    Typically ~5,300 tiles for zoom 10-14 covering all of Israel.
    """
    cache_dir = _get_tile_cache_dir()
    total = 0
    downloaded = 0
    skipped = 0

    for z in _PREWARM_ZOOMS:
        x_min = _lng_to_tile(_IL_LNG_MIN, z)
        x_max = _lng_to_tile(_IL_LNG_MAX, z)
        y_min = _lat_to_tile(_IL_LAT_MAX, z)  # note: lat/y are inverted
        y_max = _lat_to_tile(_IL_LAT_MIN, z)

        tiles = []
        for x in range(x_min, x_max + 1):
            for y in range(y_min, y_max + 1):
                total += 1
                cached = _tile_cache_path(z, x, y)
                if cached.exists():
                    skipped += 1
                    continue
                url = _TILE_URL.format(x=x, y=y, z=z)
                tiles.append((z, x, y, url))

        # Download missing tiles with thread pool
        if tiles:
            def _fetch_tile(args):
                z_, x_, y_, url_ = args
                try:
                    resp = _requests.get(url_, timeout=5,
                                         headers={"User-Agent": "OrelliusMap/1.0"})
                    if resp.status_code == 200:
                        p = _tile_cache_path(z_, x_, y_)
                        p.write_bytes(resp.content)
                        return True
                except Exception:
                    pass
                return False

            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(_fetch_tile, tiles))
                downloaded += sum(1 for r in results if r)

    logger.info("Tile cache: %d total, %d cached, %d downloaded, %d at zoom %d-%d",
                total, skipped, downloaded, total, _PREWARM_ZOOMS.start, _PREWARM_ZOOMS.stop - 1)

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_ASSETS_DIR = Path(__file__).resolve().parent.parent.parent / "assets"

_cities_geo: dict[str, dict] | None = None
_polygons: dict[str, list] | None = None

_STYLE: dict[str, dict] = {
    "rockets":              {"rgb": (220, 38, 38),  "dark": (153, 27, 27),  "icon": "rocket"},
    "hostile_aircraft":     {"rgb": (234, 128, 0),  "dark": (180, 83, 0),   "icon": "aircraft"},
    "terror_infiltration":  {"rgb": (234, 179, 8),  "dark": (161, 118, 0),  "icon": "warning"},
    "early_warning":        {"rgb": (220, 38, 38),  "dark": (153, 27, 27),  "icon": "warning"},
    "earthquake":           {"rgb": (120, 80, 60),  "dark": (87, 55, 38),   "icon": "quake"},
    "tsunami":              {"rgb": (30, 100, 190), "dark": (20, 66, 140),  "icon": "wave"},
    "hazardous_materials":  {"rgb": (126, 34, 166), "dark": (88, 22, 115),  "icon": "hazmat"},
    "cbrne":                {"rgb": (126, 34, 166), "dark": (88, 22, 115),  "icon": "radiation"},
    "nonconventional":      {"rgb": (126, 34, 166), "dark": (88, 22, 115),  "icon": "radiation"},
}
_DEFAULT = {"rgb": (220, 38, 38), "dark": (153, 27, 27), "icon": "dot"}

_HULL_CATEGORIES = {"early_warning"}
_TILE_URL = "https://mt1.google.com/vt/lyrs=m&hl=he&x={x}&y={y}&z={z}"
_W = 3200
_H = 2400

# Pin marker cache
_pin_cache: dict[tuple, Image.Image] = {}


# ── Data loading ──────────────────────────────────────────────────

def _load_geo_data() -> None:
    global _cities_geo, _polygons
    if _cities_geo is None:
        try:
            raw = _json.loads((_DATA_DIR / "hfc_cities_geo.json").read_text("utf-8"))
            _cities_geo = {
                c["name"]: {"id": str(c.get("id", "")), "lat": c["lat"], "lng": c["lng"],
                            "zone": c.get("zone", ""), "countdown": c.get("countdown", 0)}
                for c in raw if c.get("name") and c.get("lat") and c.get("lng")
            }
            logger.info("HFC geo: %d cities loaded", len(_cities_geo))
        except Exception as e:
            logger.error("HFC geo: cities failed — %s", e)
            _cities_geo = {}
    if _polygons is None:
        try:
            _polygons = _json.loads((_DATA_DIR / "hfc_polygons.json").read_text("utf-8"))
            logger.info("HFC geo: %d polygons loaded", len(_polygons))
        except Exception as e:
            logger.error("HFC geo: polygons failed — %s", e)
            _polygons = {}


# ── Smart zoom ────────────────────────────────────────────────────

def _compute_zoom(resolved: list[dict]) -> int:
    """Pick zoom level based on geographic span of the cluster."""
    lats = [c["lat"] for c in resolved]
    lngs = [c["lng"] for c in resolved]
    lat_span = max(lats) - min(lats)
    lng_span = max(lngs) - min(lngs)
    # Approximate degrees → km at Israel's latitude (~31.5°N)
    km_lat = lat_span * 111.0
    km_lng = lng_span * 111.0 * math.cos(math.radians(31.5))
    span_km = max(km_lat, km_lng, 0.5)

    # Zoom table tuned for 3200x2400 — aggressive zoom for mobile readability
    if span_km < 4:
        return 15
    elif span_km < 10:
        return 14
    elif span_km < 25:
        return 13
    elif span_km < 60:
        return 12
    elif span_km < 120:
        return 11
    else:
        return 10


def _to_px(lng: float, lat: float, zoom: int, xc: float, yc: float) -> tuple[int, int]:
    return (
        int((_lon_to_x(lng, zoom) - xc) * 256 + _W / 2),
        int((_lat_to_y(lat, zoom) - yc) * 256 + _H / 2),
    )


# ── Programmatic icon drawing ────────────────────────────────────

def _draw_icon(d: ImageDraw.ImageDraw, icon: str, cx: int, cy: int,
               r: int, color: tuple) -> None:
    """Draw a category icon inside the pin's white circle at supersampled coords."""
    if icon == "rocket":
        bw = int(r * 0.3)
        bh = int(r * 0.9)
        top = cy - bh // 2
        d.rounded_rectangle([cx - bw, top, cx + bw, top + bh],
                            radius=bw, fill=(*color, 220))
        d.polygon([(cx - bw, top + int(bh * 0.15)),
                   (cx, top - int(bh * 0.2)),
                   (cx + bw, top + int(bh * 0.15))], fill=(*color, 220))
        fw = int(r * 0.25)
        fb = top + bh
        d.polygon([(cx - bw, fb - int(bh * 0.25)), (cx - bw - fw, fb), (cx - bw, fb)],
                  fill=(*color, 180))
        d.polygon([(cx + bw, fb - int(bh * 0.25)), (cx + bw + fw, fb), (cx + bw, fb)],
                  fill=(*color, 180))

    elif icon == "aircraft":
        bw = int(r * 0.15)
        bh = int(r * 0.9)
        top = cy - bh // 2
        d.rounded_rectangle([cx - bw, top, cx + bw, top + bh],
                            radius=bw, fill=(*color, 220))
        d.polygon([(cx - bw, top + int(bh * 0.1)),
                   (cx, top - int(bh * 0.15)),
                   (cx + bw, top + int(bh * 0.1))], fill=(*color, 220))
        wspan = int(r * 0.85)
        wy = cy - int(r * 0.05)
        d.polygon([(cx, wy - int(r * 0.15)),
                   (cx - wspan, wy + int(r * 0.25)),
                   (cx, wy + int(r * 0.1))], fill=(*color, 200))
        d.polygon([(cx, wy - int(r * 0.15)),
                   (cx + wspan, wy + int(r * 0.25)),
                   (cx, wy + int(r * 0.1))], fill=(*color, 200))
        tw = int(r * 0.35)
        ty = top + bh
        d.polygon([(cx, ty - int(r * 0.3)), (cx - tw, ty), (cx, ty)],
                  fill=(*color, 180))
        d.polygon([(cx, ty - int(r * 0.3)), (cx + tw, ty), (cx, ty)],
                  fill=(*color, 180))

    elif icon == "warning":
        s = int(r * 0.9)
        d.polygon([(cx, cy - s), (cx - s, cy + int(s * 0.7)),
                   (cx + s, cy + int(s * 0.7))], fill=(*color, 220))
        si = int(s * 0.65)
        d.polygon([(cx, cy - int(si * 0.75)), (cx - si, cy + int(si * 0.55)),
                   (cx + si, cy + int(si * 0.55))], fill=(255, 255, 255, 200))
        ew = max(int(r * 0.15), 2)
        d.rectangle([cx - ew, cy - int(r * 0.35), cx + ew, cy + int(r * 0.15)],
                    fill=(*color, 240))
        d.ellipse([cx - ew - 1, cy + int(r * 0.25), cx + ew + 1, cy + int(r * 0.45)],
                  fill=(*color, 240))

    elif icon == "quake":
        w = int(r * 0.5)
        h = int(r * 0.9)
        top = cy - h
        pts = [
            (cx + int(w * 0.2), top),
            (cx - int(w * 0.3), cy - int(h * 0.1)),
            (cx + int(w * 0.15), cy - int(h * 0.05)),
            (cx - int(w * 0.2), cy + h),
            (cx + int(w * 0.3), cy + int(h * 0.1)),
            (cx - int(w * 0.15), cy + int(h * 0.05)),
        ]
        d.polygon(pts, fill=(*color, 220))

    elif icon == "wave":
        lw = max(int(r * 0.2), 3)
        for row_off in [-int(r * 0.4), 0, int(r * 0.4)]:
            y = cy + row_off
            d.arc([cx - r, y - int(r * 0.3), cx, y + int(r * 0.3)],
                  start=180, end=0, fill=(*color, 220), width=lw)
            d.arc([cx, y - int(r * 0.3), cx + r, y + int(r * 0.3)],
                  start=0, end=180, fill=(*color, 220), width=lw)

    elif icon == "hazmat":
        lr = int(r * 0.4)
        lw = max(int(r * 0.12), 2)
        for angle_deg in [90, 210, 330]:
            a = math.radians(angle_deg)
            lx = cx + int(lr * math.cos(a))
            ly = cy - int(lr * math.sin(a))
            d.ellipse([lx - lr, ly - lr, lx + lr, ly + lr],
                      outline=(*color, 220), width=lw)
        cr = int(r * 0.2)
        d.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=(*color, 220))

    elif icon == "radiation":
        ir_inner = int(r * 0.2)
        ir_outer = int(r * 0.8)
        for start_deg in [30, 150, 270]:
            d.pieslice([cx - ir_outer, cy - ir_outer, cx + ir_outer, cy + ir_outer],
                       start=start_deg, end=start_deg + 60, fill=(*color, 220))
        d.ellipse([cx - ir_inner - 2, cy - ir_inner - 2,
                   cx + ir_inner + 2, cy + ir_inner + 2], fill=(255, 255, 255, 230))
        cd = int(r * 0.12)
        d.ellipse([cx - cd, cy - cd, cx + cd, cy + cd], fill=(*color, 220))

    else:
        dr = int(r * 0.45)
        d.ellipse([cx - dr, cy - dr, cx + dr, cy + dr], fill=(*color, 200))


# ── Supersampled pin marker ──────────────────────────────────────

def _make_pin(rgb: tuple, dark: tuple, icon: str = "dot",
              pw: int = 80, ph: int = 104) -> Image.Image:
    """Render a Google Maps-style pin with drawn category icon via 4x supersampling."""
    cache_key = (rgb, dark, icon, pw, ph)
    if cache_key in _pin_cache:
        return _pin_cache[cache_key]

    scale = 4
    sw, sh = pw * scale, ph * scale
    img = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    cx = sw // 2
    r = int(sw * 0.42)
    cy_c = r + scale * 2
    tip_y = sh - scale * 4

    # Drop shadow
    so = scale * 2
    d.ellipse([cx + so - r - scale, cy_c + so - r - scale,
               cx + so + r + scale, cy_c + so + r + scale], fill=(0, 0, 0, 50))
    d.polygon([(cx + so - int(r * 0.55), cy_c + so + int(r * 0.5)),
               (cx + so + int(r * 0.55), cy_c + so + int(r * 0.5)),
               (cx + so, tip_y + so)], fill=(0, 0, 0, 40))

    # Teardrop tail
    d.polygon([(cx - int(r * 0.58), cy_c + int(r * 0.5)),
               (cx + int(r * 0.58), cy_c + int(r * 0.5)),
               (cx, tip_y)], fill=(*rgb, 255))

    # Circle with dark border
    bw = max(scale, 3)
    d.ellipse([cx - r - bw, cy_c - r - bw, cx + r + bw, cy_c + r + bw], fill=(*dark, 255))
    d.ellipse([cx - r, cy_c - r, cx + r, cy_c + r], fill=(*rgb, 255))

    # White inner circle
    ir = int(r * 0.58)
    d.ellipse([cx - ir, cy_c - ir, cx + ir, cy_c + ir], fill=(255, 255, 255, 245))

    # Category icon
    _draw_icon(d, icon, cx, cy_c, ir, dark)

    pin = img.resize((pw, ph), Image.LANCZOS)
    _pin_cache[cache_key] = pin
    return pin


# ── Polygon rendering ────────────────────────────────────────────

def _draw_geom(draw: ImageDraw.ImageDraw, geom, fill: tuple, border: tuple, bw: int,
               zoom: int, xc: float, yc: float) -> None:
    if not hasattr(geom, "exterior"):
        return
    px = [_to_px(lng, lat, zoom, xc, yc) for lng, lat in geom.exterior.coords]
    draw.polygon(px, fill=fill)
    ring = px + [px[0]]
    for step in range(bw, 0, -1):
        a = 255 if step <= bw // 2 else 200
        draw.line(ring, fill=(*border[:3], a), width=step, joint="curve")


def _draw_hull_zone(draw: ImageDraw.ImageDraw, resolved: list[dict], rgb: tuple, dark: tuple,
                    zoom: int, xc: float, yc: float) -> bool:
    """Convex hull wrapping all city polygon boundaries — Tzofar-style zone."""
    all_pts: list[tuple[float, float]] = []
    for city in resolved:
        coords = _polygons.get(city["id"]) if _polygons else None
        if coords:
            for p in coords:
                all_pts.append((p[1], p[0]))
        else:
            all_pts.append((city["lng"], city["lat"]))
    if len(all_pts) < 3:
        return False
    hull = MultiPoint(all_pts).convex_hull
    if hull.is_empty or not hasattr(hull, "exterior"):
        return False
    hull = hull.buffer(0.008).simplify(0.003)
    for g in (hull.geoms if hasattr(hull, "geoms") else [hull]):
        _draw_geom(draw, g, (*rgb, 120), (*dark, 255), 10, zoom, xc, yc)
    return True


def _draw_city_zones(overlay: Image.Image, draw: ImageDraw.ImageDraw, resolved: list[dict],
                     rgb: tuple, dark: tuple, icon: str,
                     zoom: int, xc: float, yc: float) -> None:
    """Individual city boundary fills + supersampled icon pin markers."""
    pin = _make_pin(rgb, dark, icon)

    if _polygons:
        for city in resolved:
            coords = _polygons.get(city["id"])
            if not coords or len(coords) < 3:
                continue
            try:
                ring = [(p[1], p[0]) for p in coords]
                poly = ShapelyPolygon(ring)
                if not poly.is_valid:
                    poly = poly.buffer(0)
                if poly.is_valid and not poly.is_empty:
                    for g in (poly.geoms if hasattr(poly, "geoms") else [poly]):
                        # Stronger fill + border for visibility
                        _draw_geom(draw, g, (*rgb, 90), (*dark, 220), 6, zoom, xc, yc)
            except Exception:
                pass

    for city in resolved:
        px, py = _to_px(city["lng"], city["lat"], zoom, xc, yc)
        overlay.paste(pin, (px - pin.width // 2, py - pin.height), pin)


# ── Watermark ─────────────────────────────────────────────────────

def _apply_watermark(img: Image.Image) -> Image.Image:
    stamp_path = _ASSETS_DIR / "stamps" / "watermark.png"
    if not stamp_path.exists():
        return img
    base = img.convert("RGBA")
    stamp = Image.open(stamp_path).convert("RGBA")
    sw = int(base.width * 0.18)
    sh = int(stamp.height * (sw / stamp.width))
    stamp = stamp.resize((sw, sh), Image.LANCZOS)
    r, g, b, a = stamp.split()
    a = a.point(lambda x: int(x * 0.7))
    stamp = Image.merge("RGBA", (r, g, b, a))
    base.paste(stamp, (int(base.width * 0.012), int(base.height * 0.012)), stamp)
    return base


# ── Entry point ───────────────────────────────────────────────────

def _generate_alert_map_sync(cities: list[str], category_key: str) -> Path | None:
    """Synchronous map generation — runs in thread pool to avoid blocking the event loop."""
    _load_geo_data()
    if not _cities_geo:
        return None

    # Deduplicate by name and ID
    seen: set[str] = set()
    unique_cities: list[str] = []
    for name in cities:
        if name not in seen:
            seen.add(name)
            unique_cities.append(name)

    resolved = []
    seen_ids: set[str] = set()
    for name in unique_cities:
        geo = _cities_geo.get(name)
        if geo and geo["id"] not in seen_ids:
            seen_ids.add(geo["id"])
            resolved.append({"name": name, **geo})
    if not resolved:
        logger.warning("HFC map: 0/%d cities resolved", len(cities))
        return None

    try:
        _t_render = time.monotonic()
        s = _STYLE.get(category_key, _DEFAULT)
        rgb, dark, icon = s["rgb"], s["dark"], s.get("icon", "dot")
        is_hull = category_key in _HULL_CATEGORIES

        # Smart zoom based on geographic span
        zoom = _compute_zoom(resolved)

        # Compute center from all points (including polygon vertices)
        all_lats: list[float] = []
        all_lngs: list[float] = []
        for city in resolved:
            all_lats.append(city["lat"])
            all_lngs.append(city["lng"])
            if _polygons:
                coords = _polygons.get(city["id"])
                if coords:
                    for pt in coords[:: max(1, len(coords) // 8)]:
                        all_lats.append(pt[0])
                        all_lngs.append(pt[1])

        center_lat = (min(all_lats) + max(all_lats)) / 2
        center_lng = (min(all_lngs) + max(all_lngs)) / 2

        # Use CachedStaticMap for disk-cached tile rendering
        m = CachedStaticMap(_W, _H, url_template=_TILE_URL, tile_size=256,
                            headers={"User-Agent": "OrelliusMap/1.0"})
        # Add a single invisible marker at center so render() works
        m.add_marker(CircleMarker((center_lng, center_lat), "#00000001", 1))

        base = m.render(zoom=zoom, center=[center_lng, center_lat])
        xc, yc = m.x_center, m.y_center

        overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        if is_hull:
            if not _draw_hull_zone(draw, resolved, rgb, dark, zoom, xc, yc):
                pin = _make_pin(rgb, dark, icon, pw=88, ph=114)
                for city in resolved:
                    px, py = _to_px(city["lng"], city["lat"], zoom, xc, yc)
                    overlay.paste(pin, (px - pin.width // 2, py - pin.height), pin)
        else:
            _draw_city_zones(overlay, draw, resolved, rgb, dark, icon, zoom, xc, yc)

        result = Image.alpha_composite(base.convert("RGBA"), overlay)
        result = _apply_watermark(result)

        out_dir = Path(settings.media_dir) / "hfc_maps"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{category_key}_{int(time.time())}.png"
        result.save(str(out_path), "PNG")

        render_ms = (time.monotonic() - _t_render) * 1000
        logger.info("HFC map: %s (%d/%d cities, zoom=%d) in %.0fms",
                     out_path.name, len(resolved), len(cities), zoom, render_ms)
        return out_path

    except Exception as e:
        logger.error("HFC map: render failed — %s", e)
        return None


async def generate_alert_map(cities: list[str], category_key: str) -> Path | None:
    """Async entry point — offloads sync tile download + PIL compositing to a thread."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _generate_alert_map_sync, cities, category_key)
