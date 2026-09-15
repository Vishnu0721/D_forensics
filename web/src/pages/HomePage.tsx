import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listCases, type CaseSummary } from "../api";

export function HomePage() {
  const [cases, setCases] = useState<CaseSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listCases()
      .then((items) => {
        if (!cancelled) {
          setCases(items);
          setError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : "Could not load investigations. Is the API running?",
          );
          setCases([]);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div>
      <div className="page-hero">
        <h1>Investigations</h1>
        <p className="lead">
          Open a case or start a new investigation. Import evidence first, then
          analyze.
        </p>
        <Link className="btn btn--primary" to="/cases/new">
          New investigation
        </Link>
      </div>

      {error && <p className="status-err">{error}</p>}

      {cases === null && !error && <p className="muted">Loading…</p>}

      {cases && cases.length === 0 && !error && (
        <section className="empty-state">
          <h2>No investigations yet</h2>
          <p className="muted">Create one to import evidence and explore activity.</p>
          <Link className="btn btn--primary" to="/cases/new">
            New investigation
          </Link>
        </section>
      )}

      {cases && cases.length > 0 && (
        <ul className="case-list">
          {cases.map((c) => (
            <li key={c.id}>
              <Link className="case-card" to={`/cases/${c.id}`}>
                <div>
                  <h2 className="case-card__title">{c.name}</h2>
                  {c.description && <p className="muted">{c.description}</p>}
                  <p className="case-card__meta muted">
                    {c.evidence_count} saved record{c.evidence_count === 1 ? "" : "s"}
                    {" · "}
                    {c.event_count} activit{c.event_count === 1 ? "y" : "ies"}
                    {c.created_at ? ` · ${formatDate(c.created_at)}` : ""}
                  </p>
                </div>
                <span className="case-card__chevron" aria-hidden>
                  →
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString();
  } catch {
    return iso;
  }
}
