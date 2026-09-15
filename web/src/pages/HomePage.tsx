import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { deleteCase, listCases, type CaseSummary } from "../api";
import { PRODUCT_TAGLINE } from "../product";

export function HomePage() {
  const [cases, setCases] = useState<CaseSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  async function refresh() {
    const items = await listCases();
    setCases(items);
    setError(null);
  }

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

  async function onDelete(c: CaseSummary) {
    const ok = window.confirm(
      `Delete investigation “${c.name}”?\n\nThis removes its web_data copies only. Desktop forensics.db is not touched.`,
    );
    if (!ok) return;
    setDeletingId(c.id);
    setError(null);
    try {
      await deleteCase(c.id);
      await refresh();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Could not delete");
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div>
      <div className="page-hero">
        <p className="eyebrow">Local investigation workspace</p>
        <h1>Investigations</h1>
        <p className="lead">{PRODUCT_TAGLINE}</p>
        <p className="muted hero-sub">
          Same forensic pipeline as the desktop monitor — clearer screens for
          review. Import evidence first, then analyze.
        </p>
        <div className="btn-row">
          <Link className="btn btn--primary" to="/cases/new">
            New investigation
          </Link>
        </div>
      </div>

      {error && (
        <p className="status-err">
          {error}{" "}
          <button type="button" className="text-link" onClick={() => void refresh().catch(() => undefined)}>
            Retry
          </button>
        </p>
      )}

      {cases === null && !error && <p className="muted">Loading…</p>}

      {cases && cases.length === 0 && !error && (
        <section className="empty-state">
          <h2>No investigations yet</h2>
          <p className="muted">
            Create one, then import the sample file{" "}
            <code>sample_evidence.json</code> (or capture from the desktop app).
          </p>
          <Link className="btn btn--primary" to="/cases/new">
            New investigation
          </Link>
        </section>
      )}

      {cases && cases.length > 0 && (
        <ul className="case-list">
          {cases.map((c) => (
            <li key={c.id} className="case-row">
              <Link className="case-card" to={`/cases/${c.id}`}>
                <div>
                  <h2 className="case-card__title">{c.name}</h2>
                  {c.description && <p className="muted">{c.description}</p>}
                  <p className="case-card__meta muted">
                    {c.evidence_count} saved record
                    {c.evidence_count === 1 ? "" : "s"}
                    {" · "}
                    {c.event_count} activit
                    {c.event_count === 1 ? "y" : "ies"}
                    {c.created_at ? ` · ${formatDate(c.created_at)}` : ""}
                  </p>
                </div>
                <span className="case-card__chevron" aria-hidden>
                  →
                </span>
              </Link>
              <button
                type="button"
                className="btn btn--ghost btn--danger-text case-delete"
                disabled={deletingId === c.id}
                onClick={() => void onDelete(c)}
              >
                {deletingId === c.id ? "Deleting…" : "Delete"}
              </button>
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
