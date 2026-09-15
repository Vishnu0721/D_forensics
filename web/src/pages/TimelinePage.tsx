import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { listEvents, type EventFilter, type EventSummary } from "../api";
import { EventDrawer } from "../components/EventDrawer";

const FILTERS: { id: EventFilter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "user", label: "User actions" },
  { id: "background", label: "Background noise" },
  { id: "findings", label: "Needs a look" },
  { id: "linked", label: "Linked" },
  { id: "unclear", label: "Unclear" },
];

export function TimelinePage() {
  const { caseId = "" } = useParams();
  const [filter, setFilter] = useState<EventFilter>("all");
  const [items, setItems] = useState<EventSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    listEvents(caseId, filter, { limit: 200 })
      .then((page) => {
        if (!cancelled) {
          setItems(page.items);
          setTotal(page.total);
          setError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Could not load timeline");
          setItems([]);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [caseId, filter]);

  return (
    <div>
      <h1>Timeline</h1>
      <p className="lead">Activity in order, as plain sentences.</p>

      <div className="filter-bar" role="tablist" aria-label="Timeline filters">
        {FILTERS.map((f) => (
          <button
            key={f.id}
            type="button"
            role="tab"
            aria-selected={filter === f.id}
            className={
              filter === f.id ? "filter-chip filter-chip--active" : "filter-chip"
            }
            onClick={() => setFilter(f.id)}
          >
            {f.label}
          </button>
        ))}
      </div>

      {loading && <p className="muted">Loading…</p>}
      {error && <p className="status-err">{error}</p>}

      {!loading && !error && items.length === 0 && (
        <section className="empty-state">
          <h2>No activity yet</h2>
          <p className="muted">
            Import evidence and run Analyze to build this timeline.
          </p>
          <Link className="btn btn--primary" to={`/cases/${caseId}/import`}>
            Import evidence
          </Link>
        </section>
      )}

      {!loading && items.length > 0 && (
        <>
          <p className="muted timeline-count">
            Showing {items.length}
            {total !== items.length ? ` of ${total}` : ""}{" "}
            {items.length === 1 ? "event" : "events"}
          </p>
          <ol className="timeline">
            {items.map((ev) => (
              <li key={ev.id}>
                <button
                  type="button"
                  className="timeline-item"
                  onClick={() => setSelectedId(ev.id)}
                >
                  <time className="timeline-item__when">
                    {ev.timestamp ? formatWhen(ev.timestamp) : "Unknown time"}
                  </time>
                  <span className="timeline-item__headline">{ev.headline}</span>
                  {ev.detail && (
                    <span className="timeline-item__detail muted">{ev.detail}</span>
                  )}
                  <span className={`badge badge--${sev(ev.severity_label)}`}>
                    {ev.severity_label}
                  </span>
                </button>
              </li>
            ))}
          </ol>
        </>
      )}

      <EventDrawer
        caseId={caseId}
        eventId={selectedId}
        onClose={() => setSelectedId(null)}
      />
    </div>
  );
}

function formatWhen(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function sev(label: string): string {
  const lower = label.toLowerCase();
  if (lower.includes("warn") || lower.includes("look") || lower.includes("medium")) {
    return "warn";
  }
  if (lower.includes("high") || lower.includes("critical")) return "danger";
  return "ok";
}
