import asyncio
import json as _json
import logging
import os
import re
from contextlib import asynccontextmanager
from datetime import UTC
from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import text as sa_text

from app.config import settings
from app.errors import (
    AppError,
    AuthError,
    NotFoundError,
    TelegramNotConnectedError,
    ValidationError,
    register_error_handlers,
)
from app.middleware.auth import BearerAuthMiddleware, verify_ws_token
from app.middleware.logging import RequestIdMiddleware
from app.schemas import (
    AddChannelRequest,
    AddReplacementRequest,
    AddWatermarkRefRequest,
    ApplyTemplateRequest,
    ApproveMessageRequest,
    BulkMessageRequest,
    CreateTemplateRequest,
    DeleteWatermarkRefRequest,
    DiscoverChannelsRequest,
    ProfileChannelRequest,
    ReorderTemplatesRequest,
    ScrapeChannelRequest,
    TaxonomyItemRequest,
    Telegram2FARequest,
    TelegramCodeRequest,
    TelegramConnectRequest,
    TelegramTestSendRequest,
    UpdateHfcTemplateRequest,
    UpdateKeywordsRequest,
    UpdateReplacementRequest,
    UpdateSettingsRequest,
    UpdateSourceTrustRequest,
    UpdateTaxonomyItemRequest,
    UpdateTemplateRequest,
)
from app.ws_server import ConnectionManager

logger = logging.getLogger(__name__)

manager = ConnectionManager()

# ── Persistent runtime state (channels, etc.) ────────────────────
_STATE_FILE = Path(__file__).resolve().parent.parent / "data" / "runtime_state.json"


def _load_runtime_state() -> dict:
    """Load persisted runtime state from disk."""
    if _STATE_FILE.exists():
        try:
            return _json.loads(_STATE_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_runtime_state(state: dict) -> None:
    """Save runtime state to disk."""
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _STATE_FILE.write_text(_json.dumps(state, indent=2))


def _restore_channels_from_state():
    """Restore source/target channels from saved state into settings."""
    state = _load_runtime_state()
    saved_channels = state.get("source_channels", "")
    saved_target = state.get("target_channel", "")
    if saved_channels and not settings.source_channels:
        settings.source_channels = saved_channels
    if saved_target and not settings.target_channel:
        settings.target_channel = saved_target


def _persist_channels():
    """Save current channel config to runtime state file."""
    state = _load_runtime_state()
    state["source_channels"] = settings.source_channels
    state["target_channel"] = settings.target_channel
    _save_runtime_state(state)


# ── Settings keys that should persist across backend restarts ──
_PERSISTABLE_SETTINGS = [
    "publish_delay_seconds",
    "auto_publish",
    "stamp_enabled",
    "stamp_image_path",
    "stamp_opacity",
    "stamp_size_pct",
    "stamp_position",
    "watermark_removal_enabled",
    "watermark_confidence_threshold",
    "geo_enrichment_enabled",
    "ghost_mode_enabled",
    "suppress_read_receipts",
    "suppress_online_status",
    "keyword_filter_enabled",
    "dedup_enabled",
    "priority_keywords",
    "channel_signature",
    "fact_check_enabled",
]


def _persist_settings():
    """Save all user-facing settings to runtime state."""
    state = _load_runtime_state()
    saved = {}
    for key in _PERSISTABLE_SETTINGS:
        if hasattr(settings, key):
            saved[key] = getattr(settings, key)
    state["user_settings"] = saved
    _save_runtime_state(state)


def _restore_settings_from_state():
    """Restore user-facing settings from saved state on startup."""
    state = _load_runtime_state()
    saved = state.get("user_settings", {})
    for key, value in saved.items():
        if hasattr(settings, key):
            try:
                setattr(settings, key, value)
            except Exception:
                pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    import logging as _logging

    from app.agents.daemon import SystemDaemon
    from app.orchestrator.graph import set_ws_manager
    from app.services.log_buffer import LogBuffer, WebSocketLogHandler

    # ── Configure structured logging ────────────────────────
    log_buffer = LogBuffer(max_entries=2000)
    ws_log_handler = WebSocketLogHandler(log_buffer, ws_manager=manager)
    ws_log_handler.setLevel(_logging.DEBUG)

    # Console handler so pipeline logs are visible in the terminal
    console_handler = _logging.StreamHandler()
    console_handler.setLevel(_logging.INFO)
    console_handler.setFormatter(
        _logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s", datefmt="%H:%M:%S")
    )

    root_logger = _logging.getLogger("app")
    root_logger.addHandler(ws_log_handler)
    root_logger.addHandler(console_handler)
    root_logger.setLevel(_logging.DEBUG)

    app.state.log_buffer = log_buffer

    # ── Core state ──────────────────────────────────────────
    app.state.ws_manager = manager
    app.state.pipeline_running = False
    app.state.pipeline_router = None
    app.state.scraper = None
    app.state.hfc_service = None

    # Restore saved channel config + user settings before auto-resume
    _restore_channels_from_state()
    _restore_settings_from_state()

    # Wire ws_manager into the graph's notify_review node
    set_ws_manager(manager)

    # ── Start system daemon ─────────────────────────────────
    daemon = SystemDaemon(manager)
    app.state.daemon = daemon
    daemon_task = asyncio.create_task(daemon.start())

    # ── Auto-reconnect Telegram + auto-start pipeline ─────
    asyncio.create_task(_auto_resume(app))

    # ── Auto-resume HFC independently (not gated on pipeline) ──
    asyncio.create_task(_auto_resume_hfc(app))

    yield

    # ── Shutdown ────────────────────────────────────────────
    if app.state.hfc_service:
        await app.state.hfc_service.stop()
    await daemon.stop()
    daemon_task.cancel()
    if app.state.scraper:
        await app.state.scraper.stop()
    root_logger.removeHandler(ws_log_handler)
    await manager.shutdown()


async def _auto_resume(app: FastAPI):
    """Try to restore last session: reconnect Telegram and restart the pipeline."""
    import logging as _log

    _logger = _log.getLogger("app.auto_resume")

    await asyncio.sleep(1)

    try:
        from app.services.telegram_session import connect

        _logger.info("Auto-resume: attempting Telegram reconnect...")
        result = await connect()
        status = result.get("status", "")

        if status == "connected":
            _logger.info(f"Auto-resume: Telegram connected as {result.get('user', {}).get('first_name', '?')}")
            await manager.broadcast({"type": "telegram_status", **result})
        else:
            _logger.info(f"Auto-resume: Telegram not auto-connectable (status={status}), skipping pipeline")
            return

        channels = settings.source_channels_list
        if not channels:
            _logger.info("Auto-resume: no source channels configured, skipping pipeline start")
            return

        if app.state.pipeline_running:
            _logger.info("Auto-resume: pipeline already running")
            return

        _logger.info(f"Auto-resume: starting pipeline with {len(channels)} source channel(s)")

        from app.agents.ingestion import TelegramScraper
        from app.orchestrator.router import PipelineRouter
        from app.services.telegram_session import get_client

        router = PipelineRouter(manager, daemon=getattr(app.state, "daemon", None))
        app.state.pipeline_router = router

        scraper = TelegramScraper(on_message=router.process_message)
        app.state.scraper = scraper

        client = await get_client()
        await scraper.start(client, channels)

        app.state.pipeline_running = True
        await manager.broadcast({"type": "pipeline_status", "running": True})
        _logger.info("Auto-resume: pipeline started successfully")

    except Exception as e:
        import traceback

        _log.getLogger("app.auto_resume").error(f"Auto-resume failed: {e}\n{traceback.format_exc()}")


async def _auto_resume_hfc(app: FastAPI):
    """Independent HFC auto-resume — not gated on channel pipeline."""
    import logging as _log

    _logger = _log.getLogger("app.auto_resume_hfc")

    await asyncio.sleep(2)

    state = _load_runtime_state()
    if not state.get("hfc_enabled"):
        return

    try:
        from app.services.telegram_session import connect, get_status

        status_info = await get_status()
        if status_info.get("status") != "connected":
            _logger.info("Auto-resume HFC: Telegram not connected, attempting reconnect...")
            result = await connect()
            if result.get("status") != "connected":
                _logger.warning("Auto-resume HFC: Telegram not connectable, HFC skipped")
                return

        from app.services.hfc_alerts import HfcAlertService

        zone_filter_raw = state.get("hfc_zone_filter")
        zone_filter = set(zone_filter_raw) if zone_filter_raw else None
        hfc = HfcAlertService(
            ws_manager=manager,
            poll_interval=settings.hfc_poll_interval,
            dedup_ttl=settings.hfc_dedup_ttl,
            zone_filter=zone_filter,
        )
        hfc.start()
        app.state.hfc_service = hfc
        _logger.info("Auto-resume HFC: alert service started (independent of pipeline)")
    except Exception as e:
        import traceback

        _logger.warning(f"Auto-resume HFC failed: {e}\n{traceback.format_exc()}")


app = FastAPI(
    title="Orellius Backend",
    version="0.1.0",
    lifespan=lifespan,
)

# ── Rate limiting ────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
app.state.limiter = limiter

# Default state — lifespan overrides these with real values at startup
app.state.pipeline_running = False
app.state.pipeline_router = None
app.state.scraper = None
app.state.hfc_service = None
app.state.ws_manager = None
app.state.log_buffer = None
app.state.daemon = None
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Register error handlers ──────────────────────────────────
register_error_handlers(app)

# ── Sentry (optional) ────────────────────────────────────────
if getattr(settings, "sentry_dsn", ""):
    try:
        import sentry_sdk

        sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.1)
    except Exception:
        pass

