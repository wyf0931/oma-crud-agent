"""Infrastructure adapters: storage, sessions, preview, tracing."""

from oma_info_system.platform.preview import (
    PreviewManager,
    PreviewRecord,
    PreviewState,
    get_preview_manager,
    reset_preview_manager,
)
from oma_info_system.platform.sessions import SessionManager
from oma_info_system.platform.storage import get_database
from oma_info_system.platform.trace import (
    TraceManager,
    get_trace_manager,
    session_trace_context,
    trace_event,
)

__all__ = [
    "PreviewManager",
    "PreviewRecord",
    "PreviewState",
    "SessionManager",
    "TraceManager",
    "get_database",
    "get_preview_manager",
    "get_trace_manager",
    "reset_preview_manager",
    "session_trace_context",
    "trace_event",
]
