import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { CaseSummary, listCases } from "../api";

export function HomePage() {
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await listCases();
        if (!cancelled) setCases(data.items);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="home">
      <header className="home__hero panel">
        <span className="badge badge--phase">Phase 3 · investigate</span>
        <h1>Investigations</h1>
        <p className="muted">
          Open a case or start a new one. Import preserved evidence — live monitoring comes later.
        </p>
        <Link className="btn btn--primary" to="/cases/new">
          New investigation
        </Link>
      </header>

      <section className="panel">
        <h2>Your cases</h2>
        {loading && <p className="muted">Loading cases…</p>}
        {error && (
          <p className="error">
            Could not reach the API. Is it running on port 8000? ({error})
          </p>
        )}
        {!loading && !error && cases.length === 0 && (
          <div className="empty">
            <p>No cases yet.</p>
            <p className="muted">Create an investigation, then import a JSON or CSV evidence file.</p>
          </div>
        )}
        <ul className="case-list">
          {cases.map((c) => (
            <li key={c.id}>
              <Link className="case-card" to={`/cases/${c.id}`}>
                <div>
                  <strong>{c.name}</strong>
                  <p className="muted">{c.description || "No description"}</p>
                </div>
                <div className="case-card__meta">
                  <span className="badge">{c.mode === "live" ? "Live" : "Imported"}</span>
                  <span className="muted">
                    {c.evidence_count} evidence · {c.event_count} events
                  </span>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
