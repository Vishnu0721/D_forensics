"""FastAPI application entry."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import __version__
from api.config import get_settings
from api.db import init_web_db
from api.routes import (
    analysis_jobs,
    cases,
    evidence,
    events,
    export,
    findings,
    graph,
    health,
    integrity,
    live,
    meta,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    get_settings().ensure_directories()
    init_web_db()
    yield


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description=(
        "Light-theme investigation web API on feature/webapp. "
        "Offline import + optional local live agent. "
        "Uses web_data/ only — does not touch the desktop forensics.db."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(meta.router)
app.include_router(cases.router)
app.include_router(evidence.router)
app.include_router(analysis_jobs.router)
app.include_router(events.router)
app.include_router(findings.router)
app.include_router(graph.router)
app.include_router(integrity.router)
app.include_router(export.router)
app.include_router(live.router)
