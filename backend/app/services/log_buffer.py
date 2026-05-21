"""In-memory ring-buffer log handler that broadcasts entries via WebSocket."""

import asyncio
import logging
from collections import deque
from typing import Any


class LogEntry:
    """Single log entry stored in the ring buffer."""

    __slots__ = ("exc_info", "level", "logger_name", "message", "timestamp")

    def __init__(self, timestamp: float, level: str, logger_name: str, message: str, exc_info: str | None = None):
        self.timestamp = timestamp
        self.level = level
        self.logger_name = logger_name
        self.message = message
        self.exc_info = exc_info

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "timestamp": self.timestamp,
            "level": self.level,
            "logger": self.logger_name,
            "message": self.message,
        }
        if self.exc_info:
            d["exc_info"] = self.exc_info
        return d


class LogBuffer:
    """Thread-safe ring buffer for log entries."""

    def __init__(self, max_entries: int = 2000):
        self._buffer: deque[LogEntry] = deque(maxlen=max_entries)

    def append(self, entry: LogEntry) -> None:
        self._buffer.append(entry)

    def get_entries(self, limit: int = 200, level: str | None = None) -> list[dict[str, Any]]:
        """Return the most recent entries, optionally filtered by level."""
        entries = list(self._buffer)
        if level:
            level_upper = level.upper()
            entries = [e for e in entries if e.level == level_upper]
        return [e.to_dict() for e in entries[-limit:]]

    def clear(self) -> None:
        self._buffer.clear()


class WebSocketLogHandler(logging.Handler):
    """Python logging handler that writes to a LogBuffer and broadcasts via WebSocket.

    Non-blocking: WS broadcasts are fire-and-forget via asyncio tasks so they
    never block the logging call.
    """

    def __init__(self, buffer: LogBuffer, ws_manager=None):
        super().__init__()
        self.buffer = buffer
        self.ws_manager = ws_manager

    def emit(self, record: logging.LogRecord) -> None:
        try:
            exc_text = None
            if record.exc_info and record.exc_info[1]:
                exc_text = (
                    self.format(record) if self.formatter else logging.Formatter().formatException(record.exc_info)
                )

            entry = LogEntry(
                timestamp=record.created,
                level=record.levelname,
                logger_name=record.name,
                message=record.getMessage(),
                exc_info=exc_text,
            )
            self.buffer.append(entry)

            # Fire-and-forget WS broadcast
            if self.ws_manager:
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self._broadcast(entry))
                except RuntimeError:
                    pass  # No running loop (e.g. during startup)
        except Exception:
            self.handleError(record)

    async def _broadcast(self, entry: LogEntry) -> None:
        try:
            await self.ws_manager.broadcast(
                {
                    "type": "log_entry",
                    "entry": entry.to_dict(),
                }
            )
        except Exception:
            pass  # Never let log broadcasting kill the app
