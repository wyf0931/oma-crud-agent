"""Local application settings API."""

import os

from fastapi import APIRouter
from pydantic import BaseModel
from tinydb.table import Document

from backend.core.config import settings
from shared.storage.database import get_database

router = APIRouter(tags=["settings"])


class SettingsUpdate(BaseModel):
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None
    data_dir: str | None = None


def _read() -> dict:
    return dict(get_database(settings.DATABASE_FILE).table("settings").get(doc_id=1) or {})


def _write(data: dict) -> None:
    table = get_database(settings.DATABASE_FILE).table("settings")
    if table.get(doc_id=1):
        table.update(data, doc_ids=[1])
    else:
        table.insert(Document(data, doc_id=1))


@router.get("/settings")
async def get_settings():
    return {
        "base_url": os.getenv("OPENAI_BASE_URL", settings.OPENAI_BASE_URL),
        "model": os.getenv("OPENAI_MODEL", settings.OPENAI_MODEL),
        "api_key_set": bool(os.getenv("OPENAI_API_KEY", settings.OPENAI_API_KEY)),
        "data_dir": str(settings.DATA_DIR),
    }


@router.put("/settings")
async def update_settings(update: SettingsUpdate):
    stored = _read()
    if update.base_url is not None:
        stored["base_url"] = update.base_url.strip()
        os.environ["OPENAI_BASE_URL"] = stored["base_url"]
        settings.OPENAI_BASE_URL = stored["base_url"]
    if update.model is not None:
        stored["model"] = update.model.strip()
        os.environ["OPENAI_MODEL"] = stored["model"]
        settings.OPENAI_MODEL = stored["model"]
    if update.api_key:
        stored["api_key"] = update.api_key.strip()
        os.environ["OPENAI_API_KEY"] = stored["api_key"]
        settings.OPENAI_API_KEY = stored["api_key"]
    if update.data_dir is not None:
        stored["data_dir"] = update.data_dir.strip()
    _write(stored)

    from agent.providers.openai_compatible import reset_provider
    reset_provider()
    return {"status": "saved", "restart_required": update.data_dir is not None}
