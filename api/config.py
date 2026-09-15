"""Web-only paths and settings — isolated from the desktop app.

Phase A: ensure directories exist. No database init until a later phase.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Configuration for the web API. Desktop keeps forensics.db / data/."""

    model_config = SettingsConfigDict(
        env_prefix="FORENSICS_WEB_",
        env_file=".env",
        extra="ignore",
    )

    app_name: str = "Digital Forensics Web API"
    app_version: str = "0.1.0-a"
    debug: bool = False

    # Isolated from desktop: forensics.db and data/
    data_root: Path = Field(default=REPO_ROOT / "web_data")
    database_url: str = Field(
        default=f"sqlite:///{(REPO_ROOT / 'web_data' / 'forensics_web.db').as_posix()}"
    )

    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )

    @property
    def evidence_dir(self) -> Path:
        return self.data_root / "evidence"

    @property
    def graphs_dir(self) -> Path:
        return self.data_root / "graphs"

    def ensure_directories(self) -> None:
        """Create empty web_data layout. Does not create or open a database."""
        self.data_root.mkdir(parents=True, exist_ok=True)
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.graphs_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
