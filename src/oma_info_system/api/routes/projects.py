"""Generated-project artifact endpoints."""

import io
import os
import re
import zipfile
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from oma_info_system.api.deps import session_manager

router = APIRouter()

_PROJECT_ZIP_EXCLUDED_DIRS = {
    "__pycache__",
    ".venv",
    "venv",
    ".git",
    "node_modules",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}
_PROJECT_ZIP_EXCLUDED_SUFFIXES = {".pyc", ".pyo"}
_PROJECT_ZIP_EXCLUDED_NAMES = {".DS_Store"}


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

    # RFC 5987: ASCII fallback plus a UTF-8 encoded name for non-ASCII titles.
    ascii_fallback = re.sub(r"[^\x20-\x7E]", "_", filename)
    disposition = f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{quote(filename, safe='')}"

    root = Path(project_path)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in _PROJECT_ZIP_EXCLUDED_DIRS]
            for name in filenames:
                file_path = Path(dirpath) / name
                if file_path.suffix in _PROJECT_ZIP_EXCLUDED_SUFFIXES:
                    continue
                if file_path.name in _PROJECT_ZIP_EXCLUDED_NAMES:
                    continue
                archive.write(file_path, file_path.relative_to(root.parent))
    buf.seek(0)

    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": disposition},
    )
