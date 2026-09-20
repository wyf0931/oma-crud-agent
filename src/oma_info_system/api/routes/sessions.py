"""Session lifecycle endpoints."""

import shutil
import threading
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException

from oma_info_system.api.deps import preview_manager, session_manager
from oma_info_system.api.schemas import SessionApproval, SessionCreate
from oma_info_system.config import settings
from oma_info_system.platform.trace import get_trace_manager, trace_event
from oma_info_system.workflow.graph import continue_workflow, run_workflow

router = APIRouter()


def _run_in_background(target) -> None:
    """Start a daemon thread for workflow work that outlives the request."""
    threading.Thread(target=target, daemon=True).start()


@router.post("/sessions")
async def create_session(request: SessionCreate):
    """Create a new generation session."""
    output_dir = request.output_dir or settings.OUTPUT_DIR
    session_id = session_manager.create(
        user_input=request.user_input,
        mode=request.mode,
        output_dir=output_dir,
    )
    trace_event("task_received", session_id=session_id, mode=request.mode, user_input_chars=len(request.user_input))
    trace_event("session_created", session_id=session_id, output_dir=output_dir)

    def run() -> None:
        try:
            run_workflow(session_id, request.user_input, request.mode)
        except Exception as exc:
            session_manager.update(
                session_id,
                {
                    "error": str(exc),
                    "status": "failed",
                    "finished_at": datetime.now().isoformat(),
                },
            )
            trace_event("workflow_failed", session_id=session_id, error_type=type(exc).__name__, error=str(exc))

    _run_in_background(run)

    return {"session_id": session_id, "status": "started"}


@router.get("/sessions")
async def list_sessions(limit: int = 50):
    """List all sessions."""
    return {"sessions": session_manager.list(limit=limit)}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Get session status."""
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.get("/sessions/{session_id}/trace")
async def get_session_trace(session_id: str, limit: int = 2000):
    """Return the execution trace for a generation session."""
    if not session_manager.get(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": session_id, "events": get_trace_manager().read(session_id, limit)}


@router.post("/sessions/{session_id}/approve")
async def approve_step(session_id: str, approval: SessionApproval):
    """Handle HITL approval and continue workflow."""
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session_manager.update(
        session_id,
        {"approval_response": approval.approval_response, "approval_required": False},
    )

    def run() -> None:
        try:
            continue_workflow(session_id)
        except Exception as exc:
            session_manager.update(
                session_id,
                {
                    "error": str(exc),
                    "status": "failed",
                    "finished_at": datetime.now().isoformat(),
                },
            )

    _run_in_background(run)

    return session_manager.get(session_id)


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session and its generated project."""
    record = preview_manager.get_record(session_id)
    if record and record.state == "preview":
        preview_manager.stop_preview(session_id)
    preview_manager.destroy_record(session_id)

    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    project_path = session.get("project_path")
    if project_path:
        path = Path(project_path)
        if path.exists():
            try:
                shutil.rmtree(path)
            except OSError as exc:
                raise HTTPException(status_code=500, detail=f"Could not delete project files: {exc}") from exc

    session_manager.delete(session_id)

    return {"status": "deleted"}
