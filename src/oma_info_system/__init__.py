"""Info System Agent — generate lightweight internal information systems."""

from importlib.metadata import PackageNotFoundError, version

_DISTRIBUTION_NAME = "ohmyagent-info-system-agent"

try:
    # Single source of truth is the version recorded in the installed
    # distribution metadata, which pyproject.toml owns and a release tag
    # must match.
    __version__ = version(_DISTRIBUTION_NAME)
except PackageNotFoundError:  # pragma: no cover - only when running uninstalled
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
