"""Liveness — safe by default (no local paths unless FORENSICS_WEB_EXPOSE_PATHS)."""

from __future__ import annotations

from fastapi import APIRouter

from api import __phase__, __product_name__, __tagline__, __version__
from api.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    settings = get_settings()
    payload: dict = {
        "status": "ok",
        "phase": __phase__,
        "version": __version__,
        "product_name": __product_name__,
        "tagline": __tagline__,
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
            "delete_case": True,
        },
    }
    if settings.expose_paths or settings.debug:
        payload["data_root"] = str(settings.data_root)
        payload["database_url"] = settings.database_url
    return payload
