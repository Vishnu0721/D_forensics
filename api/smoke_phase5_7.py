"""Smoke tests for Phase 1–7 web API (feature/webapp / web_data only)."""

from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from api.main import app
from api.services.live_monitor import live_monitor


def main() -> None:
    # Ensure monitor stopped between runs
    try:
        live_monitor.stop()
    except Exception:
        pass

    client = TestClient(app)
    health = client.get("/health").json()
    assert health["phase"] == 7, health
    meta = client.get("/api/v1/meta").json()
    assert meta["live_agent"] is True
    assert meta["phases"]["current"] == 7

    created = client.post(
        "/api/v1/cases",
        json={"name": "Phase567 Smoke", "description": "Reliability check"},
    )
    assert created.status_code == 201, created.text
    case_id = created.json()["id"]
    print("case", case_id)

    fixture = Path("web/fixtures/sample_evidence.json")
    with fixture.open("rb") as handle:
        upload = client.post(
            f"/api/v1/cases/{case_id}/evidence",
            files={"file": ("sample_evidence.json", handle, "application/json")},
        )
    assert upload.status_code == 201, upload.text

    job = client.post(f"/api/v1/cases/{case_id}/analyze", json={}).json()
    final = None
    for _ in range(80):
        final = client.get(f"/api/v1/jobs/{job['id']}").json()
        if final["status"] in ("completed", "failed"):
            break
        time.sleep(0.35)
    assert final and final["status"] == "completed", final

    # Concurrent analysis: second request while first running should 409
    j1 = client.post(f"/api/v1/cases/{case_id}/analyze", json={})
    j2 = client.post(f"/api/v1/cases/{case_id}/analyze", json={})
    assert j1.status_code == 202, j1.text
    assert j2.status_code == 409, j2.text
    # Wait for j1
    jid = j1.json()["id"]
    for _ in range(80):
        st = client.get(f"/api/v1/jobs/{jid}").json()
        if st["status"] in ("completed", "failed"):
            break
        time.sleep(0.35)
    assert st["status"] == "completed", st

    # Export
    md = client.get(f"/api/v1/cases/{case_id}/export?format=markdown")
    assert md.status_code == 200, md.text
    assert "Case report" in md.text
    html = client.get(f"/api/v1/cases/{case_id}/export?format=html")
    assert html.status_code == 200
    assert "<html" in html.text.lower()
    print("export ok")

    # Live start/stop (brief)
    live = client.post(f"/api/v1/cases/{case_id}/live/start")
    assert live.status_code == 200, live.text
    assert live.json()["running"] is True
    # Cannot analyze while live
    blocked = client.post(f"/api/v1/cases/{case_id}/analyze", json={})
    assert blocked.status_code == 409
    time.sleep(2.5)
    stopped = client.post(f"/api/v1/cases/{case_id}/live/stop")
    assert stopped.status_code == 200
    assert stopped.json()["running"] is False
    print("live ok", live.json().get("events_captured"))

    # Graph caps still return
    graph = client.get(f"/api/v1/cases/{case_id}/graph?view=simple")
    assert graph.status_code == 200
    print("OK phase 5–7")


if __name__ == "__main__":
    main()