# ── Auth middleware ───────────────────────────────────────────
app.add_middleware(BearerAuthMiddleware)

# ── Request ID middleware ─────────────────────────────────────
app.add_middleware(RequestIdMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:1420", "tauri://localhost", "https://tauri.localhost"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

# Serve downloaded/stamped media files
_media_dir = Path(settings.media_dir)
_media_dir.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(_media_dir)), name="media")


# ── Root-level endpoints (unversioned) ────────────────────────


@app.get("/api/health")
async def health():
    """Enhanced health check with service connectivity."""
    services = {}
    overall = "ok"

    # Check PostgreSQL
    try:
        from app.db.session import engine

        async with engine.connect() as conn:
            await conn.execute(sa_text("SELECT 1"))
        services["postgres"] = "ok"
    except Exception:
        services["postgres"] = "down"
        overall = "degraded"

    # Check Redis
    try:
        from app.redis_client import get_redis

        r = await get_redis()
        await r.ping()
        services["redis"] = "ok"
    except Exception:
        services["redis"] = "down"
        overall = "degraded"

    # Check Ollama
    try:
        import httpx

        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            services["ollama"] = "ok" if resp.status_code == 200 else "down"
    except Exception:
        services["ollama"] = "down"

    return {"status": overall, "version": "0.1.0", "services": services}


# ── V1 API Router ────────────────────────────────────────────

v1 = APIRouter(prefix="/api/v1")


# ── Auth ──────────────────────────────────────────────────────


@v1.post("/auth/register")
async def auth_register(request: Request):
    """Register a new user + organization."""
    from sqlalchemy import select

    from app.auth.jwt import create_access_token, create_refresh_token, hash_password
    from app.db.models import Organization, User
    from app.db.session import async_session

    body = await request.json()
    email = body.get("email", "").strip().lower()
    password = body.get("password", "")
    org_name = body.get("org_name", "").strip()

    if not email or not password:
        raise ValidationError("email and password are required")
    if len(password) < 8:
        raise ValidationError("Password must be at least 8 characters")

    async with async_session() as session:
        existing = await session.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none():
            raise ValidationError("Email already registered", code="email_taken")

        org = Organization(name=org_name or email.split("@")[0])
        session.add(org)
        await session.flush()

        user = User(
            email=email,
            hashed_password=hash_password(password),
            org_id=org.id,
            role="admin",
        )
        session.add(user)
        await session.commit()

        token_data = {"sub": str(user.id), "email": email, "org_id": org.id, "role": "admin"}
        return {
            "ok": True,
            "access_token": create_access_token(token_data),
            "refresh_token": create_refresh_token(token_data),
            "user": {"id": user.id, "email": email, "role": "admin", "org_id": org.id},
        }


@v1.post("/auth/login")
async def auth_login(request: Request):
    """Login with email + password, returns JWT tokens."""
    from datetime import datetime

    from sqlalchemy import select

    from app.auth.jwt import create_access_token, create_refresh_token, verify_password
    from app.db.models import User
    from app.db.session import async_session

    body = await request.json()
    email = body.get("email", "").strip().lower()
    password = body.get("password", "")

    async with async_session() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if not user or not verify_password(password, user.hashed_password):
            raise AuthError("Invalid email or password")

        user.last_login = datetime.now(UTC)
        await session.commit()

        token_data = {
            "sub": str(user.id),
            "email": user.email,
            "org_id": user.org_id,
            "role": user.role,
            "is_superadmin": user.is_superadmin,
        }
        return {
            "ok": True,
            "access_token": create_access_token(token_data),
            "refresh_token": create_refresh_token(token_data),
            "user": {
                "id": user.id,
                "email": user.email,
                "role": user.role,
                "org_id": user.org_id,
            },
        }


@v1.post("/auth/refresh")
async def auth_refresh(request: Request):
    """Refresh access token using a refresh token."""
    from app.auth.jwt import create_access_token, decode_token

    body = await request.json()
    refresh_token = body.get("refresh_token", "")

    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise AuthError("Invalid refresh token")

    token_data = {k: v for k, v in payload.items() if k not in ("exp", "type", "iat")}
    return {
        "ok": True,
        "access_token": create_access_token(token_data),
    }


@v1.get("/auth/me")
async def auth_me(request: Request):
    """Get current user info from JWT."""
    from app.auth.deps import get_current_user

    user = await get_current_user(request)
    if not user:
        raise AuthError()
    return {"ok": True, "user": user}


# ── Pipeline ──────────────────────────────────────────────────


@v1.post("/pipeline/start")
@limiter.limit("10/minute")
async def start_pipeline(request: Request):
    """Start the ingestion pipeline: wire scraper → router → LangGraph."""
    from app.agents.ingestion import TelegramScraper
    from app.orchestrator.router import PipelineRouter
    from app.services.telegram_session import get_client, get_status

    if app.state.pipeline_running and app.state.scraper:
        return {"ok": True, "message": "Pipeline already running"}

    # Stop any lingering scraper from a previous run (e.g., hot-reload left it orphaned)
    if app.state.scraper:
        try:
            await app.state.scraper.stop()
        except Exception:
            pass
        app.state.scraper = None

    status = await get_status()
    if not status.get("connected"):
        raise TelegramNotConnectedError()

    channels = settings.source_channels_list
    if not channels:
        raise ValidationError("No source channels configured.")

    try:
        router = PipelineRouter(manager, daemon=getattr(app.state, "daemon", None))
        app.state.pipeline_router = router

        scraper = TelegramScraper(on_message=router.process_message)
        app.state.scraper = scraper

        client = await get_client()
        await scraper.start(client, channels)
    except Exception as e:
        import logging

        logging.getLogger(__name__).error(f"Pipeline start failed: {e}", exc_info=True)
        app.state.pipeline_router = None
        app.state.scraper = None
        raise AppError(message=f"Pipeline start failed: {e}", code="pipeline_error") from e

    app.state.pipeline_running = True
    await manager.broadcast({"type": "pipeline_status", "running": True})
    return {"ok": True}


@v1.post("/pipeline/stop")
async def stop_pipeline():
    """Stop the ingestion pipeline and free model RAM."""
    if app.state.scraper:
        await app.state.scraper.stop()
        app.state.scraper = None
    app.state.pipeline_router = None
    app.state.pipeline_running = False

    from app.services.ollama_manager import ollama_manager

    await ollama_manager.unload_all()

    await manager.broadcast({"type": "pipeline_status", "running": False})
    return {"ok": True}


@v1.get("/pipeline/status")
async def pipeline_status():
    return {
        "running": app.state.pipeline_running,
        "agents": {},
        "queue_size": 0,
    }


# ── Channels ──────────────────────────────────────────────────


@v1.get("/channels")
async def list_channels():
    return {"channels": settings.source_channels_list}


@v1.post("/channels")
async def add_channel(body: AddChannelRequest):
    channel = body.channel.strip().lstrip("@")
    if not channel:
        return {"ok": False, "error": "Empty channel identifier"}
    current = settings.source_channels_list
    # Normalize comparison — case-insensitive, strip @
    current_lower = [c.lstrip("@").lower() for c in current]
    if channel.lower() not in current_lower:
        current.append(channel)
        settings.source_channels = ",".join(current)
        _persist_channels()
        logger.info(f"Channel added: {channel} (total: {len(current)})")
    return {"ok": True}


@v1.delete("/channels/{channel}")
async def remove_channel(channel: str):
    channel_norm = channel.strip().lstrip("@").lower()
    current = settings.source_channels_list
    # Remove by normalized match (handles @prefix and case differences)
    filtered = [c for c in current if c.lstrip("@").lower() != channel_norm]
    if len(filtered) < len(current):
        settings.source_channels = ",".join(filtered)
        _persist_channels()
        logger.info(f"Channel removed: {channel} (remaining: {len(filtered)})")
    return {"ok": True}


# ── Templates ─────────────────────────────────────────────────


@v1.get("/templates")
async def list_templates():
    from app.services.templates import get_all_templates

    return {"templates": get_all_templates()}


@v1.post("/templates")
async def create_template_endpoint(body: CreateTemplateRequest):
    from app.services.templates import create_template

    tpl = create_template(body.model_dump(exclude_unset=True))
    return {"ok": True, "template": tpl}


@v1.put("/templates/reorder")
async def reorder_templates_endpoint(body: ReorderTemplatesRequest):
    from app.services.templates import reorder_templates

    reorder_templates(body.ordered_ids)
    return {"ok": True}


