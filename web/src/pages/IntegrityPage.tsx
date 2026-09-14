import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import {
  IntegrityResponse,
  listIntegrity,
  verifyIntegrity,
} from "../api";

export function IntegrityPage() {
  const { caseId } = useParams();
  const [data, setData] = useState<IntegrityResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!caseId) return;
    setLoading(true);
    setError(null);
    try {
      setData(await listIntegrity(caseId));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function onVerify() {
    if (!caseId) return;
    setBusy(true);
    setError(null);
    try {
      setData(await verifyIntegrity(caseId));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  if (!caseId) return null;

  return (
    <div className="integrity-page">
      <section className="panel">
        <header className="integrity-header">
          <div>
            <h1>Integrity</h1>
            <p className="muted">
              We check that <strong>our saved copies</strong> of evidence still match their SHA-256
              fingerprints — not original files on another computer.
            </p>
          </div>
          <button
            type="button"
            className="btn btn--primary"
            disabled={busy || loading}
            onClick={onVerify}
          >
            {busy ? "Verifying…" : "Verify now"}
          </button>
        </header>

        {loading && <p className="muted">Loading integrity table…</p>}
        {error && <p className="error">{error}</p>}

        {data && (
          <>
            <div className="legend-row">
              {Object.entries(data.legend).map(([key, help]) => (
                <div key={key} className="legend-item">
                  <strong>{statusLabel(key, data)}</strong>
                  <span className="muted">{help}</span>
                </div>
              ))}
            </div>

            {data.items.length === 0 ? (
              <div className="empty">
                <p>No preserved evidence yet.</p>
                <p className="muted">Import a file first, then verify fingerprints here.</p>
              </div>
            ) : (
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>What it is</th>
                      <th>Status</th>
                      <th>Fingerprint (SHA-256)</th>
                      <th>Collected</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.items.map((row) => (
                      <tr key={row.evidence_id}>
                        <td>
                          <strong>{row.what}</strong>
                          <div className="muted mono" style={{ fontSize: "0.75rem" }}>
                            {row.evidence_id.slice(0, 8)}…
                          </div>
                        </td>
                        <td>
                          <span className={`status-pill status-pill--${row.status.toLowerCase()}`}>
                            {row.status_label}
                          </span>
                        </td>
                        <td className="mono fingerprint">{row.sha256_hash}</td>
                        <td className="muted">
                          {row.collected_at
                            ? new Date(row.collected_at).toLocaleString()
                            : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </section>
    </div>
  );
}

function statusLabel(key: string, data: IntegrityResponse): string {
  const sample = data.items.find((i) => i.status === key);
  if (sample) return sample.status_label;
  const map: Record<string, string> = {
    VALID: "Unchanged",
    MODIFIED: "Changed on disk",
    UNVERIFIABLE: "File missing",
    PENDING: "Not checked yet",
  };
  return map[key] || key;
}
