import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { listEvents, type EventFilter, type EventSummary } from "../api";
import { EventDrawer } from "../components/EventDrawer";
import { useLabels } from "../context/LabelMode";

const PAGE = 50;

export function TimelinePage() {
  const { caseId = "" } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const { t } = useLabels();
  const [filter, setFilter] = useState<EventFilter>("all");
  const [items, setItems] = useState<EventSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(
    searchParams.get("event"),
  );

  const FILTERS: { id: EventFilter; label: string }[] = [
    { id: "all", label: "All" },
    { id: "user", label: t("User actions", "User activity") },
    { id: "background", label: t("Background noise", "System activity") },
    { id: "findings", label: t("Needs a look", "Review recommended") },
    { id: "linked", label: t("Linked", "Correlated") },
    { id: "unclear", label: "Unclear" },
  ];

  useEffect(() => {
    const ev = searchParams.get("event");
    if (ev) setSelectedId(ev);
  }, [searchParams]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    listEvents(caseId, filter, { limit: PAGE, offset: 0 })
      .then((page) => {
        if (!cancelled) {
          setItems(page.items);
          setTotal(page.total);
          setOffset(page.items.length);
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

  async function loadMore() {
    setLoading(true);
    try {
      const page = await listEvents(caseId, filter, { limit: PAGE, offset });
      setItems((prev) => [...prev, ...page.items]);
      setOffset((o) => o + page.items.length);
      setTotal(page.total);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Could not load more");
    } finally {
      setLoading(false);
    }
  }

  function openEvent(id: string) {
    setSelectedId(id);
    setSearchParams({ event: id }, { replace: true });
  }

  function closeDrawer() {
    setSelectedId(null);
    setSearchParams({}, { replace: true });
  }

  return (
    <div>
      <h1>Timeline</h1>
      <p className="lead">
        {t(
          "Activity in order, as plain sentences (one list — not dual desktop streams).",
          "Chronological forensic events in a single feed.",
        )}
      </p>

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

      {loading && items.length === 0 && <p className="muted">Loading…</p>}
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

      {items.length > 0 && (
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
                  onClick={() => openEvent(ev.id)}
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
          {items.length < total && (
            <button
              type="button"
              className="btn btn--ghost"
              disabled={loading}
              onClick={() => void loadMore()}
            >
              {loading ? "Loading…" : "Load more"}
            </button>
          )}
        </>
      )}

      <EventDrawer
        caseId={caseId}
        eventId={selectedId}
        onClose={closeDrawer}
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
  if (lower.includes("warn") || lower.includes("look") || lower.includes("review") || lower.includes("medium")) {
    return "warn";
  }
  if (lower.includes("high") || lower.includes("critical")) return "danger";
  return "ok";
}
