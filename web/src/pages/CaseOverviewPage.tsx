import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  CaseDetail,
  EvidenceSummary,
  getCase,
  listEvidence,
  pollJob,
  startAnalysis,
} from "../api";

export function CaseOverviewPage() {
  const { caseId } = useParams();
  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [evidence, setEvidence] = useState<EvidenceSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [jobMessage, setJobMessage] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!caseId) return;
    const [caseData, evidenceData] = await Promise.all([
      getCase(caseId),
      listEvidence(caseId),
    ]);
    setDetail(caseData);
    setEvidence(evidenceData.items);
  }, [caseId]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await refresh();
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [refresh]);

  async function onAnalyzeOnly() {
    if (!caseId) return;
    setBusy(true);
    setError(null);
    try {
      const job = await startAnalysis(caseId);
      const done = await pollJob(job.id, (j) => setJobMessage(j.message));
      if (done.status === "failed") {
        throw new Error(done.error || "Analysis failed");
      }
      setJobMessage("Analysis complete");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  if (!detail && !error) {
    return <p className="muted">Loading case…</p>;
  }

  if (error && !detail) {
    return <p className="error">{error}</p>;
  }

  if (!detail || !caseId) return null;

  return (
    <div className="overview">
      <section className="panel">
        <div className="overview__header">
          <div>
            <span className="badge">{detail.mode === "live" ? "Live" : "Imported"}</span>
            <h1>{detail.name}</h1>
            <p className="muted">{detail.description || "No description"}</p>
          </div>
        </div>

        <div className="stat-row">
          <div className="stat">
            <span className="stat__value">{detail.evidence_count}</span>
            <span className="stat__label">Evidence</span>
          </div>
          <div className="stat">
            <span className="stat__value">{detail.event_count}</span>
            <span className="stat__label">Events</span>
          </div>
          <div className="stat">
            <span className="stat__value">{detail.relationship_count}</span>
            <span className="stat__label">Links</span>
          </div>
          <div className="stat">
            <span className="stat__value">{detail.finding_count}</span>
            <span className="stat__label">Findings</span>
          </div>
        </div>

        {detail.last_analysis_at && (
          <p className="muted">
            Last analysis: {new Date(detail.last_analysis_at).toLocaleString()}
          </p>
        )}

        <div className="overview__cta">
          <Link className="btn btn--primary" to={`/cases/${caseId}/import`}>
            Import evidence
          </Link>
          <Link className="btn btn--ghost" to={`/cases/${caseId}/timeline`}>
            Open Timeline
          </Link>
          <Link className="btn btn--ghost" to={`/cases/${caseId}/findings`}>
            Open Findings
          </Link>
        </div>
      </section>

      <section className="panel">
        <h2>Evidence in this case</h2>
        <p className="muted">
          Preserved hashed copies. Use Import evidence for the guided wizard.
        </p>
        {evidence.length > 0 && (
          <button
            className="btn btn--ghost"
            type="button"
            disabled={busy}
            onClick={onAnalyzeOnly}
          >
            {busy ? "Re-analyzing…" : "Re-analyze case"}
          </button>
        )}
        {jobMessage && <p className="muted">{jobMessage}</p>}
        {error && <p className="error">{error}</p>}

        {evidence.length === 0 ? (
          <div className="empty">
            <p>No evidence yet.</p>
            <p className="muted">Import a file to populate Timeline and Findings.</p>
            <Link className="btn btn--primary" to={`/cases/${caseId}/import`}>
              Start import wizard
            </Link>
          </div>
        ) : (
          <ul className="evidence-list">
            {evidence.map((item) => (
              <li key={item.id}>
                <strong>{item.filename}</strong>
                <span className="muted">
                  {item.status_label} · {item.source_type} · {item.sha256_hash.slice(0, 12)}…
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {detail.top_findings.length > 0 && (
        <section className="panel">
          <div className="panel__row">
            <h2>Top findings</h2>
            <Link to={`/cases/${caseId}/findings`}>View all</Link>
          </div>
          <ul className="finding-list">
            {detail.top_findings.map((f) => (
              <li key={f.id}>
                <strong>{f.headline}</strong>
                <span className="badge">{f.severity_label}</span>
                {f.detail && <p className="muted">{f.detail}</p>}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
