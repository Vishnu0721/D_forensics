"""Case export download (Phase 5)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from api.db import get_db
from api.serializers import get_case_or_404
from api.services.export import build_case_export

router = APIRouter(prefix="/api/v1/cases/{case_id}/export", tags=["export"])


@router.get("")
def export_case(
    case_id: str,
    format: str = Query(default="markdown", pattern="^(markdown|html)$"),
    db: Session = Depends(get_db),
):
    case = get_case_or_404(db, case_id)
    try:
        body = build_case_export(db, case, fmt=format)  # type: ignore[arg-type]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Export failed: {exc}") from exc

    if format == "html":
        media = "text/html; charset=utf-8"
        filename = f"{case.name.replace(' ', '_')}_report.html"
    else:
        media = "text/markdown; charset=utf-8"
        filename = f"{case.name.replace(' ', '_')}_report.md"

    return Response(
        content=body,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
