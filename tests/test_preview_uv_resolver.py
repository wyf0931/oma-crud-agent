"""Tests for uv binary resolution used by the preview endpoint."""

import pytest


def _reload_resolver():
    """Return the resolver; it reads environment and filesystem state per call."""
    from oma_info_system.api.routes.sessions import _resolve_uv_bin

    return _resolve_uv_bin


def test_resolve_uv_bin_uses_env_override(monkeypatch, tmp_path):
    fake_uv = tmp_path / "uv"
    fake_uv.write_text("#!/bin/sh\n")
    monkeypatch.setenv("UV_BIN", str(fake_uv))

    resolver = _reload_resolver()
    assert resolver() == str(fake_uv)


def test_resolve_uv_bin_falls_back_to_local_install(monkeypatch, tmp_path):
    """When UV_BIN isn't set and `which` fails, ~/.local/bin/uv is checked."""
    fake_home = tmp_path / "home"
    (fake_home / ".local" / "bin").mkdir(parents=True)
    fake_uv = fake_home / ".local" / "bin" / "uv"
    fake_uv.write_text("")

    monkeypatch.delenv("UV_BIN", raising=False)
    monkeypatch.setenv("HOME", str(fake_home))
    # `which` should not find anything
    monkeypatch.setattr("shutil.which", lambda _: None)

    resolver = _reload_resolver()
    assert resolver() == str(fake_uv)


def test_resolve_uv_bin_500s_when_missing(monkeypatch, tmp_path):
    from fastapi import HTTPException

    monkeypatch.delenv("UV_BIN", raising=False)
    monkeypatch.setattr("shutil.which", lambda _: None)
    # Point HOME and /usr/local/bin candidates at empty dirs
    fake_home = tmp_path / "empty_home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr("oma_info_system.api.routes.sessions.Path.exists", lambda self: False)

    resolver = _reload_resolver()
    with pytest.raises(HTTPException) as exc:
        resolver()
    assert exc.value.status_code == 500
    assert "uv" in exc.value.detail.lower()
