"""Core application configuration."""

import os
from pathlib import Path

from dotenv import load_dotenv

from oma_info_system import __version__

# Directory holding this package. Resolving from here works both in a source
# checkout and in an installed wheel, unlike a repo-root relative path.
PACKAGE_DIR = Path(__file__).resolve().parent


def _source_root() -> Path | None:
    """Return the checkout root when running from a src/ layout, else None."""
    candidate = PACKAGE_DIR.parent.parent
    return candidate if (candidate / "pyproject.toml").exists() else None


def load_env() -> None:
    """Load .env from the working directory, then from the checkout root."""
    locations = [Path.cwd() / ".env"]
    root = _source_root()
    if root is not None:
        locations.append(root / ".env")

    for env_file in locations:
        if env_file.exists():
            load_dotenv(env_file, override=True)
            print(f"Loaded .env from: {env_file}")
            break


load_env()


def _default_data_dir() -> Path:
    """Pick the runtime data root.

    Prefers an existing ./data in the working directory so a local source
    setup keeps its state, otherwise falls back to the platform user-data
    directory instead of writing inside the installed package.
    """
    local = Path.cwd() / "data"
    if local.exists():
        return local
    xdg = os.getenv("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / "oma-info-system"


def _env_int(name: str, default: int) -> int:
    """Read an int env var, falling back to the default when unset/invalid."""
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


class Settings:
    """Application settings."""

    # Application
    APP_NAME: str = "Info System Agent"
    APP_VERSION: str = __version__
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # Server
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = _env_int("PORT", 8020)

    # OpenAI-compatible LLM configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "")

    # Unified local data root. Relative paths resolve from the working directory.
    _DATA_DIR_VALUE: str = os.getenv("DATA_DIR", "")
    DATA_DIR: Path = Path(os.path.expanduser(_DATA_DIR_VALUE)) if _DATA_DIR_VALUE else _default_data_dir()
    if not DATA_DIR.is_absolute():
        DATA_DIR = Path.cwd() / DATA_DIR
    OUTPUT_DIR: str = str(DATA_DIR / "projects")
    DATABASE_FILE: Path = DATA_DIR / "app.json"
    PREVIEW_STATE_FILE: Path = DATA_DIR / "preview_state.json"
    TRACES_DIR: Path = DATA_DIR / "traces"

    def ensure_directories(self):
        """Ensure required directories exist."""
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        Path(self.OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

    def apply_stored_settings(self):
        from oma_info_system.platform.storage import get_database

        record = get_database(self.DATABASE_FILE).table("settings").get(doc_id=1)
        if not record:
            return
        for key, env_name in {
            "base_url": "OPENAI_BASE_URL",
            "model": "OPENAI_MODEL",
            "api_key": "OPENAI_API_KEY",
            "response_format": "OPENAI_RESPONSE_FORMAT",
        }.items():
            if record.get(key):
                os.environ[env_name] = str(record[key])
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", self.OPENAI_API_KEY)
        self.OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", self.OPENAI_BASE_URL)
        self.OPENAI_MODEL = os.getenv("OPENAI_MODEL", self.OPENAI_MODEL)


settings = Settings()
settings.ensure_directories()
settings.apply_stored_settings()
