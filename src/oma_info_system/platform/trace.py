"""Append-only JSONL trace storage for task execution."""

import json
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class TraceManager:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _path(self, session_id: str) -> Path:
        return self.root / f"{session_id}.jsonl"

    def emit(self, session_id: str, event: str, **data: Any) -> dict:
        record = {
            "event_id": str(uuid.uuid4()),
            "session_id": session_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            **data,
        }
        path = self._path(session_id)
        with self._lock:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        return record

    def read(self, session_id: str, limit: int = 2000) -> list[dict]:
        path = self._path(session_id)
        if not path.exists():
            return []
        records = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return records[-limit:]


_manager: TraceManager | None = None


def get_trace_manager() -> TraceManager:
    global _manager
    if _manager is None:
        from oma_info_system.config import settings

        _manager = TraceManager(settings.TRACES_DIR)
    return _manager


_session_id: ContextVar[str | None] = ContextVar("trace_session_id", default=None)


@contextmanager
def session_trace_context(session_id: str) -> Iterator[None]:
    token = _session_id.set(session_id)
    try:
        yield
    finally:
        _session_id.reset(token)


def trace_event(event: str, session_id: str | None = None, **data: Any) -> None:
    session_id = session_id or _session_id.get()
    if not session_id:
        return
    get_trace_manager().emit(session_id, event, **data)


__all__ = [
    "TraceManager",
    "get_trace_manager",
    "session_trace_context",
    "trace_event",
]
