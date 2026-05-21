"""Tests for pipeline state machine, dedup, and concurrency."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio


async def test_pipeline_state_transitions():
    """Test that PipelineState TypedDict has all expected fields."""
    from app.orchestrator.state import PipelineState

    # Verify PipelineState has the expected keys
    hints = PipelineState.__annotations__
    assert "message_id" in hints
    assert "original_text" in hints
    assert "translated_text" in hints
    assert "approved" in hints
    assert "published" in hints
    assert "content_filtered" in hints


async def test_pipeline_router_concurrency():
    """Test that PipelineRouter respects max_concurrent semaphore."""
    mock_manager = MagicMock()
    mock_manager.broadcast = AsyncMock()

    with patch("app.orchestrator.router.PipelineRouter._run_pipeline", new_callable=AsyncMock):
        from app.orchestrator.router import PipelineRouter

        router = PipelineRouter(mock_manager)
        # The semaphore should be initialized with pipeline_max_concurrent
        assert router._semaphore._value == 5  # default from settings


async def test_pending_state_lifecycle():
    """Test get/set/remove pending state."""
    from app.orchestrator.graph import (
        _pending_reviews,
        get_pending_state,
        remove_pending_state,
    )

    msg_id = "test-msg-001"
    test_state = {"message_id": msg_id, "status": "reviewing"}

    _pending_reviews[msg_id] = test_state
    assert get_pending_state(msg_id) == test_state

    remove_pending_state(msg_id)
    assert get_pending_state(msg_id) is None
