"""Tests for uv binary resolution and the preview endpoint's error contract."""

import pytest

from oma_info_system.platform.uv import UVNotFoundError, resolve_uv_bin


def test_resolve_uv_bin_uses_env_override(monkeypatch, tmp_path):
    fake_uv = tmp_path / "uv"
    fake_uv.write_text("#!/bin/sh\n")
    monkeypatch.setenv("UV_BIN", str(fake_uv))

    assert resolve_uv_bin() == str(fake_uv)


def test_resolve_uv_bin_falls_back_to_local_install(monkeypatch, tmp_path):
    """When UV_BIN isn't set and `which` fails, ~/.local/bin/uv is checked."""
    fake_home = tmp_path / "home"
    (fake_home / ".local" / "bin").mkdir(parents=True)
    fake_uv = fake_home / ".local" / "bin" / "uv"
    fake_uv.write_text("")

    monkeypatch.delenv("UV_BIN", raising=False)
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr("shutil.which", lambda _: None)

    assert resolve_uv_bin() == str(fake_uv)


def test_resolve_uv_bin_raises_when_missing(monkeypatch, tmp_path):
    monkeypatch.delenv("UV_BIN", raising=False)
    monkeypatch.setattr("shutil.which", lambda _: None)
    fake_home = tmp_path / "empty_home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr("oma_info_system.platform.uv.Path.exists", lambda self: False)

    with pytest.raises(UVNotFoundError):
        resolve_uv_bin()


def test_start_preview_returns_500_when_uv_missing(monkeypatch):
    """The route translates a missing uv binary into a 500 response."""
    from fastapi import HTTPException
    from fastapi.testclient import TestClient

    from oma_info_system.api.app import create_app
    from oma_info_system.api.routes import preview as preview_routes

    session = {"id": "s1", "status": "completed", "project_path": __file__}

    monkeypatch.setattr(preview_routes.session_manager, "get", lambda _sid: session)

    def _boom() -> str:
        raise UVNotFoundError("uv binary not found")

    monkeypatch.setattr(preview_routes, "resolve_uv_bin", _boom, raising=False)

    client = TestClient(create_app())
    resp = client.post("/api/sessions/s1/preview")

    assert resp.status_code == 500
    assert "uv binary not found" in resp.json()["detail"]
    assert HTTPException is not None
