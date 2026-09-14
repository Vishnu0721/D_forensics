"""Per-case web metadata (mode, tour flags) — stored under web_data only."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from api.config import get_settings


def _meta_path(case_id: str) -> Path:
    path = get_settings().data_root / "cases" / case_id
    path.mkdir(parents=True, exist_ok=True)
    return path / "meta.json"


def load_case_meta(case_id: str) -> dict[str, Any]:
    path = _meta_path(case_id)
    if not path.exists():
        return {"mode": "imported", "tour_seen": False}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"mode": "imported", "tour_seen": False}
        data.setdefault("mode", "imported")
        data.setdefault("tour_seen", False)
        return data
    except Exception:
        return {"mode": "imported", "tour_seen": False}


def save_case_meta(case_id: str, **updates: Any) -> dict[str, Any]:
    data = load_case_meta(case_id)
    data.update(updates)
    path = _meta_path(case_id)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data
