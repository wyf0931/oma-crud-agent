"""Health check endpoints."""

from fastapi import APIRouter

from oma_info_system.config import settings

router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "version": settings.APP_VERSION,
    }


@router.get("/config")
async def get_config():
    """Get public configuration."""
    return {
        "version": settings.APP_VERSION,
        "features": {
            "yolo_mode": True,
            "hitl_mode": True,
        },
    }
