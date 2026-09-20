"""Lightweight per-session execution tracing."""

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator, Optional

from .manager import TraceManager, get_trace_manager

_session_id: ContextVar[Optional[str]] = ContextVar("trace_session_id", default=None)


@contextmanager
def session_trace_context(session_id: str) -> Iterator[None]:
    token = _session_id.set(session_id)
    try:
        yield
    finally:
        _session_id.reset(token)


def trace_event(event: str, session_id: Optional[str] = None, **data) -> None:
    session_id = session_id or _session_id.get()
    if not session_id:
        return
    get_trace_manager().emit(session_id, event, **data)


__all__ = ["TraceManager", "get_trace_manager", "session_trace_context", "trace_event"]
