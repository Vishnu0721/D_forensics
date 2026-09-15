"""Phase I — import desktop evidence folders into web_data (copy, never share DB)."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from api.config import REPO_ROOT, get_settings
from core.services.ingestion import ingest_preserved_evidence

EVIDENCE_EXTENSIONS = {".json", ".csv", ".txt", ".log", ".evtx"}


def desktop_evidence_root() -> Path:
    return REPO_ROOT / "data" / "evidence"


def resolve_source_dir(source_dir: str) -> Path:
    raw = Path(source_dir)
    path = raw if raw.is_absolute() else (REPO_ROOT / raw).resolve()
    if not path.exists() or not path.is_dir():
        raise ValueError(f"Source folder not found: {path}")
    # Safety: must stay under repo (desktop data/ or already under web_data)
    try:
        path.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise ValueError("Source folder must be inside the project repository.") from exc
    return path


def scan_desktop_evidence() -> list[dict]:
    root = desktop_evidence_root()
    if not root.exists():
        return []
    items: list[dict] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        files = [
            p
            for p in child.rglob("*")
            if p.is_file() and p.suffix.lower() in EVIDENCE_EXTENSIONS
        ]
        if files:
            items.append(
                {
                    "case_folder": child.name,
                    "path": str(child.resolve()),
                    "file_count": len(files),
                }
            )
    return items


def import_desktop_folder(db: Session, case_id: str, source_dir: str) -> dict:
    """Copy desktop evidence files into web case via the same ingest path as uploads."""
    settings = get_settings()
    folder = resolve_source_dir(source_dir)
    files = sorted(
        p
        for p in folder.rglob("*")
        if p.is_file() and p.suffix.lower() in EVIDENCE_EXTENSIONS
    )
    if not files:
        raise ValueError("No evidence files (.json/.csv/.log/.txt/.evtx) found in that folder.")

    imported = []
    for path in files[:100]:
        artifact = ingest_preserved_evidence(
            db=db,
            case_id=case_id,
            source_file_path=str(path),
            source_type="offline_report",
            actor="desktop_bridge",
            evidence_root=str(settings.evidence_dir),
        )
        imported.append({"id": artifact.id, "filename": artifact.filename})

    return {
        "source_dir": str(folder),
        "imported_count": len(imported),
        "items": imported,
        "note": "Files were copied into web_data/. Desktop forensics.db was not opened.",
    }
