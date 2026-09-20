"""Tests for the preview reverse-proxy endpoint."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    from oma_info_system.api.app import create_app

    app = create_app()
    return TestClient(app)


@patch("oma_info_system.api.routes.sessions.preview_manager")
def test_proxy_returns_404_when_no_preview_running(mock_pm, client):
    mock_pm.get_record.return_value = None
    response = client.get("/api/sessions/sess-1/preview/proxy/admin/")
    assert response.status_code == 404


@patch("oma_info_system.api.routes.sessions.preview_manager")
def test_proxy_returns_404_when_preview_destroyed(mock_pm, client):
    rec = MagicMock()
    rec.state = "destroyed"
    rec.port = 5001
    mock_pm.get_record.return_value = rec
    response = client.get("/api/sessions/sess-1/preview/proxy/admin/")
    assert response.status_code == 404


@patch("oma_info_system.api.routes.sessions.preview_manager")
def test_proxy_returns_502_when_upstream_unreachable(mock_pm, client):
    """If the Flask process died or hasn't bound yet, return 502."""
    import httpx

    rec = MagicMock()
    rec.state = "preview"
    rec.port = 5001
    mock_pm.get_record.return_value = rec

    # Patch AsyncClient.request to raise ConnectError
    class _FakeAsyncClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def request(self, *a, **kw):
            raise httpx.ConnectError("connection refused")

    with patch("httpx.AsyncClient", _FakeAsyncClient):
        response = client.get("/api/sessions/sess-1/preview/proxy/admin/")
    assert response.status_code == 502


@patch("oma_info_system.api.routes.sessions.preview_manager")
def test_proxy_forwards_path_query_and_method_to_upstream(mock_pm, client):
    """Path, query string, method, and request body must reach the upstream."""
    captured = {}

    class _FakeResponse:
        status_code = 200
        headers = {"content-type": "text/html"}
        content = b"<html>admin</html>"

    class _FakeAsyncClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def request(self, method, url, **kw):
            captured["method"] = method
            captured["url"] = url
            captured["headers"] = kw.get("headers", {})
            captured["content"] = kw.get("content")
            return _FakeResponse()

    rec = MagicMock()
    rec.state = "preview"
    rec.port = 5599
    mock_pm.get_record.return_value = rec

    with patch("httpx.AsyncClient", _FakeAsyncClient):
        response = client.post(
            "/api/sessions/sess-1/preview/proxy/admin/save?x=1",
            content=b'{"foo": "bar"}',
            headers={"content-type": "application/json"},
        )

    assert response.status_code == 200
    assert response.content == b"<html>admin</html>"
    assert response.headers["content-type"] == "text/html"

    assert captured["method"] == "POST"
    assert captured["url"] == "http://127.0.0.1:5599/admin/save?x=1"
    assert captured["content"] == b'{"foo": "bar"}'


@patch("oma_info_system.api.routes.sessions.preview_manager")
@patch("oma_info_system.api.routes.sessions._resolve_uv_bin", return_value="/usr/local/bin/uv")
@patch("oma_info_system.api.routes.sessions._find_free_port", return_value=5012)
@patch("oma_info_system.api.routes.sessions._wait_for_preview")
@patch("oma_info_system.api.routes.sessions.subprocess")
def test_start_preview_includes_public_url_when_base_set(
    mock_subprocess, mock_wait, mock_port, mock_uv, mock_pm, client, tmp_path, monkeypatch
):
    """start_preview returns public_url when PREVIEW_PUBLIC_BASE env is set."""
    # Set up a fake project so the validation passes
    project_dir = tmp_path / "myproject"
    project_dir.mkdir()
    (project_dir / "app.db").touch()  # Skip init-db subprocess
    monkeypatch.setenv("PREVIEW_PUBLIC_BASE", "preview.ohmyagent.ai")

    mock_pm.get_record.return_value = None  # No existing preview
    fake_proc = MagicMock()
    fake_proc.pid = 12345
    mock_subprocess.Popen.return_value = fake_proc

    session = {
        "id": "abc123",
        "status": "completed",
        "project_path": str(project_dir),
    }
    with patch("oma_info_system.api.routes.sessions.session_manager") as mock_sm:
        mock_sm.get.return_value = session
        response = client.post("/api/sessions/abc123/preview")

    assert response.status_code == 200
    data = response.json()
    assert data["public_url"] == "https://abc123.preview.ohmyagent.ai/admin/"
    # Internal URL still returned for server-side health checks
    assert data["preview_url"] == "http://127.0.0.1:5012/admin/"


