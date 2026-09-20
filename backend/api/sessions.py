"""Session management endpoints."""

import io
import subprocess
import os
import re
import socket
import shutil
import zipfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote

from datetime import datetime
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from typing import Optional

from backend.core.config import settings
from shared.session.manager import SessionManager
from shared.preview.manager import get_preview_manager
from shared.trace import get_trace_manager, trace_event
from agent.graph.workflow import run_workflow


router = APIRouter()
session_manager = SessionManager(settings.DATABASE_FILE)
preview_manager = get_preview_manager()


class SessionCreate(BaseModel):
    """Request model for creating a session."""
    user_input: str
    mode: str = "yolo"  # yolo or hitl
    output_dir: Optional[str] = None


class SessionApproval(BaseModel):
    """Request model for approving a step."""
    approval_response: str


@router.post("/sessions")
async def create_session(request: SessionCreate):
    """Create a new generation session."""
    session_id = session_manager.create(
        user_input=request.user_input,
        mode=request.mode,
        output_dir=request.output_dir or settings.OUTPUT_DIR
    )
    trace_event("task_received", session_id=session_id, mode=request.mode, user_input_chars=len(request.user_input))
    trace_event("session_created", session_id=session_id, output_dir=request.output_dir or settings.OUTPUT_DIR)

    # Run workflow in background thread
    import threading

    def run():
        try:
            run_workflow(session_id, request.user_input, request.mode)
        except Exception as e:
            session_manager.update(session_id, {
                "error": str(e),
                "status": "failed",
                "finished_at": datetime.now().isoformat(),
            })
            trace_event("workflow_failed", session_id=session_id, error_type=type(e).__name__, error=str(e))

    t = threading.Thread(target=run, daemon=True)
    t.start()

    return {"session_id": session_id, "status": "started"}


@router.get("/sessions/{session_id}/trace")
async def get_session_trace(session_id: str, limit: int = 2000):
    """Return the execution trace for a generation session."""
    if not session_manager.get(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": session_id, "events": get_trace_manager().read(session_id, limit)}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Get session status."""
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.post("/sessions/{session_id}/approve")
async def approve_step(session_id: str, approval: SessionApproval):
    """Handle HITL approval and continue workflow."""
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Update with approval
    session_manager.update(session_id, {
        "approval_response": approval.approval_response,
        "approval_required": False
    })

    # Continue workflow in background
    import threading
    def run():
        try:
            from agent.graph.workflow import continue_workflow
            continue_workflow(session_id)
        except Exception as e:
            session_manager.update(session_id, {
                "error": str(e),
                "status": "failed",
                "finished_at": datetime.now().isoformat(),
            })

    t = threading.Thread(target=run, daemon=True)
    t.start()

    return session_manager.get(session_id)


def _find_free_port(start: int = 5001, end: int = 5100) -> int:
    """Find a free port in the given range."""
    for port in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("No free port found")


def _wait_for_preview(process, port: int, timeout: float = 15.0) -> None:
    """Wait until the generated Flask app accepts HTTP requests."""
    deadline = time.monotonic() + timeout
    url = f"http://127.0.0.1:{port}/admin/"
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    while time.monotonic() < deadline:
        if process.poll() is not None:
            stderr = process.stderr.read().decode("utf-8", errors="replace") if process.stderr else ""
            raise RuntimeError(f"Preview process exited early: {stderr[-1200:]}")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                pass
            with opener.open(url, timeout=0.5):
                return
        except urllib.error.HTTPError:
            return
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(0.25)
    raise TimeoutError(f"Preview did not become ready on port {port}")


@router.post("/sessions/{session_id}/preview")
async def start_preview(session_id: str):
    """Start the generated project as a preview."""
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    project_path = session.get("project_path")
    if not project_path or not Path(project_path).exists():
        raise HTTPException(status_code=400, detail="Project not generated yet")

    # Stop existing preview if any
    existing = preview_manager.get_record(session_id)
    if existing and existing.state == "preview":
        preview_manager.stop_preview(session_id)

    port = _find_free_port()
    uv_bin = _resolve_uv_bin()
    uv_run_prefix = [
        uv_bin, "run", "--no-project",
        "--with", "flask", "--with", "flask-admin",
        "--with", "flask-sqlalchemy", "--with", "flask-bcrypt",
        "--with", "flask-login", "--with", "flask-babel",
    ]

    # Init DB if needed (first run)
    db_file = Path(project_path) / "app.db"
    if not db_file.exists():
        init_result = subprocess.run(
            uv_run_prefix + ["python", "run.py", "--init-db"],
            cwd=project_path,
            capture_output=True, timeout=60,
        )
        if init_result.returncode != 0:
            error = init_result.stderr.decode("utf-8", errors="replace")[-1200:]
            raise HTTPException(status_code=500, detail=f"Preview database initialization failed: {error}")

    # Start app via uv run
    process = subprocess.Popen(
        uv_run_prefix + ["python", "run.py", "--port", str(port)],
        cwd=project_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ},
    )

    try:
        _wait_for_preview(process, port)
    except Exception as exc:
        process.terminate()
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Track in preview manager after the process is ready.
    preview_manager.start_preview(session_id, project_path, port, process)

    # Browser-facing URL. Prefer the wildcard subdomain when configured; fall
    # back to the FastAPI subpath proxy (works immediately on the main domain).
    public_base = os.environ.get("PREVIEW_PUBLIC_BASE")
    if public_base:
        public_url = f"https://{session_id}.{public_base}/admin/"
    else:
        public_url = f"/api/sessions/{session_id}/preview/proxy/admin/"
    return {
        "preview_url": f"http://127.0.0.1:{port}/admin/",
        "public_url": public_url,
        "port": port,
        "project_path": project_path,
    }


