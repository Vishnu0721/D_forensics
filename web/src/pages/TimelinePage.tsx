import { useCallback, useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import {
  EventFilter,
  EventSummary,
  listEvents,
} from "../api";
import { EventDrawer } from "../components/EventDrawer";

const FILTERS: { value: EventFilter; label: string }[] = [
  { value: "all", label: "All activity" },
  { value: "user", label: "User actions" },
  { value: "findings", label: "Needs attention" },
  { value: "linked", label: "Linked activity" },
  { value: "unclear", label: "Unclear" },
];

const CLASS_LABELS: Record<string, string> = {
  USER_ACTIVITY: "User action",
  BACKGROUND_ACTIVITY: "Background",
  SUSPICIOUS_ACTIVITY: "Needs attention",
  CORRELATED_ACTIVITY: "Linked",
  UNKNOWN: "Unclear",
};

export function TimelinePage() {
  const { caseId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const filter = (searchParams.get("filter") as EventFilter) || "all";
  const selectedId = searchParams.get("event");
  const evidenceId = searchParams.get("evidence") || undefined;

  const [items, setItems] = useState<EventSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!caseId) return;
    setLoading(true);
    setError(null);
    try {
      const page = await listEvents(caseId, {
        filter,
        evidenceId,
        limit: 200,
      });
      setItems(page.items);
      setTotal(page.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [caseId, filter, evidenceId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!evidenceId || selectedId || items.length === 0) return;
    const params = new URLSearchParams(searchParams);
    params.set("event", items[0].id);
    setSearchParams(params, { replace: true });
  }, [evidenceId, selectedId, items, searchParams, setSearchParams]);

  function setFilter(next: EventFilter) {
    const params = new URLSearchParams(searchParams);
    if (next === "all") params.delete("filter");
    else params.set("filter", next);
    setSearchParams(params);
  }

  function selectEvent(id: string) {
    const params = new URLSearchParams(searchParams);
    params.set("event", id);
    setSearchParams(params);
  }

  function clearSelection() {
    const params = new URLSearchParams(searchParams);
    params.delete("event");
    setSearchParams(params);
  }

  if (!caseId) return null;

  return (
    <div className={`timeline-layout ${selectedId ? "timeline-layout--split" : ""}`}>
      <section className="panel timeline-panel">
        <header className="timeline-header">
          <div>
            <h1>Timeline</h1>
            <p className="muted">One chronological story of what happened in this case.</p>
            {evidenceId && (
              <p className="muted">
                Showing events from one evidence file.{" "}
                <button
                  type="button"
                  className="linkish"
                  onClick={() => {
                    const params = new URLSearchParams(searchParams);
                    params.delete("evidence");
                    setSearchParams(params);
                  }}
                >
                  Clear evidence filter
                </button>
              </p>
            )}
          </div>
          <p className="muted">{loading ? "Loading…" : `${total} event${total === 1 ? "" : "s"}`}</p>
        </header>

        <div className="filter-bar" role="tablist" aria-label="Timeline filters">
          {FILTERS.map((f) => (
            <button
              key={f.value}
              type="button"
              role="tab"
              aria-selected={filter === f.value}
              className={
                filter === f.value ? "filter-chip filter-chip--active" : "filter-chip"
              }
              onClick={() => setFilter(f.value)}
            >
              {f.label}
            </button>
          ))}
        </div>

        {error && <p className="error">{error}</p>}

        {!loading && !error && items.length === 0 && (
          <div className="empty">
            <p>No events in this view.</p>
            <p className="muted">
              Import evidence from Overview, or try the “All activity” filter.
            </p>
          </div>
        )}

        <ol className="timeline-list">
          {items.map((ev) => {
            const active = ev.id === selectedId;
            const time = ev.timestamp
              ? new Date(ev.timestamp).toLocaleString(undefined, {
                  month: "short",
                  day: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                  second: "2-digit",
                })
              : "Unknown time";
            return (
              <li key={ev.id}>
                <button
                  type="button"
                  className={active ? "timeline-item timeline-item--active" : "timeline-item"}
                  onClick={() => selectEvent(ev.id)}
                >
                  <span className="timeline-item__time mono">{time}</span>
                  <span className="timeline-item__body">
                    <strong>{ev.headline}</strong>
                    <span className="muted timeline-item__sub">
                      {CLASS_LABELS[ev.classification] || ev.classification}
                      {ev.severity_label === "Review recommended" ? " · Review recommended" : ""}
                    </span>
                  </span>
                </button>
              </li>
            );
          })}
        </ol>
      </section>

      <EventDrawer caseId={caseId} eventId={selectedId} onClose={clearSelection} />
    </div>
  );
}
