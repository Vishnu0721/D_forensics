"""Liveness — reports current phase."""

from __future__ import annotations

from fastapi import APIRouter

from api import __phase__, __version__
from api.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "phase": __phase__,
        "version": __version__,
        "data_root": str(settings.data_root),
        "database_url": settings.database_url,
        "features": {
            "cases": True,
            "import": True,
            "analysis": True,
            "timeline": True,
            "connections": True,
            "findings": True,
            "integrity": True,
            "live": True,
            "export": True,
            "desktop_bridge": True,
        },
    }
