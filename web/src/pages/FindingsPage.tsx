import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { FindingSummary, listFindings } from "../api";

function FindingCard({
  item,
  caseId,
}: {
  item: FindingSummary;
  caseId: string;
}) {
  const review = item.severity_label === "Review recommended";
  return (
    <article className={`finding-card ${review ? "finding-card--review" : ""}`}>
      <div className="finding-card__top">
        <h3>{item.headline}</h3>
        <span className={`badge ${review ? "badge--warn" : ""}`}>{item.severity_label}</span>
      </div>
      {item.detail && <p className="muted">{item.detail}</p>}
      {item.related_event_ids.length > 0 && (
        <p className="finding-card__links">
          <Link
            to={`/cases/${caseId}/timeline?evidence=${item.related_event_ids[0]}&filter=all`}
          >
            View related activity on Timeline
          </Link>
          <span className="muted">
            {" "}
            · {item.related_event_ids.length} related evidence ref
            {item.related_event_ids.length === 1 ? "" : "s"}
          </span>
        </p>
      )}
    </article>
  );
}

export function FindingsPage() {
  const { caseId } = useParams();
  const [findings, setFindings] = useState<FindingSummary[]>([]);
  const [stories, setStories] = useState<FindingSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!caseId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await listFindings(caseId);
      setFindings(data.findings);
      setStories(data.stories);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!caseId) return null;

  return (
    <div className="findings-page">
      <section className="panel">
        <h1>Findings</h1>
        <p className="muted">
          Things that may need a closer look, plus short activity stories from correlated events.
        </p>
        {loading && <p className="muted">Loading findings…</p>}
        {error && <p className="error">{error}</p>}
        {!loading && !error && findings.length === 0 && stories.length === 0 && (
          <div className="empty">
            <p>No findings yet.</p>
            <p className="muted">
              Import evidence from Overview. After analysis, rule hits and stories appear here.
            </p>
            <Link className="btn btn--primary" to={`/cases/${caseId}/import`}>
              Import evidence
            </Link>
          </div>
        )}
      </section>

      {findings.length > 0 && (
        <section className="panel">
          <h2>Needs attention</h2>
          <p className="muted">Rule-based alerts from the evidence graph.</p>
          <div className="finding-grid">
            {findings.map((f) => (
              <FindingCard key={f.id} item={f} caseId={caseId} />
            ))}
          </div>
        </section>
      )}

      {stories.length > 0 && (
        <section className="panel">
          <h2>Activity stories</h2>
          <p className="muted">
            Connected chains of activity (what the desktop called “incidents”), in plain language.
          </p>
          <div className="finding-grid">
            {stories.map((s) => (
              <FindingCard key={s.id} item={s} caseId={caseId} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
