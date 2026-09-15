import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { listFindings, type FindingSummary, type FindingsResponse } from "../api";
import { useLabels } from "../context/LabelMode";

export function FindingsPage() {
  const { caseId = "" } = useParams();
  const { t } = useLabels();
  const [data, setData] = useState<FindingsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
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
      <p className="lead">
        {t(
          "What needs a look, plus activity stories (desktop: Needs attention / Incident Summary).",
          "Review-recommended items and reconstructed activity chains.",
        )}
      </p>

      {loading && <p className="muted">Loading…</p>}
      {error && (
        <p className="status-err">
          {error}{" "}
          <button
            type="button"
            className="text-link"
            onClick={() => window.location.reload()}
          >
            Retry
          </button>
        </p>
      )}

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
          <h2>{t("Needs a look", "Review recommended")}</h2>
          <ul className="finding-list">
            {data.findings.map((f) => (
              <FindingRow key={f.id} caseId={caseId} item={f} />
            ))}
          </ul>
        </section>
      )}

      {data && data.stories.length > 0 && (
        <section className="panel">
          <h2>{t("Activity stories", "Reconstructed incidents")}</h2>
          <ul className="finding-list">
            {data.stories.map((f) => (
              <FindingRow key={f.id} caseId={caseId} item={f} />
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function FindingRow({
  caseId,
  item,
}: {
  caseId: string;
  item: FindingSummary;
}) {
  const eventId = item.related_event_ids?.[0];
  const to = eventId
    ? `/cases/${caseId}/timeline?event=${encodeURIComponent(eventId)}`
    : `/cases/${caseId}/timeline`;

  return (
    <li className="finding-item">
      <span className={`badge badge--${sev(item.severity_label)}`}>
        {item.severity_label}
      </span>
      <div>
        <strong>{item.headline}</strong>
        {item.detail && <p className="muted">{item.detail}</p>}
        <Link className="text-link" to={to}>
          {eventId ? "Open related activity" : "Open Timeline"}
        </Link>
      </div>
    </li>
  );
}

function sev(label: string): string {
  const lower = label.toLowerCase();
  if (lower.includes("warn") || lower.includes("look") || lower.includes("review") || lower.includes("medium")) {
    return "warn";
  }
  if (lower.includes("high") || lower.includes("critical")) return "danger";
  return "ok";
}