@router.get("/sessions/{session_id}/preview")
async def get_preview_status(session_id: str):
    """Get preview status for a session."""
    record = preview_manager.get_record(session_id)
    if not record or record.state != "preview":
        return {"running": False}

    # Check both the process and the local port. A stale PID alone is not
    # enough because the preview child may have exited or the PID may be reused.
    try:
        os.kill(record.pid, 0)
        with socket.create_connection(("127.0.0.1", record.port), timeout=0.3):
            pass
    except (ProcessLookupError, ConnectionRefusedError, TimeoutError, OSError):
        # Process died, mark as stopped
        preview_manager.stop_preview(session_id)
        return {"running": False}

    return {
        "running": True,
        "port": record.port,
        "pid": record.pid,
        "preview_url": f"http://127.0.0.1:{record.port}/admin/",
        "started_at": record.started_at,
        "timeout_at": record.timeout_at,
    }


_PREVIEW_PROXY_HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host",
}


@router.api_route(
    "/sessions/{session_id}/preview/proxy/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
)
async def proxy_preview(
    session_id: str,
    path: str,
    request: Request,
):
    """Reverse-proxy a request to the session's preview Flask process.

    Two URL modes:
      - PREVIEW_PUBLIC_BASE set  → wildcard subdomain; nginx routes the
        raw path through to this endpoint. No rewriting needed because
        the browser origin already matches the absolute /admin/ URLs
        that Flask-Admin emits.
      - PREVIEW_PUBLIC_BASE unset → subpath fallback on the main domain.
        We rewrite absolute /admin/ URLs and Location redirects so they
        route back through the proxy instead of hitting the main app.
    """
    import httpx

    record = preview_manager.get_record(session_id)
    if not record or record.state != "preview":
        raise HTTPException(status_code=404, detail="Preview not running")

    upstream = f"http://127.0.0.1:{record.port}/{path}"
    if request.url.query:
        upstream += f"?{request.url.query}"

    fwd_headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in _PREVIEW_PROXY_HOP_BY_HOP
    }
    body = await request.body()

    try:
        async with httpx.AsyncClient(follow_redirects=False, timeout=30.0, trust_env=False) as client:
            resp = await client.request(
                request.method,
                upstream,
                headers=fwd_headers,
                content=body if body else None,
            )
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="Preview process not responding")

    excluded = _PREVIEW_PROXY_HOP_BY_HOP | {"content-length"}
    resp_headers = {
        k: v for k, v in resp.headers.items()
        if k.lower() not in excluded
    }

    public_base = os.environ.get("PREVIEW_PUBLIC_BASE")
    if not public_base:
        proxy_prefix = f"/api/sessions/{session_id}/preview/proxy"

        # Rewrite redirect Location so the browser follows through the proxy.
        loc = resp_headers.get("location")
        if loc and loc.startswith("/"):
            resp_headers["location"] = f"{proxy_prefix}{loc}"

        # Rewrite absolute /admin/ URLs in HTML so CSS/JS/assets load.
        content_type = (resp_headers.get("content-type") or "").lower()
        if "text/html" in content_type:
            text = resp.content.decode("utf-8", errors="replace")
            text = re.sub(
                r'(["\'])/admin/',
                rf'\1{proxy_prefix}/admin/',
                text,
            )
            return Response(
                content=text.encode("utf-8"),
                status_code=resp.status_code,
                headers=resp_headers,
                media_type="text/html; charset=utf-8",
            )

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=resp_headers,
    )


