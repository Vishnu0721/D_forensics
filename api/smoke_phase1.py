"""Smoke test for Phase 1 API (cases → upload → analyze → reads)."""

from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from api.main import app


def main() -> None:
    client = TestClient(app)
    health = client.get("/health").json()
    assert health["phase"] == 3, health

    created = client.post(
        "/api/v1/cases",
        json={"name": "Phase1 Smoke", "description": "API check"},
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
    print("upload", upload.json()["filename"], upload.json()["sha256_hash"][:12])

    job = client.post(f"/api/v1/cases/{case_id}/analyze", json={}).json()
    print("job queued", job["id"])
    final = None
    for _ in range(80):
        final = client.get(f"/api/v1/jobs/{job['id']}").json()
        if final["status"] in ("completed", "failed"):
            break
        time.sleep(0.35)
    assert final is not None
    print("job", final["status"], final.get("error"), final.get("result_summary"))
    assert final["status"] == "completed", final

    detail = client.get(f"/api/v1/cases/{case_id}").json()
    print(
        "detail",
        "events=",
        detail["event_count"],
        "findings=",
        detail["finding_count"],
        "stories=",
        detail["story_count"],
    )
    assert detail["event_count"] > 0

    events = client.get(f"/api/v1/cases/{case_id}/events").json()
    print("events", events["total"], events["items"][0]["headline"])
    findings = client.get(f"/api/v1/cases/{case_id}/findings").json()
    print("findings", len(findings["findings"]), "stories", len(findings["stories"]))
    graph = client.get(f"/api/v1/cases/{case_id}/graph?view=simple").json()
    print("graph", len(graph["nodes"]), "nodes", len(graph["edges"]), "edges")
    integrity = client.post(f"/api/v1/cases/{case_id}/integrity").json()
    print("integrity", integrity["items"][0]["status_label"])
    print("OK")


if __name__ == "__main__":
    main()