@v1.put("/templates/{template_id}")
async def update_template_endpoint(template_id: str, body: UpdateTemplateRequest):
    from app.services.templates import update_template

    tpl = update_template(template_id, body.model_dump(exclude_unset=True))
    if not tpl:
        raise NotFoundError("Template not found")
    return {"ok": True, "template": tpl}


@v1.delete("/templates/{template_id}")
async def delete_template_endpoint(template_id: str):
    from app.services.templates import delete_template

    success = delete_template(template_id)
    return {"ok": success}


@v1.post("/templates/reset")
async def reset_templates_endpoint():
    from app.services.templates import reset_templates

    templates = reset_templates()
    return {"ok": True, "templates": templates}


# ── Taxonomies (Event Types & Threat Levels) ──────────────────


@v1.get("/event-types")
async def list_event_types():
    from app.services.taxonomies import get_event_types

    return {"event_types": get_event_types()}


@v1.post("/event-types")
async def create_event_type_endpoint(body: TaxonomyItemRequest):
    from app.services.taxonomies import create_event_type

    entry = create_event_type(body.model_dump())
    return {"ok": True, "event_type": entry}


@v1.put("/event-types/{key}")
async def update_event_type_endpoint(key: str, body: UpdateTaxonomyItemRequest):
    from app.services.taxonomies import update_event_type

    entry = update_event_type(key, body.model_dump(exclude_unset=True))
    if not entry:
        raise NotFoundError("Event type not found")
    return {"ok": True, "event_type": entry}


@v1.delete("/event-types/{key}")
async def delete_event_type_endpoint(key: str):
    from app.services.taxonomies import delete_event_type

    success = delete_event_type(key)
    return {"ok": success}


@v1.get("/threat-levels")
async def list_threat_levels():
    from app.services.taxonomies import get_threat_levels

    return {"threat_levels": get_threat_levels()}


@v1.post("/threat-levels")
async def create_threat_level_endpoint(body: TaxonomyItemRequest):
    from app.services.taxonomies import create_threat_level

    entry = create_threat_level(body.model_dump())
    return {"ok": True, "threat_level": entry}


@v1.put("/threat-levels/{key}")
async def update_threat_level_endpoint(key: str, body: UpdateTaxonomyItemRequest):
    from app.services.taxonomies import update_threat_level

    entry = update_threat_level(key, body.model_dump(exclude_unset=True))
    if not entry:
        raise NotFoundError("Threat level not found")
    return {"ok": True, "threat_level": entry}


@v1.delete("/threat-levels/{key}")
async def delete_threat_level_endpoint(key: str):
    from app.services.taxonomies import delete_threat_level

    success = delete_threat_level(key)
    return {"ok": success}


@v1.post("/taxonomies/reset")
async def reset_taxonomies_endpoint():
    from app.services.taxonomies import reset_taxonomies

    data = reset_taxonomies()
    return {"ok": True, **data}


# ── Phrase Replacements ───────────────────────────────────────


@v1.get("/replacements")
async def list_replacements():
    from app.services.phrase_replacements import get_all

    return {"replacements": get_all()}


@v1.post("/replacements")
async def add_replacement_endpoint(body: AddReplacementRequest):
    from app.services.phrase_replacements import add_replacement

    rule = add_replacement(body.find.strip(), body.replace.strip(), body.enabled)
    return {"ok": True, "replacement": rule}


@v1.put("/replacements/{index}")
async def update_replacement_endpoint(index: int, body: UpdateReplacementRequest):
    from app.services.phrase_replacements import update_replacement

    result = update_replacement(index, body.model_dump(exclude_unset=True))
    if result is None:
        raise NotFoundError("Invalid replacement index", code="replacement_not_found")
    return {"ok": True, "replacement": result}


@v1.delete("/replacements/{index}")
async def delete_replacement_endpoint(index: int):
    from app.services.phrase_replacements import delete_replacement

    return {"ok": delete_replacement(index)}


# ── Review ────────────────────────────────────────────────────


@v1.post("/review/{message_id}/apply-template")
async def apply_template_to_message(message_id: str, body: ApplyTemplateRequest):
    from app.services.templates import apply_template

    formatted = apply_template(
        template_id=body.template_id,
        translated_text=body.translated_text,
        facts=body.extracted_facts,
        tags=body.auto_tags,
        timestamp=body.timestamp,
        title=body.title,
        intel_status=body.intel_status,
    )

    await manager.broadcast(
        {
            "type": "message_update",
            "message_id": message_id,
            "updates": {
                "formattedOutput": formatted,
                "appliedTemplateId": body.template_id,
            },
        }
    )

    return {"ok": True, "formatted_output": formatted}


@v1.post("/review/{message_id}/acknowledge-disinfo")
async def acknowledge_disinfo(message_id: str):
    from app.orchestrator.graph import get_pending_state

    state = get_pending_state(message_id)
    if not state:
        raise NotFoundError("No pending state for this message")

    fact_check = state.get("fact_check")
    if not fact_check:
        raise ValidationError("No fact check data")

    fact_check["override_acknowledged"] = True
    state["fact_check"] = fact_check

    await manager.broadcast(
        {
            "type": "message_update",
            "message_id": message_id,
            "updates": {"factCheck": fact_check},
        }
    )

    return {"ok": True}


@v1.post("/review/{message_id}/approve")
async def approve_message(message_id: str, body: ApproveMessageRequest):
    """Approve a message — runs media processing + publisher with stored pipeline state."""
    import logging as _log

    from app.agents.media_handler import process_media_node
    from app.agents.publisher import publish_node
    from app.orchestrator.graph import await_pre_stamp, get_pending_state, remove_pending_state

    _logger = _log.getLogger(__name__)

    state = get_pending_state(message_id)
    if not state:
        _logger.warning(f"[{message_id}] No pending state — cannot publish")
        raise NotFoundError("No pending pipeline state found for this message")

    # Disinformation safety gate
    fact_check = state.get("fact_check")
    if fact_check and fact_check.get("flagged") and not fact_check.get("override_acknowledged"):
        raise ValidationError("Disinformation not acknowledged", code="disinfo_not_acknowledged")

    # Apply human edits
    state["approved"] = True
    if body.edited_text:
        state["formatted_output"] = body.edited_text
        state["human_edited"] = True

    # Filter media to only include items the operator kept
    # None = don't filter (include all), [] = user explicitly excluded everything,
    # [...] = user selected specific items
    if body.included_media is not None and len(body.included_media) > 0:
        included_set = set(body.included_media)
        state["media_items"] = [
            m for m in state.get("media_items", []) if os.path.basename(m.get("local_path", "")) in included_set
        ]
    elif body.included_media is not None and len(body.included_media) == 0 and state.get("media_items"):
        # Empty array but state has media — likely a frontend sync issue, keep all media
        _logger.warning(f"[{message_id}] included_media is empty but state has {len(state['media_items'])} media items — keeping all")

    # Return Reviewer to idle
    await manager.broadcast(
        {
            "type": "agent_status",
            "agent": "Reviewer",
            "status": "idle",
            "activity": "Approved by operator",
        }
    )

    try:
        # ── Media processing (use pre-stamped result if available) ──
        await manager.broadcast(
            {
                "type": "message_update",
                "message_id": message_id,
                "updates": {"status": "processing_media"},
            }
        )
        await manager.broadcast(
            {
                "type": "agent_status",
                "agent": "Media Handler",
                "status": "running",
                "activity": f"Processing {message_id[:8]}...",
            }
        )

        pre_stamped = await await_pre_stamp(message_id)
        if pre_stamped and pre_stamped.get("media_processed"):
            if body.included_media is not None:
                kept_file_ids = {m["file_id"] for m in state.get("media_items", [])}
                pre_stamped["media_items"] = [
                    m for m in pre_stamped.get("media_items", []) if m.get("file_id") in kept_file_ids
                ]
            state["media_items"] = pre_stamped["media_items"]
            state["media_processed"] = True
            _logger.info(f"[{message_id}] Using pre-stamped media (saved processing time)")
        else:
            state = await process_media_node(state)

        stamped_urls = [
            os.path.basename(m.get("stamped_path") or m.get("local_path", ""))
            for m in state.get("media_items", [])
            if m.get("stamped_path") or m.get("local_path")
        ]
        await manager.broadcast(
            {
                "type": "message_update",
                "message_id": message_id,
                "updates": {"mediaUrls": stamped_urls},
            }
        )

        await manager.broadcast(
            {
                "type": "agent_status",
                "agent": "Media Handler",
                "status": "idle",
                "activity": "Done",
            }
        )

        # ── Publishing ──
        await manager.broadcast(
            {
                "type": "message_update",
                "message_id": message_id,
                "updates": {"status": "publishing"},
            }
        )
        await manager.broadcast(
            {
                "type": "agent_status",
                "agent": "Publisher",
                "status": "running",
                "activity": f"Publishing {message_id[:8]}...",
            }
        )

        state = await publish_node(state)

        if state.get("published"):
            await manager.broadcast(
                {
                    "type": "message_update",
                    "message_id": message_id,
                    "updates": {"status": "published"},
                }
            )
            await manager.broadcast(
                {
                    "type": "agent_status",
                    "agent": "Publisher",
                    "status": "idle",
                    "activity": "Published successfully",
                    "messagesProcessed": 1,
                }
            )
        else:
            error = state.get("publish_error", "Unknown error")
            _logger.error(f"[{message_id}] Publish failed: {error}")
            await manager.broadcast(
                {
                    "type": "message_update",
                    "message_id": message_id,
                    "updates": {"status": "failed"},
                }
            )
            await manager.broadcast(
                {
                    "type": "agent_status",
                    "agent": "Publisher",
                    "status": "error",
                    "activity": error[:120],
                }
            )

    except Exception as e:
        _logger.error(f"[{message_id}] Post-approval processing failed: {e}", exc_info=True)
        await manager.broadcast(
            {
                "type": "message_update",
                "message_id": message_id,
                "updates": {"status": "failed"},
            }
        )
        remove_pending_state(message_id)
        raise AppError(message=str(e), code="approval_error") from e
    finally:
        remove_pending_state(message_id)

    if state.get("published"):
        return {"ok": True}
    else:
        raise AppError(message=state.get("publish_error", "Publishing failed"), code="publish_error")


