"""Preview endpoints for generated projects.

This module owns the lifecycle of the temporary Flask process that serves a
generated project, plus the reverse proxy used to reach it from the browser.
"""

import os
import re
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from oma_info_system.api.deps import preview_manager, session_manager
from oma_info_system.platform.uv import UVNotFoundError, resolve_uv_bin

router = APIRouter()

# Headers that must not be forwarded verbatim by a hop-by-hop proxy.
_PREVIEW_PROXY_HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",
}

_PREVIEW_WITH_PACKAGES = [
    "--with",
    "flask",
    "--with",
    "flask-admin",
    "--with",
    "flask-sqlalchemy",
    "--with",
    "flask-bcrypt",
    "--with",
    "flask-login",
    "--with",
    "flask-babel",
]


def _find_free_port(start: int = 5001, end: int = 5100) -> int:
    """Find a free TCP port in the given range."""
    for port in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
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


def _preview_launch_prefix() -> list[str]:
    """Command prefix that runs a generated project without its own env."""
    try:
        uv_bin = resolve_uv_bin()
    except UVNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return [uv_bin, "run", "--no-project", *_PREVIEW_WITH_PACKAGES]


@router.post("/sessions/{session_id}/preview")
async def start_preview(session_id: str):
    """Start the generated project as a preview."""
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    project_path = session.get("project_path")
    if not project_path or not Path(project_path).exists():
        raise HTTPException(status_code=400, detail="Project not generated yet")

    existing = preview_manager.get_record(session_id)
    if existing and existing.state == "preview":
        preview_manager.stop_preview(session_id)

    port = _find_free_port()
    uv_run_prefix = _preview_launch_prefix()

    db_file = Path(project_path) / "app.db"
    if not db_file.exists():
        init_result = subprocess.run(
            uv_run_prefix + ["python", "run.py", "--init-db"],
            cwd=project_path,
            capture_output=True,
            timeout=60,
        )
        if init_result.returncode != 0:
            error = init_result.stderr.decode("utf-8", errors="replace")[-1200:]
            raise HTTPException(status_code=500, detail=f"Preview database initialization failed: {error}")

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

    preview_manager.start_preview(session_id, project_path, port, process)

    # Browser-facing URL: prefer the wildcard subdomain when configured,
    # otherwise fall back to the subpath proxy on the main domain.
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

    # A stale PID is not enough: the child may have exited, or the PID may
    # have been reused, so confirm the port is actually accepting connections.
    try:
        os.kill(record.pid, 0)
        with socket.create_connection(("127.0.0.1", record.port), timeout=0.3):
            pass
    except (ProcessLookupError, ConnectionRefusedError, TimeoutError, OSError):
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


@router.delete("/sessions/{session_id}/preview")
async def stop_preview(session_id: str):
    """Stop the preview process."""
    record = preview_manager.get_record(session_id)
    if not record or record.state != "preview":
        return {"status": "stopped", "already_stopped": True}
    preview_manager.stop_preview(session_id)
    return {"status": "stopped"}


@router.api_route(
    "/sessions/{session_id}/preview/proxy/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
)
async def proxy_preview(session_id: str, path: str, request: Request):
    """Reverse-proxy a request to the session's preview Flask process.

    Two URL modes:
      - PREVIEW_PUBLIC_BASE set  -> wildcard subdomain; the edge routes the
        raw path through to this endpoint. No rewriting is needed because the
        browser origin already matches the absolute /admin/ URLs that
        Flask-Admin emits.
      - PREVIEW_PUBLIC_BASE unset -> subpath fallback on the main domain.
        Absolute /admin/ URLs and Location redirects are rewritten so they
        route back through this proxy instead of hitting the main app.
    """
    import httpx

    record = preview_manager.get_record(session_id)
    if not record or record.state != "preview":
        raise HTTPException(status_code=404, detail="Preview not running")

    upstream = f"http://127.0.0.1:{record.port}/{path}"
    if request.url.query:
        upstream += f"?{request.url.query}"

    fwd_headers = {k: v for k, v in request.headers.items() if k.lower() not in _PREVIEW_PROXY_HOP_BY_HOP}
    body = await request.body()

    try:
        async with httpx.AsyncClient(follow_redirects=False, timeout=30.0, trust_env=False) as client:
            resp = await client.request(
                request.method,
                upstream,
                headers=fwd_headers,
                content=body if body else None,
            )
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail="Preview process not responding") from exc

    excluded = _PREVIEW_PROXY_HOP_BY_HOP | {"content-length"}
    resp_headers = {k: v for k, v in resp.headers.items() if k.lower() not in excluded}

    public_base = os.environ.get("PREVIEW_PUBLIC_BASE")
    if not public_base:
        proxy_prefix = f"/api/sessions/{session_id}/preview/proxy"

        loc = resp_headers.get("location")
        if loc and loc.startswith("/"):
            resp_headers["location"] = f"{proxy_prefix}{loc}"

        content_type = (resp_headers.get("content-type") or "").lower()
        if "text/html" in content_type:
            text = resp.content.decode("utf-8", errors="replace")
            text = re.sub(r'(["\'])/admin/', rf"\1{proxy_prefix}/admin/", text)
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
