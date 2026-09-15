"""Smoke: create case → upload fixture → analyze → read timeline/findings/graph/integrity/export.

Run from repo root:
  $env:PYTHONPATH = (Get-Location).Path
  python api/smoke_phase_b_j.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from api.main import app  # noqa: E402

FIXTURE = REPO / "web" / "fixtures" / "sample_evidence.json"


def main() -> None:
    assert FIXTURE.exists(), f"Missing fixture: {FIXTURE}"
    client = TestClient(app)

    h = client.get("/health")
    assert h.status_code == 200, h.text
    assert h.json()["phase"] == "P7", h.json()
    assert "database_url" not in h.json(), "health must not leak paths by default"
    print("OK health phase P7 (paths hidden)")

    meta = client.get("/api/v1/meta")
    assert meta.status_code == 200
    assert meta.json()["features"]["cases"] is True
    print("OK meta")

    created = client.post(
        "/api/v1/cases",
        json={"name": "Smoke B-J", "description": "Automated smoke"},
    )
    assert created.status_code == 201, created.text
    case_id = created.json()["id"]
    print("OK create case", case_id)

    with FIXTURE.open("rb") as f:
        up = client.post(
            f"/api/v1/cases/{case_id}/evidence",
            files={"file": ("sample_evidence.json", f, "application/json")},
        )
    assert up.status_code == 201, up.text
    print("OK upload", up.json()["filename"])

    job = client.post(f"/api/v1/cases/{case_id}/analyze", json={})
    assert job.status_code == 202, job.text
    job_id = job.json()["id"]

    for _ in range(60):
        st = client.get(f"/api/v1/jobs/{job_id}")
        assert st.status_code == 200
        body = st.json()
        if body["status"] in ("completed", "failed"):
            break
        time.sleep(0.25)
    else:
        raise AssertionError("Job timed out")

    assert body["status"] == "completed", body
    print("OK analyze", body.get("result_summary"))

    detail = client.get(f"/api/v1/cases/{case_id}")
    assert detail.status_code == 200
    d = detail.json()
    assert d["event_count"] >= 1, d
    assert d.get("next_step"), d
    print("OK overview events=", d["event_count"], "next=", d["next_step"][:60])

    events = client.get(f"/api/v1/cases/{case_id}/events?filter=all&limit=50")
    assert events.status_code == 200
    assert events.json()["total"] >= 1
    print("OK timeline", events.json()["total"])

    findings = client.get(f"/api/v1/cases/{case_id}/findings")
    assert findings.status_code == 200
    print(
        "OK findings",
        len(findings.json()["findings"]),
        "stories",
        len(findings.json()["stories"]),
    )

    graph = client.get(f"/api/v1/cases/{case_id}/graph?view=simple")
    assert graph.status_code == 200
    print("OK graph nodes", len(graph.json()["nodes"]), "edges", len(graph.json()["edges"]))

    integ = client.post(f"/api/v1/cases/{case_id}/integrity")
    assert integ.status_code == 200
    assert integ.json()["items"], integ.text
    assert "status_label" in integ.json()["items"][0]
    print("OK integrity", integ.json()["items"][0]["status_label"])

    md = client.get(f"/api/v1/cases/{case_id}/export?format=markdown")
    assert md.status_code == 200
    assert "Investigation report" in md.text or "Case report" in md.text
    print("OK export markdown")

    bridge = client.get("/api/v1/bridge/desktop")
    assert bridge.status_code == 200
    print("OK bridge scan", len(bridge.json()["items"]), "folders")

    live = client.get(f"/api/v1/cases/{case_id}/live")
    assert live.status_code == 200
    assert "this_case_active" in live.json()
    print("OK live status")

    deleted = client.delete(f"/api/v1/cases/{case_id}")
    assert deleted.status_code == 204, deleted.text
    gone = client.get(f"/api/v1/cases/{case_id}")
    assert gone.status_code == 404
    print("OK delete investigation")

    print("OK phase B–J + publish polish smoke")


if __name__ == "__main__":
    main()