@v1.post("/review/{message_id}/reject")
async def reject_message(message_id: str):
    from app.orchestrator.graph import remove_pending_state

    remove_pending_state(message_id)

    await manager.broadcast(
        {
            "type": "message_update",
            "message_id": message_id,
            "updates": {"status": "failed"},
        }
    )
    await manager.broadcast(
        {
            "type": "agent_status",
            "agent": "Reviewer",
            "status": "idle",
            "activity": "Rejected by operator",
        }
    )
    return {"ok": True}


@v1.post("/review/{message_id}/archive")
async def archive_message(message_id: str):
    from app.orchestrator.graph import remove_pending_state

    remove_pending_state(message_id)

    await manager.broadcast(
        {
            "type": "message_update",
            "message_id": message_id,
            "updates": {"status": "archived"},
        }
    )
    return {"ok": True}


@v1.post("/review/{message_id}/restore")
async def restore_message(message_id: str):
    await manager.broadcast(
        {
            "type": "message_update",
            "message_id": message_id,
            "updates": {"status": "failed"},
        }
    )
    return {"ok": True}


@v1.delete("/review/{message_id}")
async def delete_message(message_id: str):
    from app.orchestrator.graph import remove_pending_state

    remove_pending_state(message_id)

    await manager.broadcast(
        {
            "type": "message_delete",
            "message_id": message_id,
        }
    )
    return {"ok": True}


_ALL_AGENT_NAMES = ["Ingestion", "Analyst", "Reviewer", "Media Handler", "Publisher", "System Daemon"]


async def _reset_all_agents(reason: str) -> None:
    for agent_name in _ALL_AGENT_NAMES:
        await manager.broadcast(
            {
                "type": "agent_status",
                "agent": agent_name,
                "status": "idle",
                "activity": reason,
            }
        )


@v1.post("/review/bulk/archive")
async def bulk_archive(body: BulkMessageRequest):
    from app.orchestrator.graph import remove_pending_state

    for mid in body.message_ids:
        remove_pending_state(mid)
        await manager.broadcast(
            {
                "type": "message_update",
                "message_id": mid,
                "updates": {"status": "archived"},
            }
        )

    await _reset_all_agents("Bulk archive — queue cleared")
    return {"ok": True, "count": len(body.message_ids)}


@v1.post("/review/bulk/delete")
async def bulk_delete(body: BulkMessageRequest):
    from app.orchestrator.graph import remove_pending_state

    for mid in body.message_ids:
        remove_pending_state(mid)
        await manager.broadcast(
            {
                "type": "message_delete",
                "message_id": mid,
            }
        )

    await _reset_all_agents("Bulk delete — queue cleared")
    return {"ok": True, "count": len(body.message_ids)}


# ── Logs ──────────────────────────────────────────────────────


@v1.get("/logs")
async def get_logs(limit: int = 200, level: str | None = None):
    log_buffer = getattr(app.state, "log_buffer", None)
    if not log_buffer:
        return {"entries": []}
    return {"entries": log_buffer.get_entries(limit=limit, level=level)}


@v1.delete("/logs")
async def clear_logs():
    log_buffer = getattr(app.state, "log_buffer", None)
    if log_buffer:
        log_buffer.clear()
    return {"ok": True}


# ── Settings ──────────────────────────────────────────────────


@v1.get("/settings")
async def get_settings():
    return {
        "publish_delay": settings.publish_delay_seconds,
        "auto_publish": settings.auto_publish,
        "stamp_enabled": settings.stamp_enabled,
        "stamp_image_path": settings.stamp_image_path,
        "stamp_opacity": settings.stamp_opacity,
        "stamp_size_pct": settings.stamp_size_pct,
        "stamp_position": settings.stamp_position,
        "target_channel": settings.target_channel,
        "watermark_removal_enabled": settings.watermark_removal_enabled,
        "watermark_confidence_threshold": settings.watermark_confidence_threshold,
        "geo_enrichment_enabled": getattr(settings, "geo_enrichment_enabled", True),
        "ghost_mode_enabled": settings.ghost_mode_enabled,
        "suppress_read_receipts": settings.suppress_read_receipts,
        "suppress_online_status": settings.suppress_online_status,
        "keyword_filter_enabled": settings.keyword_filter_enabled,
        "dedup_enabled": settings.dedup_enabled,
        "priority_keywords": settings.priority_keywords,
        "channel_signature": settings.channel_signature,
        "fact_check_enabled": settings.fact_check_enabled,
    }


@v1.put("/settings")
async def update_settings(body: UpdateSettingsRequest):
    data = body.model_dump(exclude_unset=True)

    if "publish_delay" in data:
        settings.publish_delay_seconds = data["publish_delay"]
    if "auto_publish" in data:
        settings.auto_publish = data["auto_publish"]
    if "stamp_enabled" in data:
        settings.stamp_enabled = data["stamp_enabled"]
    if "stamp_image_path" in data:
        settings.stamp_image_path = data["stamp_image_path"]
    if "stamp_opacity" in data:
        settings.stamp_opacity = data["stamp_opacity"]
    if "stamp_size_pct" in data:
        settings.stamp_size_pct = data["stamp_size_pct"]
    if "stamp_position" in data:
        allowed = {"center", "bottom-right", "bottom-left", "top-right", "top-left"}
        pos = data["stamp_position"]
        if pos in allowed:
            settings.stamp_position = pos
    if "target_channel" in data:
        settings.target_channel = data["target_channel"]
        _persist_channels()
    if "watermark_removal_enabled" in data:
        settings.watermark_removal_enabled = data["watermark_removal_enabled"]
    if "watermark_confidence_threshold" in data:
        settings.watermark_confidence_threshold = data["watermark_confidence_threshold"]
    if "geo_enrichment_enabled" in data:
        settings.geo_enrichment_enabled = data["geo_enrichment_enabled"]
    if "ghost_mode_enabled" in data:
        settings.ghost_mode_enabled = data["ghost_mode_enabled"]
    if "suppress_read_receipts" in data:
        settings.suppress_read_receipts = data["suppress_read_receipts"]
    if "suppress_online_status" in data:
        settings.suppress_online_status = data["suppress_online_status"]
    if "keyword_filter_enabled" in data:
        settings.keyword_filter_enabled = data["keyword_filter_enabled"]
    if "dedup_enabled" in data:
        settings.dedup_enabled = data["dedup_enabled"]
    if "priority_keywords" in data:
        settings.priority_keywords = data["priority_keywords"]
    if "channel_signature" in data:
        settings.channel_signature = data["channel_signature"]
    if "fact_check_enabled" in data:
        settings.fact_check_enabled = data["fact_check_enabled"]

    _persist_settings()
    return {"ok": True}


# ── Watermark Reference Management ────────────────────────────


@v1.post("/watermark/add-reference")
async def add_watermark_reference(body: AddWatermarkRefRequest):
    import base64

    from app.services.watermark_manager import reload_templates

    channel = re.sub(r"[^a-zA-Z0-9_\-.]", "", body.channel.strip()) or "global"
    if not body.image:
        raise ValidationError("image (base64) is required")

    ref_dir = Path(settings.watermark_ref_dir)
    if not ref_dir.is_absolute():
        ref_dir = Path.cwd() / ref_dir

    channel_dir = ref_dir / channel
    channel_dir.mkdir(parents=True, exist_ok=True)

    safe_name = "".join(c for c in body.filename if c.isalnum() or c in "._-")
    if not safe_name:
        safe_name = "ref.png"
    if not safe_name.lower().endswith((".png", ".jpg", ".jpeg")):
        safe_name += ".png"

    out_path = channel_dir / safe_name
    try:
        img_bytes = base64.b64decode(body.image)
        out_path.write_bytes(img_bytes)
    except Exception as e:
        raise ValidationError(f"Failed to decode/save image: {e}") from e

    reload_templates()
    return {"ok": True, "path": str(out_path), "channel": channel, "filename": safe_name}


