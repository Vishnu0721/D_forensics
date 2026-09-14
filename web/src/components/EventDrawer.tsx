import { useEffect, useState } from "react";
import { EventDetail, getEvent } from "../api";

const CLASS_LABELS: Record<string, string> = {
  USER_ACTIVITY: "User action",
  BACKGROUND_ACTIVITY: "Background noise",
  SUSPICIOUS_ACTIVITY: "Needs attention",
  CORRELATED_ACTIVITY: "Linked activity",
  UNKNOWN: "Unclear",
};

type Props = {
  caseId: string;
  eventId: string | null;
  onClose: () => void;
};

export function EventDrawer({ caseId, eventId, onClose }: Props) {
  const [detail, setDetail] = useState<EventDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!eventId) {
      setDetail(null);
      setError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    (async () => {
      try {
        const data = await getEvent(caseId, eventId);
        if (!cancelled) setDetail(data);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [caseId, eventId]);

  if (!eventId) return null;

  return (
    <aside className="drawer" aria-label="Event details">
      <div className="drawer__header">
        <h2>What happened</h2>
        <button type="button" className="btn btn--ghost drawer__close" onClick={onClose}>
          Close
        </button>
      </div>

      {loading && <p className="muted">Loading details…</p>}
      {error && <p className="error">{error}</p>}

      {detail && !loading && (
        <div className="drawer__body">
          <p className="drawer__headline">{detail.headline}</p>
          <p className="muted">{detail.detail}</p>
          <div className="drawer__meta">
            <span className="badge">{detail.severity_label}</span>
            <span className="badge">
              {CLASS_LABELS[detail.classification] || detail.classification}
            </span>
          </div>
          <dl className="facts">
            <div>
              <dt>When</dt>
              <dd>
                {detail.timestamp
                  ? new Date(detail.timestamp).toLocaleString()
                  : "Unknown"}
              </dd>
            </div>
            <div>
              <dt>Type</dt>
              <dd>
                {detail.source_type} · {detail.event_type}
              </dd>
            </div>
          </dl>

          <details className="tech-details">
            <summary>Technical details</summary>
            <dl className="tech-grid">
              {Object.entries(detail.technical)
                .filter(([, v]) => v !== null && v !== undefined && v !== "")
                .map(([key, value]) => (
                  <div key={key}>
                    <dt>{key}</dt>
                    <dd className="mono">{String(value)}</dd>
                  </div>
                ))}
            </dl>
          </details>
        </div>
      )}
    </aside>
  );
}
