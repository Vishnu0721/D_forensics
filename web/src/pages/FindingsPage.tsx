import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { listFindings, type FindingsResponse } from "../api";

export function FindingsPage() {
  const { caseId = "" } = useParams();
  const [data, setData] = useState<FindingsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listFindings(caseId)
      .then((res) => {
        if (!cancelled) {
          setData(res);
          setError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Could not load findings");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [caseId]);

  const empty =
    data && data.findings.length === 0 && data.stories.length === 0;

  return (
    <div>
      <h1>Findings</h1>
      <p className="lead">What needs a look, plus activity stories.</p>

      {loading && <p className="muted">Loading…</p>}
      {error && <p className="status-err">{error}</p>}

      {empty && (
        <section className="empty-state">
          <h2>Nothing to review yet</h2>
          <p className="muted">Run Analyze after importing evidence.</p>
          <Link className="btn btn--primary" to={`/cases/${caseId}/import`}>
            Import evidence
          </Link>
        </section>
      )}

      {data && data.findings.length > 0 && (
        <section className="panel">
          <h2>Needs a look</h2>
          <ul className="finding-list">
            {data.findings.map((f) => (
              <li key={f.id} className="finding-item">
                <span className={`badge badge--${sev(f.severity_label)}`}>
                  {f.severity_label}
                </span>
                <div>
                  <strong>{f.headline}</strong>
                  {f.detail && <p className="muted">{f.detail}</p>}
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {data && data.stories.length > 0 && (
        <section className="panel">
          <h2>Activity stories</h2>
          <ul className="finding-list">
            {data.stories.map((f) => (
              <li key={f.id} className="finding-item">
                <span className={`badge badge--${sev(f.severity_label)}`}>
                  {f.severity_label}
                </span>
                <div>
                  <strong>{f.headline}</strong>
                  {f.detail && <p className="muted">{f.detail}</p>}
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function sev(label: string): string {
  const lower = label.toLowerCase();
  if (lower.includes("warn") || lower.includes("look") || lower.includes("medium")) {
    return "warn";
  }
  if (lower.includes("high") || lower.includes("critical")) return "danger";
  return "ok";
}