@v1.get("/watermark/references")
async def list_watermark_references():
    ref_dir = Path(settings.watermark_ref_dir)
    if not ref_dir.is_absolute():
        ref_dir = Path.cwd() / ref_dir

    refs: list[dict] = []
    if ref_dir.exists():
        for subdir in sorted(ref_dir.iterdir()):
            if not subdir.is_dir():
                continue
            channel = subdir.name
            for img_path in sorted(subdir.iterdir()):
                if img_path.suffix.lower() in (".png", ".jpg", ".jpeg"):
                    refs.append(
                        {
                            "channel": channel,
                            "filename": img_path.name,
                            "path": str(img_path),
                        }
                    )

    return {"references": refs}


@v1.delete("/watermark/reference")
async def delete_watermark_reference(body: DeleteWatermarkRefRequest):
    from app.services.watermark_manager import reload_templates

    channel = re.sub(r"[^a-zA-Z0-9_\-.]", "", body.channel)
    filename = re.sub(r"[^a-zA-Z0-9_\-.]", "", body.filename)

    ref_dir = Path(settings.watermark_ref_dir)
    if not ref_dir.is_absolute():
        ref_dir = Path.cwd() / ref_dir

    target = (ref_dir / channel / filename).resolve()
    if not str(target).startswith(str(ref_dir.resolve())):
        raise HTTPException(status_code=400, detail="Invalid path")

    if target.exists():
        target.unlink()
        reload_templates()
        return {"ok": True}

    raise NotFoundError("Reference not found")


# ── Source Trust ──────────────────────────────────────────────


@v1.get("/source-trust")
async def list_source_trust():
    from app.services.source_trust import list_all_trust

    entries = await list_all_trust()
    return {"entries": entries}


@v1.get("/source-trust/{channel_id:path}")
async def get_source_trust(channel_id: str):
    from app.services.source_trust import get_channel_trust

    info = await get_channel_trust(channel_id)
    return {"trust": info}


@v1.put("/source-trust/{channel_id:path}")
async def update_source_trust(channel_id: str, body: UpdateSourceTrustRequest):
    from app.services.source_trust import set_channel_trust

    result = await set_channel_trust(channel_id, body.trust_level)
    if result is None:
        raise ValidationError("Invalid trust level")
    return {"ok": True, "trust": result}


# ── Situations ────────────────────────────────────────────────


@v1.get("/situations/active")
async def get_active_situations():

    from app.redis_client import get_redis

    try:
        r = await get_redis()
        situations = []
        cursor = 0
        seen_regions = set()
        while True:
            cursor, keys = await r.scan(cursor, match="geo:events:*", count=100)
            for key in keys:
                parts = key.split(":")
                if len(parts) >= 4:
                    region = parts[2]
                    event_type = parts[3]
                    region_key = f"{region}:{event_type}"
                    if region_key in seen_regions:
                        continue
                    seen_regions.add(region_key)

                    import time

                    now = time.time()
                    window = 6 * 3600
                    count = await r.zcount(key, now - window, now)
                    if count >= 3:
                        situations.append(
                            {
                                "region": region,
                                "event_type": event_type,
                                "post_count": count,
                                "status": "DEVELOPING",
                            }
                        )

            if cursor == 0:
                break

        return {"situations": situations}
    except Exception as e:
        return {"situations": [], "error": str(e)}


# ── Ghost Mode ────────────────────────────────────────────────


@v1.post("/ghost/enable")
async def ghost_enable():
    from app.services.ghost_engine import GhostEngine
    from app.services.telegram_session import get_client, get_status

    status = await get_status()
    if not status.get("connected"):
        raise TelegramNotConnectedError()

    client = await get_client()
    ghost = GhostEngine.init(client)
    await ghost.enable()
    settings.ghost_mode_enabled = True
    return {"ok": True, "status": ghost.get_status()}


@v1.post("/ghost/disable")
async def ghost_disable():
    from app.services.ghost_engine import GhostEngine

    ghost = GhostEngine.get_instance()
    if ghost:
        await ghost.disable()
    settings.ghost_mode_enabled = False
    return {"ok": True}


@v1.get("/ghost/status")
async def ghost_status():
    from app.services.ghost_engine import GhostEngine

    ghost = GhostEngine.get_instance()
    if ghost:
        return ghost.get_status()
    return {"enabled": False}


# ── Channel Intelligence ──────────────────────────────────────


@v1.post("/channels/discover")
async def discover_channels_endpoint(body: DiscoverChannelsRequest):
    from app.services.channel_intel import discover_channels
    from app.services.telegram_session import get_client, get_status

    status = await get_status()
    if not status.get("connected"):
        raise TelegramNotConnectedError()

    client = await get_client()
    channels = await discover_channels(client, body.seed_channel, depth=body.depth)
    return {"ok": True, "channels": channels}


@v1.post("/channels/profile")
async def profile_channel_endpoint(body: ProfileChannelRequest):
    from app.services.channel_intel import profile_channel
    from app.services.telegram_session import get_client, get_status

    status = await get_status()
    if not status.get("connected"):
        raise TelegramNotConnectedError()

    client = await get_client()
    profile = await profile_channel(client, body.channel)
    return {"ok": True, "profile": profile}


@v1.post("/channels/scrape")
@limiter.limit("10/minute")
async def scrape_channel_endpoint(request: Request, body: ScrapeChannelRequest):
    from app.services.channel_intel import scrape_history
    from app.services.telegram_session import get_client, get_status

    status = await get_status()
    if not status.get("connected"):
        raise TelegramNotConnectedError()

    client = await get_client()
    messages = await scrape_history(client, body.channel, limit=body.limit)
    return {"ok": True, "messages": messages}


@v1.get("/channels/profiles")
async def get_channel_profiles():
    from app.services.channel_intel import get_cached_profiles

    return {"profiles": get_cached_profiles()}


# ── Pre-Processing / Keywords ─────────────────────────────────


@v1.get("/preprocess/keywords")
async def get_keywords():
    from app.services.preprocess import get_keywords as _get_kw

    return {"keywords": _get_kw(), "raw": settings.priority_keywords}


@v1.put("/preprocess/keywords")
async def update_keywords(body: UpdateKeywordsRequest):
    from app.services.preprocess import set_keywords

    set_keywords(body.keywords)
    return {"ok": True, "keywords": body.keywords}


# ── Raw Metadata ──────────────────────────────────────────────


@v1.get("/messages/{message_id}/raw")
async def get_raw_metadata(message_id: str):
    from app.orchestrator.graph import get_pending_state

    state = get_pending_state(message_id)
    if not state:
        raise NotFoundError("Message not found in pending reviews")

    return {
        "ok": True,
        "raw_metadata": state.get("raw_metadata"),
        "preprocess_meta": state.get("preprocess_meta"),
    }


@v1.get("/messages/{message_id}/enriched")
async def get_enriched_data(message_id: str):
    try:
        from app.orchestrator.graph import get_pending_state

        state = get_pending_state(message_id)
        if not state:
            raise NotFoundError("Message not found in pending reviews")

        media_urls = [
            os.path.basename(m.get("stamped_path") or m.get("local_path"))
            for m in state.get("media_items", [])
            if m.get("stamped_path") or m.get("local_path")
        ]

        return {
            "ok": True,
            "id": message_id,
            "sourceChannel": state.get("source_channel", ""),
            "originalText": state.get("original_text", ""),
            "translatedText": state.get("translated_text", ""),
            "mediaUrls": media_urls,
            "status": "reviewing",
            "timestamp": state.get("timestamp", ""),
            "contentType": state.get("content_type", "other"),
            "extractedFacts": state.get("extracted_facts", []),
            "autoTags": state.get("auto_tags"),
            "title": state.get("title", ""),
            "suggestedTemplateId": state.get("suggested_template_id", ""),
            "formattedOutput": state.get("formatted_output", ""),
            "reviewNotes": state.get("review_notes", ""),
            "geoContext": state.get("geo_context"),
            "sourceTrust": state.get("source_trust"),
            "relatedMessages": state.get("related_messages", []),
            "situationBrief": state.get("situation_brief", ""),
            "rawMetadata": state.get("raw_metadata"),
            "preprocessMeta": state.get("preprocess_meta"),
            "suggestedIntelStatus": state.get("suggested_intel_status", ""),
        }
    except AppError:
        raise
    except Exception as e:
        raise AppError(message=str(e), code="enriched_data_error") from e


# ── Telegram Connection ───────────────────────────────────────


@v1.post("/telegram/connect")
async def telegram_connect(body: TelegramConnectRequest | None = None):
    from app.services.telegram_session import connect

    phone = (body.phone if body else "") or ""
    result = await connect(phone=phone)
    await manager.broadcast({"type": "telegram_status", **result})
    return result


@v1.post("/telegram/code")
async def telegram_submit_code(body: TelegramCodeRequest):
    from app.services.telegram_session import submit_code

    result = await submit_code(body.code)
    await manager.broadcast({"type": "telegram_status", **result})
    return result


@v1.post("/telegram/2fa")
async def telegram_submit_2fa(body: Telegram2FARequest):
    from app.services.telegram_session import submit_2fa

    result = await submit_2fa(body.password)
    await manager.broadcast({"type": "telegram_status", **result})
    return result


