"""Product meta for the UI — Phase A clarity contract + live feature flags."""

from __future__ import annotations

from fastapi import APIRouter

from api import __phase__, __version__

router = APIRouter(prefix="/api/v1", tags=["meta"])

NAV_PRIMARY = [
    {"id": "overview", "label": "Overview", "path": "", "job": "What happened? What should I do next?"},
    {"id": "timeline", "label": "Timeline", "path": "timeline", "job": "Activity in order, as plain sentences"},
    {
        "id": "connections",
        "label": "Connections",
        "path": "connections",
        "job": "Who/what is linked (Simple graph by default)",
    },
]

NAV_SECONDARY = [
    {"id": "import", "label": "Import", "path": "import", "job": "Bring evidence files into this case"},
    {"id": "findings", "label": "Findings", "path": "findings", "job": "What needs a look + activity stories"},
    {"id": "integrity", "label": "Integrity", "path": "integrity", "job": "Are preserved files still intact?"},
    {"id": "settings", "label": "Settings", "path": "settings", "job": "About / theme notes"},
]

GLOSSARY = [
    {"avoid": "Evidence Artifacts", "prefer": "Saved records"},
    {"avoid": "Relationships", "prefer": "Links"},
    {"avoid": "Potential Incidents", "prefer": "Activity stories"},
    {"avoid": "Suspicious / Needs attention", "prefer": "Needs a look"},
    {"avoid": "Offline Evidence (Advanced)", "prefer": "Import evidence"},
    {"avoid": "User Activities", "prefer": "User actions"},
    {"avoid": "Background", "prefer": "Background noise"},
    {"avoid": "Evidence Graph", "prefer": "Connections"},
    {"avoid": "Incident Summary", "prefer": "Activity stories"},
]

PRINCIPLES = [
    "One job per screen",
    "Plain language first — technical detail is optional",
    "No dual activity lists",
    "No hash-first tables",
    "Overview answers what next — not seven jargon counters",
    "Light white + blue theme",
]


@router.get("/meta")
def get_meta() -> dict:
    return {
        "phase": __phase__,
        "version": __version__,
        "product_name": "Digital Forensics",
        "theme_default": "light",
        "theme_accent": "white_blue",
        "mvp_focus": "import_first",
        "data_isolation": "web_data_only",
        "principles": PRINCIPLES,
        "nav": {"primary": NAV_PRIMARY, "secondary": NAV_SECONDARY},
        "glossary": GLOSSARY,
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
        "message": (
            "Investigation web app using the same forensic pipeline as the desktop app. "
            "Data stays in web_data/."
        ),
    }
