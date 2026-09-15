import { useEffect, useState } from "react";
import { getEvent, type EventDetail } from "../api";

type EventDrawerProps = {
  caseId: string;
  eventId: string | null;
  onClose: () => void;
};

export function EventDrawer({ caseId, eventId, onClose }: EventDrawerProps) {
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
    getEvent(caseId, eventId)
      .then((data) => {
        if (!cancelled) setDetail(data);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Could not load event");
          setDetail(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [caseId, eventId]);

  if (!eventId) return null;

  const technicalEntries = detail
    ? Object.entries(detail.technical).filter(
        ([, v]) => v !== null && v !== undefined && v !== "",
      )
    : [];

  return (
    <div className="drawer-backdrop" onClick={onClose} role="presentation">
      <aside
        className="drawer"
        role="dialog"
        aria-label="Activity details"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="drawer__header">
          <h2>Activity details</h2>
          <button type="button" className="btn btn--ghost" onClick={onClose}>
            Close
          </button>
        </div>

        {loading && <p className="muted">Loading…</p>}
        {error && <p className="status-err">{error}</p>}

        {detail && !loading && (
          <div className="drawer__body">
            <p className="drawer__headline">{detail.headline}</p>
            {detail.detail && <p className="muted">{detail.detail}</p>}
            <div className="drawer__meta">
              <span className={`badge badge--${severityClass(detail.severity_label)}`}>
                {detail.severity_label}
              </span>
              {detail.timestamp && (
                <time dateTime={detail.timestamp}>
                  {formatWhen(detail.timestamp)}
                </time>
              )}
            </div>

            <details className="tech-details">
              <summary>Technical details</summary>
              <dl className="tech-dl">
                <div>
                  <dt>Source</dt>
                  <dd className="mono">{detail.source_type || "—"}</dd>
                </div>
                <div>
                  <dt>Type</dt>
                  <dd className="mono">{detail.event_type || "—"}</dd>
                </div>
                {detail.evidence_id && (
                  <div>
                    <dt>Record id</dt>
                    <dd className="mono">{detail.evidence_id}</dd>
                  </div>
                )}
                {technicalEntries.map(([key, value]) => (
                  <div key={key}>
                    <dt>{key}</dt>
                    <dd className="mono">{formatTech(value)}</dd>
                  </div>
                ))}
              </dl>
            </details>
          </div>
        )}
      </aside>
    </div>
  );
}

function severityClass(label: string): string {
  const lower = label.toLowerCase();
  if (lower.includes("warn") || lower.includes("look") || lower.includes("suspicious")) {
    return "warn";
  }
  if (lower.includes("danger") || lower.includes("critical") || lower.includes("high")) {
    return "danger";
  }
  if (lower.includes("ok") || lower.includes("info") || lower.includes("informational")) {
    return "ok";
  }
  return "neutral";
}

function formatWhen(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function formatTech(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}