@v1.post("/telegram/disconnect")
async def telegram_disconnect():
    from app.services.telegram_session import disconnect

    result = await disconnect()
    await manager.broadcast({"type": "telegram_status", **result})
    return result


@v1.get("/telegram/status")
async def telegram_status():
    from app.services.telegram_session import get_status

    return await get_status()


@v1.get("/telegram/channels")
async def telegram_list_channels():
    from app.services.telegram_session import list_channels

    channels = await list_channels()
    return {"channels": channels}


@v1.post("/telegram/test-send")
@limiter.limit("5/minute")
async def telegram_test_send(request: Request, body: TelegramTestSendRequest):
    from app.services.telegram_session import send_test_message

    result = await send_test_message(body.channel, body.text)
    return result


# ── HFC (Pikud HaOref) Alert Endpoints ────────────────────────


@v1.post("/hfc/start")
async def hfc_start():
    from app.services.hfc_alerts import HfcAlertService

    if app.state.hfc_service and app.state.hfc_service._running:
        return {"ok": True, "message": "HFC poller already running"}

    state = _load_runtime_state()
    zone_filter_raw = state.get("hfc_zone_filter")
    zone_filter = set(zone_filter_raw) if zone_filter_raw else None

    hfc = HfcAlertService(
        ws_manager=manager,
        poll_interval=settings.hfc_poll_interval,
        dedup_ttl=settings.hfc_dedup_ttl,
        zone_filter=zone_filter,
    )
    hfc.start()
    app.state.hfc_service = hfc

    state["hfc_enabled"] = True
    _save_runtime_state(state)

    await manager.broadcast({"type": "hfc_status", "running": True})
    return {"ok": True}


@v1.post("/hfc/stop")
async def hfc_stop():
    if app.state.hfc_service:
        await app.state.hfc_service.stop()
        app.state.hfc_service = None

    state = _load_runtime_state()
    state["hfc_enabled"] = False
    _save_runtime_state(state)

    await manager.broadcast({"type": "hfc_status", "running": False})
    return {"ok": True}


@v1.get("/hfc/status")
async def hfc_status():
    if app.state.hfc_service:
        return app.state.hfc_service.status
    return {
        "running": False,
        "geo_blocked": False,
        "last_poll": None,
        "alert_count": 0,
        "consecutive_errors": 0,
        "poller_healthy": False,
        "avg_response_ms": 0,
        "polls_total": 0,
    }


@v1.post("/hfc/test")
async def hfc_test():
    from app.services.hfc_alerts import HfcAlertService

    test_svc = HfcAlertService(ws_manager=manager)
    try:
        alerts = await test_svc._fetch_alerts()
        return {
            "ok": True,
            "connected": True,
            "alert_count": len(alerts),
            "geo_blocked": test_svc._geo_blocked,
            "sample": alerts[:3] if alerts else [],
        }
    except Exception as e:
        raise AppError(message=str(e), code="hfc_test_error") from e


_last_mock_msg_ids: list[int] = []


@v1.post("/hfc/test-mock")
@limiter.limit("5/minute")
async def hfc_test_mock(request: Request):
    import time as _time
    from datetime import datetime

    from app.services.hfc_alerts import HFC_CATEGORIES, HfcAlertService, _format_migun
    from app.services.hfc_templates import apply_hfc_template
    from app.services.hfc_zones import group_cities_by_zone
    from app.services.telegram_html import safe_parse_mode

    # Realistic regional clusters per category — real HFC alerts are localized
    _mock_clusters: dict[str, list[str]] = {
        "rockets": [
            "שדרות, איבים", "ניר עם", "נתיבות", "אופקים",
            "אשקלון - צפון", "אשקלון - דרום",
        ],
        "hostile_aircraft": [
            "חיפה - כרמל, הדר ועיר תחתית", "חיפה - מפרץ",
            "חיפה - מערב", "חיפה - קריית חיים ושמואל",
        ],
        "terror_infiltration": [
            "שדרות, איבים", "ניר עם", "נתיבות",
        ],
        "early_warning": [
            "שדרות, איבים", "ניר עם", "נתיבות", "אופקים",
            "אשקלון - צפון", "אשקלון - דרום",
        ],
        "earthquake": [
            "תל אביב - מרכז העיר", "תל אביב - דרום העיר ויפו",
            "בני ברק", "גבעתיים",
        ],
        "tsunami": [
            "תל אביב - מרכז העיר", "תל אביב - עבר הירקון",
            "חיפה - בת גלים ק.אליעזר",
        ],
        "hazardous_materials": [
            "חיפה - מפרץ", "חיפה - קריית חיים ושמואל",
        ],
        "cbrne": [
            "באר שבע - מזרח", "באר שבע - מערב",
            "באר שבע - דרום", "באר שבע - צפון",
        ],
        "nonconventional": [
            "תל אביב - מזרח", "תל אביב - מרכז העיר",
            "רמת גן - מערב",
        ],
    }
    # Default cluster for categories not in the map
    _default_cluster = [
        "תל אביב - מרכז העיר", "תל אביב - דרום העיר ויפו",
        "בני ברק", "גבעתיים",
    ]

    # Fire all real alert categories (skip drills — matrix_id < 100)
    real_categories = {
        mid: info for mid, info in HFC_CATEGORIES.items() if int(mid) < 100
    }
    real_categories["ew"] = {"key": "early_warning", "name_he": "התרעה מוקדמת", "emoji": "🟠"}

    # Use first cluster as the default for zone grouping display
    mock_cities = _mock_clusters.get("rockets", _default_cluster)
    grouped_cities = group_cities_by_zone(mock_cities)
    zone_miguns = [z["migun_time"] for z in grouped_cities.values() if z.get("migun_time")]
    min_migun = min(zone_miguns) if zone_miguns else 90
    max_migun = max(zone_miguns) if zone_miguns else 90
    migun_display = _format_migun(min_migun)
    zones_block = HfcAlertService._build_zones_block(grouped_cities)
    now_str = datetime.now().strftime("%H:%M:%S %d/%m/%Y")

    global _last_mock_msg_ids
    _last_mock_msg_ids = []

    results = []
    published_count = 0
    publish_errors = []

    for matrix_id, cat_info in real_categories.items():
        cat_key = cat_info["key"]
        cat_he = cat_info["name_he"]
        emoji = cat_info["emoji"]
        mock_id = f"mock-{cat_key}-{int(_time.time())}"

        # Use category-specific regional cluster
        cat_cities = _mock_clusters.get(cat_key, _default_cluster)
        cat_grouped = group_cities_by_zone(cat_cities)
        cat_zones_block = HfcAlertService._build_zones_block(cat_grouped)
        cat_zone_miguns = [z["migun_time"] for z in cat_grouped.values() if z.get("migun_time")]
        cat_min_migun = min(cat_zone_miguns) if cat_zone_miguns else 90

        template_data = {
            "timestamp": now_str,
            "zones_block": cat_zones_block,
            "cities_list": ", ".join(cat_cities),
            "city_count": len(cat_cities),
            "min_migun_time": _format_migun(cat_min_migun),
            "max_migun_time": _format_migun(max(cat_zone_miguns) if cat_zone_miguns else 90),
            "migun_display": _format_migun(cat_min_migun),
            "guidance": "היכנסו למרחב מוגן",
            "alert_title": cat_he,
            "category_he": cat_he,
        }

        formatted = apply_hfc_template(cat_key, template_data)

        # Generate map image for this alert category
        map_path = None
        try:
            from app.services.hfc_map_generator import generate_alert_map
            map_path = await generate_alert_map(cat_cities, cat_key)
        except Exception as e:
            publish_errors.append(f"{cat_key} map: {e}")

        # Publish to Telegram (with map if available)
        published = False
        if settings.target_channel:
            try:
                from app.services.telegram_session import get_client, resolve_peer

                client = await get_client()
                target = resolve_peer(settings.target_channel)
                text = formatted
                if settings.channel_signature:
                    text = f"{text}\n\n{settings.channel_signature}"
                parse_mode = safe_parse_mode(text)

                if map_path and map_path.exists():
                    if len(text) <= 1024:
                        msg = await client.send_file(
                            target,
                            str(map_path),
                            caption=text,
                            parse_mode=parse_mode,
                        )
                        _last_mock_msg_ids.append(msg.id)
                    else:
                        msg1 = await client.send_file(
                            target,
                            str(map_path),
                        )
                        msg2 = await client.send_message(
                            target,
                            text,
                            parse_mode=parse_mode,
                        )
                        _last_mock_msg_ids.extend([msg1.id, msg2.id])
                else:
                    msg = await client.send_message(
                        target,
                        text,
                        parse_mode=parse_mode,
                    )
                    _last_mock_msg_ids.append(msg.id)
                published = True
                published_count += 1
            except Exception as e:
                publish_errors.append(f"{cat_key}: {e}")

        # Broadcast to frontend feed
        await manager.broadcast(
            {
                "type": "new_message",
                "message": {
                    "id": mock_id,
                    "sourceChannel": "pikud_haoref",
                    "originalText": formatted,
                    "translatedText": formatted,
                    "formattedOutput": formatted,
                    "status": "published" if published else "reviewing",
                    "timestamp": int(_time.time()),
                    "contentType": "hfc_alert",
                    "hfcAlert": True,
                    "hfcCategory": cat_key,
                    "title": f"{emoji} {cat_he}",
                    "cities": mock_cities,
                    "mediaUrls": [],
                    "autoTags": None,
                    "extractedFacts": None,
                    "relatedMessages": [],
                    "situationBrief": "",
                },
            }
        )

        results.append({"category": cat_key, "name_he": cat_he, "published": published})

    return {
        "ok": True,
        "published": published_count > 0,
        "published_count": published_count,
        "total_categories": len(real_categories),
        "publish_errors": publish_errors or None,
        "results": results,
        "telegram_msg_ids": list(_last_mock_msg_ids),
    }


