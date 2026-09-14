import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { CaseSummary, listCases } from "../api";
import { GuidedTour } from "../components/GuidedTour";

export function HomePage() {
  const navigate = useNavigate();
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tourForce, setTourForce] = useState(false);

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

  function openCase(caseId: string) {
    navigate(`/cases/${caseId}`);
  }

  return (
    <div className="home">
      <GuidedTour forceOpen={tourForce} onClose={() => setTourForce(false)} />
      <header className="home__hero panel">
        <span className="badge badge--phase">Home</span>
        <h1>Investigations</h1>
        <p className="muted">
          Web app home (branch <code>feature/webapp</code>). Open a case or start a new
          investigation. Data stays in <code>web_data/</code> — separate from the desktop app.
        </p>
        <div className="overview__cta">
          <Link className="btn btn--primary" to="/cases/new">
            New investigation
          </Link>
          <button type="button" className="btn btn--ghost" onClick={() => setTourForce(true)}>
            Quick tour
          </button>
        </div>
      </header>

      <section className="panel">
        <h2>Your cases</h2>
        <p className="muted">Click a card (or Open) to enter that investigation.</p>
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
              <button
                type="button"
                className="case-card"
                onClick={() => openCase(c.id)}
                aria-label={`Open case ${c.name}`}
              >
                <div>
                  <strong>{c.name}</strong>
                  <p className="muted">{c.description || "No description"}</p>
                </div>
                <div className="case-card__meta">
                  <span className={`badge ${c.mode === "live" ? "badge--live" : ""}`}>
                    {c.mode === "live" ? "Live" : "Imported"}
                  </span>
                  <span className="muted">
                    {c.evidence_count} evidence · {c.event_count} events
                  </span>
                  <span className="case-card__open">Open →</span>
                </div>
              </button>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
