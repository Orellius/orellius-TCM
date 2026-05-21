"""Tests for API endpoints — auth, validation, basic CRUD."""

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.asyncio


# ── Health ─────────────────────────────────────────────────────


async def test_health_endpoint(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


async def test_health_no_auth_required(authed_client):
    """Health endpoint should work even without auth header."""
    # Remove the auth header
    authed_client.headers.pop("Authorization", None)
    resp = await authed_client.get("/api/health")
    assert resp.status_code == 200


# ── Auth ───────────────────────────────────────────────────────


async def test_auth_required_when_token_set():
    """When api_secret_token is set, requests without token should get 401."""
    from unittest.mock import MagicMock

    mock_manager = MagicMock()
    mock_manager.connect = AsyncMock()
    mock_manager.disconnect = MagicMock()
    mock_manager.broadcast = AsyncMock()
    mock_manager.send_to = AsyncMock()
    mock_manager.shutdown = AsyncMock()
    mock_manager.handle_command = AsyncMock()

    with (
        patch("app.main.manager", mock_manager),
        patch("app.main._restore_channels_from_state"),
        patch("app.main._restore_settings_from_state"),
        patch("app.main._auto_resume", new_callable=lambda: lambda *a: AsyncMock()()),
        patch("app.main._auto_resume_hfc", new_callable=lambda: lambda *a: AsyncMock()()),
        patch("app.orchestrator.graph.set_ws_manager"),
        patch("app.agents.daemon.SystemDaemon") as MockDaemon,
        patch("app.config.settings.api_secret_token", "secret123"),
    ):
        daemon_instance = MagicMock()
        daemon_instance.start = AsyncMock()
        daemon_instance.stop = AsyncMock()
        MockDaemon.return_value = daemon_instance

        from httpx import ASGITransport, AsyncClient

        from app.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # No token → 401
            resp = await ac.get("/api/v1/channels")
            assert resp.status_code == 401

            # Wrong token → 401
            resp = await ac.get(
                "/api/v1/channels",
                headers={"Authorization": "Bearer wrong"},
            )
            assert resp.status_code == 401

            # Correct token → 200
            resp = await ac.get(
                "/api/v1/channels",
                headers={"Authorization": "Bearer secret123"},
            )
            assert resp.status_code == 200


# ── Validation ─────────────────────────────────────────────────


async def test_add_channel_validation(client):
    """POST /api/v1/channels requires non-empty channel field."""
    resp = await client.post("/api/v1/channels", json={})
    assert resp.status_code == 422


async def test_add_channel_success(client):
    resp = await client.post("/api/v1/channels", json={"channel": "@test_channel"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


async def test_add_replacement_validation(client):
    """find field is required and must be non-empty."""
    resp = await client.post("/api/v1/replacements", json={"replace": "bar"})
    assert resp.status_code == 422


# ── Templates ──────────────────────────────────────────────────


async def test_list_templates(client):
    with patch("app.services.templates.get_all_templates", return_value=[]):
        resp = await client.get("/api/v1/templates")
        assert resp.status_code == 200
        assert "templates" in resp.json()


# ── Settings ───────────────────────────────────────────────────


async def test_get_settings(client):
    resp = await client.get("/api/v1/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert "publish_delay" in data
    assert "stamp_enabled" in data


async def test_update_settings_validation(client):
    """stamp_opacity must be between 10 and 100."""
    resp = await client.put("/api/v1/settings", json={"stamp_opacity": 5})
    assert resp.status_code == 422


async def test_update_settings_valid(client):
    with patch("app.main._persist_settings"):
        resp = await client.put("/api/v1/settings", json={"auto_publish": True})
        assert resp.status_code == 200
        assert resp.json()["ok"] is True


# ── Compat routes ──────────────────────────────────────────────


async def test_compat_routes_work(client):
    """Old /api/ paths should still work (backward compat)."""
    resp = await client.get("/api/channels")
    assert resp.status_code == 200


# ── Pipeline ──────────────────────────────────────────────────


async def test_pipeline_status(client):
    resp = await client.get("/api/v1/pipeline/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "running" in data


async def test_pipeline_start_requires_telegram(client):
    """Pipeline start should fail if Telegram is not connected."""
    with patch("app.services.telegram_session.get_status", new_callable=AsyncMock, return_value={"connected": False}):
        resp = await client.post("/api/v1/pipeline/start")
        assert resp.status_code == 503