@v1.delete("/hfc/test-mock")
@limiter.limit("5/minute")
async def hfc_delete_mock(request: Request):
    global _last_mock_msg_ids

    if not _last_mock_msg_ids:
        return {"ok": True, "deleted_count": 0, "message": "No mock messages to delete"}

    try:
        from app.services.telegram_session import get_client, resolve_peer

        client = await get_client()
        await client.delete_messages(resolve_peer(settings.target_channel), _last_mock_msg_ids)
        deleted = len(_last_mock_msg_ids)
        _last_mock_msg_ids = []
        return {"ok": True, "deleted_count": deleted}
    except Exception as e:
        raise AppError(message=str(e), code="hfc_delete_mock_error") from e


@v1.post("/hfc/test-inject")
async def hfc_test_inject():
    """Inject a single mock alert into the live HFC service to test text-first latency."""
    import time as _time

    from app.services.hfc_zones import group_cities_by_zone

    hfc_svc = app.state.hfc_service
    if not hfc_svc:
        raise AppError(message="HFC service not running", code="hfc_not_running")

    cities = ["תל אביב - מרכז העיר", "בני ברק", "גבעתיים", "רמת גן"]
    alert = {
        "id": f"inject-{int(_time.time())}",
        "category_key": "rockets",
        "category_he": "ירי רקטות וטילים",
        "emoji": "🚀",
        "title": "ירי רקטות וטילים",
        "description": "היכנסו למרחב המוגן ושהו בו 10 דקות",
        "cities": cities,
        "grouped_cities": group_cities_by_zone(cities),
        "migun_time": 90,
        "timestamp": _time.strftime("%H:%M:%S %d/%m/%Y"),
        "raw": {},
    }

    t0 = _time.monotonic()
    await hfc_svc._process_alert(alert)
    elapsed_ms = (_time.monotonic() - t0) * 1000

    return {"ok": True, "critical_path_ms": round(elapsed_ms, 1)}


@v1.get("/hfc/templates")
async def hfc_templates_list():
    from app.services.hfc_templates import get_all_hfc_templates

    return {"templates": get_all_hfc_templates()}


@v1.put("/hfc/templates/{category}")
async def hfc_template_update(category: str, body: UpdateHfcTemplateRequest):
    from app.services.hfc_templates import update_hfc_template

    result = update_hfc_template(category, body.model_dump())
    if result is None:
        raise NotFoundError("HFC template category not found")
    return {"ok": True, "template": result}


# ── Ollama / LLM Status ──────────────────────────────────────


@v1.get("/ollama/status")
async def ollama_status():
    from app.services.ollama_manager import ollama_manager

    return await ollama_manager.health_check()


@v1.get("/ollama/models")
async def ollama_models():
    import httpx

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get("http://localhost:11434/api/tags")
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        raise AppError(message=str(e), code="ollama_error") from e


# ── Billing ───────────────────────────────────────────────────


@v1.get("/billing/subscription")
async def billing_subscription(request: Request):
    """Get current subscription info."""
    from app.auth.deps import get_current_user
    from app.services.billing import get_subscription

    user = await get_current_user(request)
    if not user or not user.get("org_id"):
        return {"ok": True, "subscription": None}

    sub = await get_subscription(user["org_id"])
    return {"ok": True, "subscription": sub}


@v1.post("/billing/checkout")
async def billing_checkout(request: Request):
    """Create a Stripe checkout session."""
    from app.auth.deps import get_current_user
    from app.services.billing import create_checkout_session

    user = await get_current_user(request)
    if not user or not user.get("org_id"):
        raise AuthError()

    body = await request.json()
    plan = body.get("plan", "pro")
    success_url = body.get("success_url", "http://localhost:1420/settings?billing=success")
    cancel_url = body.get("cancel_url", "http://localhost:1420/settings?billing=cancel")

    url = await create_checkout_session(user["org_id"], plan, success_url, cancel_url)
    if not url:
        raise AppError(message="Could not create checkout session", code="billing_error")

    return {"ok": True, "checkout_url": url}


@v1.post("/billing/webhook")
async def billing_webhook(request: Request):
    """Stripe webhook handler."""
    from app.services.billing import handle_stripe_webhook

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    success = await handle_stripe_webhook(payload, sig_header)
    return {"ok": success}


# ── Audit Log ─────────────────────────────────────────────────