@router.delete("/sessions/{session_id}/preview")
async def stop_preview(session_id: str):
    """Stop the preview process."""
    record = preview_manager.get_record(session_id)
    if not record or record.state != "preview":
        return {"status": "stopped", "already_stopped": True}
    preview_manager.stop_preview(session_id)
    return {"status": "stopped"}


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session and its generated project."""
    # Stop preview if running
    record = preview_manager.get_record(session_id)
    if record and record.state == "preview":
        preview_manager.stop_preview(session_id)
    preview_manager.destroy_record(session_id)

    # Get session info
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Delete project files
    project_path = session.get("project_path")
    if project_path:
        path = Path(project_path)
        if path.exists():
            shutil.rmtree(path)

    # Delete session from TinyDB
    session_manager.delete(session_id)

    return {"status": "deleted"}


@router.get("/sessions")
async def list_sessions(limit: int = 50):
    """List all sessions."""
    sessions = session_manager.list(limit=limit)
    return {"sessions": sessions}


@router.post("/sessions/{session_id}/manual")
async def generate_manual(session_id: str):
    """Generate the user manual docx for a completed session."""
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.get("status") != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Session status is '{session.get('status')}', must be 'completed'",
        )

    project_path = session.get("project_path")
    if not project_path or not Path(project_path).exists():
        raise HTTPException(status_code=400, detail="Project path not found")

    project_config = session.get("project_config")
    if not project_config:
        raise HTTPException(status_code=400, detail="Project config missing")

    # 1. Generate outline via LLM (with fallback)
    from agent.docs.outline import generate_outline
    outline, outline_error = generate_outline(
        project_config,
        business_domain=session.get("business_domain") or "",
        return_error=True,
    )

    # 2. Build the docx
    from agent.docs.builder import build_manual
    project = project_config["project"]
    # Sanitize project name: strip characters that would break Path or escape docs/
    safe_name = re.sub(r'[\\/:*?"<>|]', "_", project["name"])
    output_filename = f"{safe_name}{project['version']}使用手册.docx"
    output_path = str(Path(project_path) / "docs" / output_filename)

    build_manual(project_config, outline, output_path)

    # 3. Persist step_details
    detail = {
        "title": "用户手册生成",
        "summary": f"生成 {len(project_config.get('modules', []))} 个模块的 docx 手册"
                   + (f" (LLM 大纲失败，使用 fallback: {outline_error})" if outline_error else ""),
        "prompt": "",
        "response": outline.model_dump_json() if outline else "",
        "thinking": None,
        "data": {
            "manual_path": output_path,
            "manual_filename": output_filename,
            "outline": outline.model_dump() if outline else {},
            "module_count": len(project_config.get("modules", [])),
            "outline_error": outline_error or None,
        },
        "duration_ms": None,
        "error": outline_error or None,
    }

    session_manager.update(session_id, {
        "step_details": {
            **(session.get("step_details") or {}),
            "generate_user_manual": detail,
        }
    })

    return {
        "manual_url": f"/api/sessions/{session_id}/manual/file",
        "manual_path": output_path,
        "manual_filename": output_filename,
        "generated_at": datetime.now().isoformat(),
        "outline_error": outline_error or None,
    }


@router.get("/sessions/{session_id}/manual/file")
async def download_manual(session_id: str):
    """Stream the generated docx file."""
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    step_details = session.get("step_details") or {}
    manual_detail = step_details.get("generate_user_manual") or {}
    manual_path = (manual_detail.get("data") or {}).get("manual_path")

    if not manual_path or not Path(manual_path).exists():
        raise HTTPException(status_code=404, detail="Manual not generated yet")

    filename = (manual_detail.get("data") or {}).get("manual_filename", "manual.docx")
    return FileResponse(
        path=str(manual_path),
        filename=str(filename),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


_PROJECT_ZIP_EXCLUDED_DIRS = {
    "__pycache__", ".venv", "venv", ".git", "node_modules",
    ".pytest_cache", ".mypy_cache", ".ruff_cache",
}
_PROJECT_ZIP_EXCLUDED_SUFFIXES = {".pyc", ".pyo"}
_PROJECT_ZIP_EXCLUDED_NAMES = {".DS_Store"}


def _resolve_uv_bin() -> str:
    """Locate the uv binary across environments where PATH may be minimal.

    systemd services don't inherit the user shell PATH, so a bare "uv"
    can fail with FileNotFoundError even when uv is installed. Check the
    env override first, then `which`, then the standard install paths.
    """
    candidates = [
        os.environ.get("UV_BIN"),
        shutil.which("uv"),
        os.path.expanduser("~/.local/bin/uv"),
        "/usr/local/bin/uv",
    ]
    for c in candidates:
        if c and Path(c).exists():
            return c
    raise HTTPException(
        status_code=500,
        detail="uv binary not found. Set UV_BIN or install uv to ~/.local/bin/uv.",
    )


@router.get("/sessions/{session_id}/project/zip")
async def download_project_zip(session_id: str):
    """Stream the generated project as a zip archive."""
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.get("status") != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Session status is '{session.get('status')}', must be 'completed'",
        )

    project_path = session.get("project_path")
    if not project_path or not Path(project_path).exists():
        raise HTTPException(status_code=400, detail="Project path not found")

    project = (session.get("project_config") or {}).get("project") or {}
    safe_name = re.sub(r'[\\/:*?"<>|]', "_", project.get("name") or "project")
    version = project.get("version") or ""
    filename = f"{safe_name}{version}.zip"
    ascii_fallback = re.sub(r"[^\x20-\x7E]", "_", filename)
    disposition = (
        f"attachment; filename=\"{ascii_fallback}\"; "
        f"filename*=UTF-8''{quote(filename, safe='')}"
    )

    root = Path(project_path)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in _PROJECT_ZIP_EXCLUDED_DIRS]
            for name in filenames:
                fp = Path(dirpath) / name
                if fp.suffix in _PROJECT_ZIP_EXCLUDED_SUFFIXES:
                    continue
                if fp.name in _PROJECT_ZIP_EXCLUDED_NAMES:
                    continue
                arcname = fp.relative_to(root.parent)
                zf.write(fp, arcname)
    buf.seek(0)

    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": disposition},
    )
