"""Liveness and readiness."""

from __future__ import annotations

from fastapi import APIRouter

from api.config import get_settings

router = APIRouter()


@router.get("/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "phase": 7,
        "data_root": str(settings.data_root),
        "database_url": settings.database_url,
    }
