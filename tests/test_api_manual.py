"""Tests for POST /api/sessions/{id}/manual endpoint."""

from unittest.mock import patch, MagicMock
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Test client for the unauthenticated local application."""
    from backend.main import create_app
    app = create_app()
    return TestClient(app)


@pytest.fixture
def fake_session():
    return {
        "id": "sess-1",
        "status": "completed",
        "project_path": "/tmp/fake-project",
        "project_config": {
            "project": {
                "name": "图书管理系统",
                "version": "V1.0",
                "author": "T",
                "code": "abc12",
            },
            "modules": [
                {"name": "BookManagement", "label": "图书管理", "description": "..."},
            ],
            "fields": {},
        },
    }


@patch("backend.api.sessions.session_manager")
def test_manual_endpoint_returns_404_for_missing_session(mock_sm, client):
    mock_sm.get.return_value = None

    response = client.post("/api/sessions/nope/manual")
    assert response.status_code == 404


@patch("backend.api.sessions.session_manager")
def test_manual_endpoint_400_when_session_not_completed(mock_sm, client):
    mock_sm.get.return_value = {"status": "running", "project_path": "/tmp/x"}

    response = client.post("/api/sessions/sess-1/manual")
    assert response.status_code == 400


@patch("agent.docs.outline.get_provider")
@patch("backend.api.sessions.session_manager")
def test_manual_endpoint_generates_docx_and_persists_step_detail(
    mock_sm, mock_get_provider, client, fake_session, tmp_path
):
    # Session with real temp project_path
    fake_session["project_path"] = str(tmp_path)
    mock_sm.get.return_value = fake_session

    # Mock LLM
    mock_provider = MagicMock()
    mock_provider.call_detailed.return_value = {
        "content": '{"system_overview": "x", "modules": [{"name": "BookManagement", "entity_name": "图书", "overview_sentence": "..."}]}',
        "thinking": None, "prompt": "", "model": "x", "usage": None, "duration_ms": 0,
    }
    mock_get_provider.return_value = mock_provider

    response = client.post("/api/sessions/sess-1/manual")

    assert response.status_code == 200
    data = response.json()
    assert "manual_url" in data
    assert "manual_path" in data
    assert data["manual_path"].endswith("使用手册.docx")

    # File should exist
    from pathlib import Path
    assert Path(data["manual_path"]).exists()

    # session_manager.update should have been called with step_details
    update_calls = mock_sm.update.call_args_list
    assert any("step_details" in str(c) for c in update_calls)


@patch("agent.docs.outline.get_provider")
@patch("backend.api.sessions.session_manager")
def test_manual_endpoint_sanitizes_unsafe_project_name(
    mock_sm, mock_get_provider, client, fake_session, tmp_path
):
    """Project name with path separators must not escape the docs/ directory."""
    fake_session["project_path"] = str(tmp_path)
    fake_session["project_config"]["project"]["name"] = "evil/../name"
    mock_sm.get.return_value = fake_session

    mock_provider = MagicMock()
    mock_provider.call_detailed.return_value = {
        "content": '{"system_overview": "x", "modules": []}',
        "thinking": None, "prompt": "", "model": "x", "usage": None, "duration_ms": 0,
    }
    mock_get_provider.return_value = mock_provider

    response = client.post("/api/sessions/sess-1/manual")

    assert response.status_code == 200
    data = response.json()
    # Path separators must be stripped so the file cannot escape docs/
    assert "/" not in data["manual_filename"]
    assert "\\" not in data["manual_filename"]
    from pathlib import Path
    saved_path = Path(data["manual_path"])
    assert saved_path.exists()
    # File must be inside {project_path}/docs/, not above it
    docs_dir = Path(tmp_path) / "docs"
    assert docs_dir in saved_path.parents
    assert saved_path.parent == docs_dir