@patch("oma_info_system.api.routes.sessions.preview_manager")
@patch("oma_info_system.api.routes.sessions._resolve_uv_bin", return_value="/usr/local/bin/uv")
@patch("oma_info_system.api.routes.sessions._find_free_port", return_value=5012)
@patch("oma_info_system.api.routes.sessions._wait_for_preview")
@patch("oma_info_system.api.routes.sessions.subprocess")
def test_start_preview_falls_back_to_subpath_proxy_when_base_unset(
    mock_subprocess, mock_wait, mock_port, mock_uv, mock_pm, client, tmp_path, monkeypatch
):
    """Without PREVIEW_PUBLIC_BASE, public_url should be the subpath proxy."""
    project_dir = tmp_path / "myproject"
    project_dir.mkdir()
    (project_dir / "app.db").touch()
    monkeypatch.delenv("PREVIEW_PUBLIC_BASE", raising=False)

    mock_pm.get_record.return_value = None
    fake_proc = MagicMock()
    fake_proc.pid = 12345
    mock_subprocess.Popen.return_value = fake_proc

    session = {
        "id": "abc123",
        "status": "completed",
        "project_path": str(project_dir),
    }
    with patch("oma_info_system.api.routes.sessions.session_manager") as mock_sm:
        mock_sm.get.return_value = session
        response = client.post("/api/sessions/abc123/preview")

    assert response.status_code == 200
    data = response.json()
    assert data["public_url"] == "/api/sessions/abc123/preview/proxy/admin/"


@patch("oma_info_system.api.routes.sessions.preview_manager")
def test_proxy_rewrites_html_absolute_urls_in_subpath_mode(mock_pm, client, monkeypatch):
    """In subpath mode, absolute /admin/ URLs must be prefixed so the browser routes them through the proxy."""
    monkeypatch.delenv("PREVIEW_PUBLIC_BASE", raising=False)

    html = (
        "<html><head>"
        '<link href="/admin/static/foo.css" rel="stylesheet">'
        '<script src="/admin/static/bar.js"></script>'
        "</head><body>content</body></html>"
    )

    class _FakeResponse:
        status_code = 200
        headers = {"content-type": "text/html; charset=utf-8"}
        content = html.encode("utf-8")

    class _FakeAsyncClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def request(self, *a, **kw):
            return _FakeResponse()

    rec = MagicMock()
    rec.state = "preview"
    rec.port = 5599
    mock_pm.get_record.return_value = rec

    with patch("httpx.AsyncClient", _FakeAsyncClient):
        response = client.get("/api/sessions/sess-1/preview/proxy/admin/")

    body = response.text
    prefix = "/api/sessions/sess-1/preview/proxy"
    assert f'"{prefix}/admin/static/foo.css"' in body
    assert f'"{prefix}/admin/static/bar.js"' in body
    # Original absolute URLs must not be present (would 404 on the main domain)
    assert 'href="/admin/static/foo.css"' not in body


@patch("oma_info_system.api.routes.sessions.preview_manager")
def test_proxy_does_not_rewrite_when_public_base_set(mock_pm, client, monkeypatch):
    """Under wildcard subdomain, nginx handles routing — no rewriting needed."""
    monkeypatch.setenv("PREVIEW_PUBLIC_BASE", "preview.ohmyagent.ai")

    html = '<link href="/admin/static/foo.css" rel="stylesheet">'

    class _FakeResponse:
        status_code = 200
        headers = {"content-type": "text/html; charset=utf-8"}
        content = html.encode("utf-8")

    class _FakeAsyncClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def request(self, *a, **kw):
            return _FakeResponse()

    rec = MagicMock()
    rec.state = "preview"
    rec.port = 5599
    mock_pm.get_record.return_value = rec

    with patch("httpx.AsyncClient", _FakeAsyncClient):
        response = client.get("/api/sessions/sess-1/preview/proxy/admin/")

    assert response.text == html


@patch("oma_info_system.api.routes.sessions.preview_manager")
def test_proxy_rewrites_redirect_location_header(mock_pm, client, monkeypatch):
    """Flask's /admin → /admin/ redirect must keep the proxy prefix."""
    monkeypatch.delenv("PREVIEW_PUBLIC_BASE", raising=False)

    class _FakeResponse:
        status_code = 302
        headers = {"location": "/admin/"}
        content = b""

    class _FakeAsyncClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def request(self, *a, **kw):
            return _FakeResponse()

    rec = MagicMock()
    rec.state = "preview"
    rec.port = 5599
    mock_pm.get_record.return_value = rec

    with patch("httpx.AsyncClient", _FakeAsyncClient):
        response = client.get("/api/sessions/sess-1/preview/proxy/admin", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/api/sessions/sess-1/preview/proxy/admin/"
