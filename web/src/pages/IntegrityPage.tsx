import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { listIntegrity, verifyIntegrity, type IntegrityResponse } from "../api";

export function IntegrityPage() {
  const { caseId = "" } = useParams();
  const [data, setData] = useState<IntegrityResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const res = await listIntegrity(caseId);
    setData(res);
  }, [caseId]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    refresh()
      .then(() => {
        if (!cancelled) setError(null);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Could not load integrity");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [refresh]);

  async function onVerify() {
    setBusy(true);
    setError(null);
    try {
      const res = await verifyIntegrity(caseId);
      setData(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Verify failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <h1>Integrity</h1>
      <p className="lead">Are preserved files still intact?</p>

      <div className="btn-row" style={{ marginBottom: "1.25rem" }}>
        <button
          type="button"
          className="btn btn--primary"
          disabled={busy || loading}
          onClick={() => void onVerify()}
        >
          {busy ? "Checking…" : "Verify now"}
        </button>
      </div>

      {loading && !data && <p className="muted">Loading…</p>}
      {error && <p className="status-err">{error}</p>}

      {data && data.items.length === 0 && (
        <section className="empty-state">
          <h2>No saved records</h2>
          <p className="muted">Import evidence first, then verify integrity.</p>
          <Link className="btn btn--primary" to={`/cases/${caseId}/import`}>
            Import evidence
          </Link>
        </section>
      )}

      {data && data.items.length > 0 && (
        <section className="panel">
          <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Status</th>
                <th>What</th>
                <th>Hash (secondary)</th>
                <th>Collected</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((row) => (
                <tr key={row.evidence_id}>
                  <td>
                    <span className={`badge badge--${statusBadge(row.status_label)}`}>
                      {row.status_label}
                    </span>
                  </td>
                  <td>{row.what}</td>
                  <td className="mono muted hash-cell">{row.sha256_hash}</td>
                  <td className="muted">
                    {row.collected_at ? formatWhen(row.collected_at) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        </section>
      )}

      {data && Object.keys(data.legend).length > 0 && (
        <section className="panel">
          <h2>Legend</h2>
          <ul className="list-plain">
            {Object.entries(data.legend).map(([key, text]) => (
              <li key={key}>
                <strong>{key}</strong> — {text}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function statusBadge(label: string): string {
  const lower = label.toLowerCase();
  if (lower.includes("intact") || lower.includes("ok") || lower.includes("valid")) {
    return "ok";
  }
  if (lower.includes("fail") || lower.includes("mismatch") || lower.includes("changed")) {
    return "danger";
  }
  return "warn";
}

function formatWhen(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}
