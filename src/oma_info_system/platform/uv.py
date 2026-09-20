"""Locate the uv binary used to launch generated projects."""

import os
import shutil
from pathlib import Path


class UVNotFoundError(RuntimeError):
    """Raised when the uv executable cannot be located."""


def resolve_uv_bin() -> str:
    """Return the path to the uv binary.

    Service managers do not inherit the interactive shell PATH, so a bare
    "uv" can fail even when uv is installed. The UV_BIN override is checked
    first, then PATH, then the usual install locations.
    """
    candidates = [
        os.environ.get("UV_BIN"),
        shutil.which("uv"),
        os.path.expanduser("~/.local/bin/uv"),
        "/usr/local/bin/uv",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    raise UVNotFoundError("uv binary not found. Set UV_BIN or install uv to ~/.local/bin/uv.")
