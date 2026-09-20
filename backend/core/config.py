"""Core application configuration."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory
BASE_DIR = Path(__file__).resolve().parents[2]


def load_env():
    """Load .env from multiple locations."""
    locations = [
        BASE_DIR / ".env",
        Path.cwd() / ".env",
    ]

    for env_file in locations:
        if env_file.exists():
            load_dotenv(env_file, override=True)
            print(f"Loaded .env from: {env_file}")
            break


load_env()


class Settings:
    """Application settings."""

    # Application
    APP_NAME: str = "Info System Agent"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # Server
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "8020"))

    # OpenAI-compatible LLM configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "")


    # Unified local data root. Relative paths resolve from the repository root.
    _DATA_DIR_VALUE: str = os.getenv("DATA_DIR", "")
    DATA_DIR: Path = Path(os.path.expanduser(_DATA_DIR_VALUE)) if _DATA_DIR_VALUE else BASE_DIR / "data"
    if not DATA_DIR.is_absolute():
        DATA_DIR = BASE_DIR / DATA_DIR
    OUTPUT_DIR: str = str(DATA_DIR / "projects")
    DATABASE_FILE: Path = DATA_DIR / "app.json"
    PREVIEW_STATE_FILE: Path = DATA_DIR / "preview_state.json"
    TRACES_DIR: Path = DATA_DIR / "traces"

    def ensure_directories(self):
        """Ensure required directories exist."""
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        Path(self.OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

    def apply_stored_settings(self):
        from shared.storage.database import get_database

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
