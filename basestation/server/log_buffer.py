"""In-memory ring buffer for server logs (legacy /api/django-logs/ compat)."""

from __future__ import annotations

import logging
from collections import deque

MAX_LINES = 2000
_lines: deque[str] = deque(maxlen=MAX_LINES)


class LogBufferHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            _lines.append(self.format(record))
        except Exception:  # noqa: BLE001 — logging must not raise
            self.handleError(record)


def get_log_lines() -> list[str]:
    return list(_lines)


def clear_log_lines() -> None:
    _lines.clear()


def attach_log_buffer() -> LogBufferHandler:
    handler = LogBufferHandler()
    handler.setFormatter(
        logging.Formatter("%(levelname)s %(asctime)s %(name)s: %(message)s")
    )
    for name in ("", "uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).addHandler(handler)
    return handler