@v1.get("/audit")
async def get_audit_logs(
    request: Request,
    action: str | None = None,
    resource_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    """Query audit logs."""
    from app.auth.deps import get_current_user
    from app.services.audit import query_audit_logs

    user = await get_current_user(request)
    org_id = user.get("org_id") if user else None

    logs = await query_audit_logs(
        org_id=org_id,
        action=action,
        resource_type=resource_type,
        limit=min(limit, 200),
        offset=offset,
    )
    return {"ok": True, "entries": logs, "count": len(logs)}


@v1.get("/audit/export")
async def export_audit_logs(request: Request):
    """Export audit logs as CSV."""
    from fastapi.responses import PlainTextResponse

    from app.auth.deps import get_current_user
    from app.services.audit import export_audit_csv

    user = await get_current_user(request)
    org_id = user.get("org_id") if user else None

    if org_id is None:
        raise AuthError()

    csv_data = await export_audit_csv(org_id)
    return PlainTextResponse(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_log.csv"},
    )


# ── Webhooks ──────────────────────────────────────────────────


@v1.get("/webhooks")
async def list_webhooks_endpoint(request: Request):
    """List webhooks for the current organization."""
    from app.auth.deps import get_current_user
    from app.services.webhooks import list_webhooks

    user = await get_current_user(request)
    org_id = user.get("org_id") if user else None
    if org_id is None:
        return {"ok": True, "webhooks": []}

    webhooks = await list_webhooks(org_id)
    return {"ok": True, "webhooks": webhooks}


@v1.post("/webhooks")
async def create_webhook_endpoint(request: Request):
    """Create a new webhook."""
    from app.auth.deps import get_current_user
    from app.services.webhooks import create_webhook

    user = await get_current_user(request)
    org_id = user.get("org_id") if user else None
    if org_id is None:
        raise AuthError()

    body = await request.json()
    url = body.get("url", "")
    events = body.get("events", [])

    if not url:
        raise ValidationError("url is required")

    wh = await create_webhook(org_id, url, events)
    return {"ok": True, "webhook": wh}


@v1.delete("/webhooks/{webhook_id}")
async def delete_webhook_endpoint(webhook_id: int, request: Request):
    """Delete a webhook."""
    from app.auth.deps import get_current_user
    from app.services.webhooks import delete_webhook

    user = await get_current_user(request)
    org_id = user.get("org_id") if user else None
    if org_id is None:
        raise AuthError()

    success = await delete_webhook(webhook_id, org_id)
    if not success:
        raise NotFoundError("Webhook not found")
    return {"ok": True}


# ── Jobs Status ───────────────────────────────────────────────


@v1.get("/jobs/{job_id}/status")
async def job_status(job_id: str):
    """Check status of a background job."""
    try:
        from app.workers.tasks import get_job_status as _get_status

        status = await _get_status(job_id)
        return {"ok": True, "job_id": job_id, **status}
    except Exception:
        return {"ok": True, "job_id": job_id, "status": "unknown"}


# ── Mount v1 router ───────────────────────────────────────────
app.include_router(v1)


# ── Backward-compatible /api/* routes → redirect to /api/v1/* ─
# Keep old /api/ paths working so the frontend transition is seamless.

compat = APIRouter(prefix="/api", deprecated=True)


@compat.post("/pipeline/start")
async def compat_start_pipeline(request: Request):
    return await start_pipeline(request)


@compat.post("/pipeline/stop")
async def compat_stop_pipeline():
    return await stop_pipeline()


@compat.get("/pipeline/status")
async def compat_pipeline_status():
    return await pipeline_status()


@compat.get("/channels")
async def compat_list_channels():
    return await list_channels()


@compat.post("/channels")
async def compat_add_channel(body: AddChannelRequest):
    return await add_channel(body)


@compat.delete("/channels/{channel}")
async def compat_remove_channel(channel: str):
    return await remove_channel(channel)


@compat.get("/templates")
async def compat_list_templates():
    return await list_templates()


@compat.post("/templates")
async def compat_create_template(body: CreateTemplateRequest):
    return await create_template_endpoint(body)


@compat.put("/templates/reorder")
async def compat_reorder_templates(body: ReorderTemplatesRequest):
    return await reorder_templates_endpoint(body)


@compat.put("/templates/{template_id}")
async def compat_update_template(template_id: str, body: UpdateTemplateRequest):
    return await update_template_endpoint(template_id, body)


@compat.delete("/templates/{template_id}")
async def compat_delete_template(template_id: str):
    return await delete_template_endpoint(template_id)


@compat.post("/templates/reset")
async def compat_reset_templates():
    return await reset_templates_endpoint()


@compat.get("/event-types")
async def compat_list_event_types():
    return await list_event_types()


@compat.post("/event-types")
async def compat_create_event_type(body: TaxonomyItemRequest):
    return await create_event_type_endpoint(body)


@compat.put("/event-types/{key}")
async def compat_update_event_type(key: str, body: UpdateTaxonomyItemRequest):
    return await update_event_type_endpoint(key, body)


@compat.delete("/event-types/{key}")
async def compat_delete_event_type(key: str):
    return await delete_event_type_endpoint(key)


@compat.get("/threat-levels")
async def compat_list_threat_levels():
    return await list_threat_levels()


@compat.post("/threat-levels")
async def compat_create_threat_level(body: TaxonomyItemRequest):
    return await create_threat_level_endpoint(body)


@compat.put("/threat-levels/{key}")
async def compat_update_threat_level(key: str, body: UpdateTaxonomyItemRequest):
    return await update_threat_level_endpoint(key, body)


@compat.delete("/threat-levels/{key}")
async def compat_delete_threat_level(key: str):
    return await delete_threat_level_endpoint(key)


@compat.post("/taxonomies/reset")
async def compat_reset_taxonomies():
    return await reset_taxonomies_endpoint()


@compat.get("/replacements")
async def compat_list_replacements():
    return await list_replacements()


@compat.post("/replacements")
async def compat_add_replacement(body: AddReplacementRequest):
    return await add_replacement_endpoint(body)


@compat.put("/replacements/{index}")
async def compat_update_replacement(index: int, body: UpdateReplacementRequest):
    return await update_replacement_endpoint(index, body)


@compat.delete("/replacements/{index}")
async def compat_delete_replacement(index: int):
    return await delete_replacement_endpoint(index)


@compat.post("/review/{message_id}/apply-template")
async def compat_apply_template(message_id: str, body: ApplyTemplateRequest):
    return await apply_template_to_message(message_id, body)


@compat.post("/review/{message_id}/acknowledge-disinfo")
async def compat_acknowledge_disinfo(message_id: str):
    return await acknowledge_disinfo(message_id)


@compat.post("/review/{message_id}/approve")
async def compat_approve_message(message_id: str, body: ApproveMessageRequest):
    return await approve_message(message_id, body)


@compat.post("/review/{message_id}/reject")
async def compat_reject_message(message_id: str):
    return await reject_message(message_id)


@compat.post("/review/{message_id}/archive")
async def compat_archive_message(message_id: str):
    return await archive_message(message_id)


@compat.post("/review/{message_id}/restore")
async def compat_restore_message(message_id: str):
    return await restore_message(message_id)


@compat.delete("/review/{message_id}")
async def compat_delete_message(message_id: str):
    return await delete_message(message_id)


@compat.post("/review/bulk/archive")
async def compat_bulk_archive(body: BulkMessageRequest):
    return await bulk_archive(body)


@compat.post("/review/bulk/delete")
async def compat_bulk_delete(body: BulkMessageRequest):
    return await bulk_delete(body)


@compat.get("/logs")
async def compat_get_logs(limit: int = 200, level: str | None = None):
    return await get_logs(limit, level)


@compat.delete("/logs")
async def compat_clear_logs():
    return await clear_logs()


@compat.get("/settings")
async def compat_get_settings():
    return await get_settings()


@compat.put("/settings")
async def compat_update_settings(body: UpdateSettingsRequest):
    return await update_settings(body)


@compat.post("/watermark/add-reference")
async def compat_add_watermark(body: AddWatermarkRefRequest):
    return await add_watermark_reference(body)


@compat.get("/watermark/references")
async def compat_list_watermark():
    return await list_watermark_references()


@compat.delete("/watermark/reference")
async def compat_delete_watermark(body: DeleteWatermarkRefRequest):
    return await delete_watermark_reference(body)


@compat.get("/source-trust")
async def compat_list_source_trust():
    return await list_source_trust()


@compat.get("/source-trust/{channel_id:path}")
async def compat_get_source_trust(channel_id: str):
    return await get_source_trust(channel_id)


@compat.put("/source-trust/{channel_id:path}")
async def compat_update_source_trust(channel_id: str, body: UpdateSourceTrustRequest):
    return await update_source_trust(channel_id, body)


@compat.get("/situations/active")
async def compat_get_situations():
    return await get_active_situations()


@compat.post("/ghost/enable")
async def compat_ghost_enable():
    return await ghost_enable()


@compat.post("/ghost/disable")
async def compat_ghost_disable():
    return await ghost_disable()


@compat.get("/ghost/status")
async def compat_ghost_status():
    return await ghost_status()


@compat.post("/channels/discover")
async def compat_discover_channels(body: DiscoverChannelsRequest):
    return await discover_channels_endpoint(body)


@compat.post("/channels/profile")
async def compat_profile_channel(body: ProfileChannelRequest):
    return await profile_channel_endpoint(body)


@compat.post("/channels/scrape")
async def compat_scrape_channel(request: Request, body: ScrapeChannelRequest):
    return await scrape_channel_endpoint(request, body)


@compat.get("/channels/profiles")
async def compat_channel_profiles():
    return await get_channel_profiles()


@compat.get("/preprocess/keywords")
async def compat_get_keywords():
    return await get_keywords()


@compat.put("/preprocess/keywords")
async def compat_update_keywords(body: UpdateKeywordsRequest):
    return await update_keywords(body)


@compat.get("/messages/{message_id}/raw")
async def compat_get_raw_metadata(message_id: str):
    return await get_raw_metadata(message_id)


@compat.get("/messages/{message_id}/enriched")
async def compat_get_enriched(message_id: str):
    return await get_enriched_data(message_id)


@compat.post("/telegram/connect")
async def compat_telegram_connect(body: TelegramConnectRequest | None = None):
    return await telegram_connect(body)


@compat.post("/telegram/code")
async def compat_telegram_code(body: TelegramCodeRequest):
    return await telegram_submit_code(body)


@compat.post("/telegram/2fa")
async def compat_telegram_2fa(body: Telegram2FARequest):
    return await telegram_submit_2fa(body)


@compat.post("/telegram/disconnect")
async def compat_telegram_disconnect():
    return await telegram_disconnect()


@compat.get("/telegram/status")
async def compat_telegram_status():
    return await telegram_status()


@compat.get("/telegram/channels")
async def compat_telegram_channels():
    return await telegram_list_channels()


@compat.post("/telegram/test-send")
async def compat_telegram_test_send(request: Request, body: TelegramTestSendRequest):
    return await telegram_test_send(request, body)


@compat.post("/hfc/start")
async def compat_hfc_start():
    return await hfc_start()


@compat.post("/hfc/stop")
async def compat_hfc_stop():
    return await hfc_stop()


@compat.get("/hfc/status")
async def compat_hfc_status():
    return await hfc_status()


@compat.post("/hfc/test")
async def compat_hfc_test():
    return await hfc_test()


@compat.post("/hfc/test-mock")
@limiter.limit("5/minute")
async def compat_hfc_test_mock(request: Request):
    return await hfc_test_mock(request)


@compat.get("/hfc/templates")
async def compat_hfc_templates():
    return await hfc_templates_list()


@compat.put("/hfc/templates/{category}")
async def compat_hfc_template_update(category: str, body: UpdateHfcTemplateRequest):
    return await hfc_template_update(category, body)


@compat.get("/ollama/status")
async def compat_ollama_status():
    return await ollama_status()


@compat.get("/ollama/models")
async def compat_ollama_models():
    return await ollama_models()


app.include_router(compat)


# ── WebSocket Endpoint ───────────────────────────────────────


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # Verify token for WebSocket connections
    if not verify_ws_token(websocket):
        await websocket.close(code=4001, reason="Invalid token")
        return

    await manager.connect(websocket)

    try:
        await manager.send_to(
            websocket,
            {
                "type": "pipeline_status",
                "running": app.state.pipeline_running,
            },
        )
        from app.services.telegram_session import get_status

        tg_status = await get_status()
        await manager.send_to(
            websocket,
            {
                "type": "telegram_status",
                **tg_status,
            },
        )

        # Send HFC status so frontend knows state immediately on connect
        hfc_svc = app.state.hfc_service
        if hfc_svc:
            await manager.send_to(websocket, {"type": "hfc_status", **hfc_svc.status})
        else:
            await manager.send_to(
                websocket,
                {"type": "hfc_status", "running": False, "geo_blocked": False, "poller_healthy": False},
            )
    except Exception:
        pass

    try:
        while True:
            data = await websocket.receive_json()
            await manager.handle_command(data, websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
