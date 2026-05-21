"""Shared fixtures for backend test suite."""

import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest.fixture(scope="session")
def event_loop():
    """Use a single event loop for all async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Async test client that talks to the FastAPI app without needing real infra."""
    # Mock heavy dependencies before importing the app
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
    ):
        daemon_instance = MagicMock()
        daemon_instance.start = AsyncMock()
        daemon_instance.stop = AsyncMock()
        MockDaemon.return_value = daemon_instance

        from app.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest_asyncio.fixture
async def authed_client() -> AsyncGenerator[AsyncClient, None]:
    """Test client with auth token set."""
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
        patch("app.config.settings.api_secret_token", "test-secret-token"),
    ):
        daemon_instance = MagicMock()
        daemon_instance.start = AsyncMock()
        daemon_instance.stop = AsyncMock()
        MockDaemon.return_value = daemon_instance

        from app.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            headers={"Authorization": "Bearer test-secret-token"},
        ) as ac:
            yield ac
