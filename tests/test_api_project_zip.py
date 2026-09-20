"""Tests for GET /api/sessions/{id}/project/zip endpoint."""

import io
import zipfile
from unittest.mock import patch
from urllib.parse import unquote

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from oma_info_system.api.app import create_app

    app = create_app()
    return TestClient(app)


def _fake_session(project_path: str = "/tmp/fake-project") -> dict:
    return {
        "id": "sess-1",
        "status": "completed",
        "project_path": project_path,
        "project_config": {
            "project": {
                "name": "图书管理系统",
                "version": "V1.0",
                "author": "T",
                "code": "abc12",
            },
            "modules": [],
            "fields": {},
        },
    }


@patch("oma_info_system.api.routes.projects.session_manager")
def test_project_zip_returns_404_for_missing_session(mock_sm, client):
    mock_sm.get.return_value = None
    response = client.get("/api/sessions/nope/project/zip")
    assert response.status_code == 404


@patch("oma_info_system.api.routes.projects.session_manager")
def test_project_zip_400_when_session_not_completed(mock_sm, client):
    mock_sm.get.return_value = {"status": "running", "project_path": "/tmp/x"}
    response = client.get("/api/sessions/sess-1/project/zip")
    assert response.status_code == 400


@patch("oma_info_system.api.routes.projects.session_manager")
def test_project_zip_400_when_project_path_missing(mock_sm, client, tmp_path):
    fake = _fake_session(str(tmp_path / "does-not-exist"))
    mock_sm.get.return_value = fake
    response = client.get("/api/sessions/sess-1/project/zip")
    assert response.status_code == 400


@patch("oma_info_system.api.routes.projects.session_manager")
def test_project_zip_streams_valid_zip_with_project_files(mock_sm, client, tmp_path):
    project_dir = tmp_path / "myproject"
    project_dir.mkdir()
    (project_dir / "app.py").write_text("print('hi')")
    (project_dir / "subdir").mkdir()
    (project_dir / "subdir" / "model.py").write_text("# model")

    mock_sm.get.return_value = _fake_session(str(project_dir))

    response = client.get("/api/sessions/sess-1/project/zip")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"

    cd = response.headers["content-disposition"]
    assert "attachment" in cd
    # Non-ASCII project name is delivered via RFC 5987 filename* (percent-encoded UTF-8)
    assert "filename*=UTF-8''" in cd
    encoded = cd.split("filename*=UTF-8''")[1].split(";")[0].strip().strip('"')
    assert unquote(encoded) == "图书管理系统V1.0.zip"

    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        names = zf.namelist()
    # Archive must include the project dir as the top-level folder
    assert any(n.startswith("myproject/") for n in names)
    assert "myproject/app.py" in names
    assert "myproject/subdir/model.py" in names


@patch("oma_info_system.api.routes.projects.session_manager")
def test_project_zip_excludes_build_and_cache_junk(mock_sm, client, tmp_path):
    project_dir = tmp_path / "myproject"
    project_dir.mkdir()
    (project_dir / "app.py").write_text("ok")
    (project_dir / "__pycache__").mkdir()
    (project_dir / "__pycache__" / "app.cpython-312.pyc").write_bytes(b"\x00\x00")
    (project_dir / "subdir").mkdir()
    (project_dir / "subdir" / "__pycache__").mkdir()
    (project_dir / "subdir" / "__pycache__" / "x.pyc").write_bytes(b"\x00")
    (project_dir / ".venv").mkdir()
    (project_dir / ".venv" / "pyvenv.cfg").write_text("home=/usr")
    (project_dir / ".DS_Store").write_bytes(b"\x00")

    mock_sm.get.return_value = _fake_session(str(project_dir))

    response = client.get("/api/sessions/sess-1/project/zip")
    assert response.status_code == 200

    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        names = zf.namelist()

    assert "myproject/app.py" in names
    assert not any("__pycache__" in n for n in names), names
    assert not any(n.endswith(".pyc") for n in names), names
    assert not any(".venv" in n for n in names), names
    assert not any(n.endswith(".DS_Store") for n in names), names


@patch("oma_info_system.api.routes.projects.session_manager")
def test_project_zip_sanitizes_unsafe_project_name(mock_sm, client, tmp_path):
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    (project_dir / "app.py").write_text("ok")

    fake = _fake_session(str(project_dir))
    fake["project_config"]["project"]["name"] = "evil/../name"
    mock_sm.get.return_value = fake

    response = client.get("/api/sessions/sess-1/project/zip")
    assert response.status_code == 200
    cd = response.headers["content-disposition"]
    assert "/" not in cd.split('filename="')[1].split('"')[0]
    assert "\\" not in cd.split('filename="')[1].split('"')[0]
