"""Product meta for the web UI (IA + phase flags)."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1")


@router.get("/meta")
def product_meta() -> dict:
    """Client can use this to show nav labels and feature flags."""
    return {
        "product_name": "Digital Forensics",
        "tagline": "Investigate evidence clearly",
        "theme": "light",
        "mvp": "offline_import",
        "live_agent": False,
        "auth_required": False,
        "navigation": {
            "primary": [
                {"id": "overview", "label": "Overview"},
                {"id": "timeline", "label": "Timeline"},
                {"id": "connections", "label": "Connections"},
            ],
            "secondary": [
                {"id": "findings", "label": "Findings"},
                {"id": "integrity", "label": "Integrity"},
                {"id": "settings", "label": "Settings"},
            ],
        },
        "renames": {
            "needs_attention": "Findings",
            "incident_summary": "Activity stories",
            "offline_evidence": "Import evidence",
        },
        "phases": {
            "current": 3,
            "next": 4,
            "implemented": [
                "foundations",
                "health",
                "meta",
                "openapi_draft",
                "cases",
                "evidence_upload",
                "analysis_jobs",
                "events",
                "findings",
                "graph",
                "integrity",
                "case_home_ui",
                "import_wizard",
                "timeline_ui",
                "findings_ui",
            ],
        },
    }
