import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  importDesktopBridge,
  listDesktopBridge,
  listEvidence,
  pollJob,
  startAnalysis,
  uploadEvidence,
  type DesktopBridgeScanItem,
  type EvidenceSummary,
} from "../api";
import { ImportWizard } from "../components/ImportWizard";

export function ImportPage() {
  const { caseId = "" } = useParams();
  const [evidence, setEvidence] = useState<EvidenceSummary[]>([]);
  const [bridgeItems, setBridgeItems] = useState<DesktopBridgeScanItem[]>([]);
  const [sourceDir, setSourceDir] = useState("");
  const [busy, setBusy] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const [items, bridge] = await Promise.all([
      listEvidence(caseId),
      listDesktopBridge().catch(() => [] as DesktopBridgeScanItem[]),
    ]);
    setEvidence(items);
    setBridgeItems(bridge);
  }, [caseId]);

  useEffect(() => {
    let cancelled = false;
    refresh()
      .then(() => {
        if (!cancelled) setError(null);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Could not load evidence");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [refresh]);

  async function onBridgeImport() {
    const dir = sourceDir.trim();
    if (!dir) {
      setError("Enter or pick a desktop evidence folder path.");
      return;
    }
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const result = await importDesktopBridge(caseId, dir);
      const count =
        typeof result.imported_count === "number"
          ? result.imported_count
          : undefined;
      setMessage(
        count != null
          ? `Imported ${count} file${count === 1 ? "" : "s"} from desktop.`
          : "Desktop import finished.",
      );
      await refresh();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Desktop import failed");
    } finally {
      setBusy(false);
    }
  }

  async function onLoadSample() {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const res = await fetch("/sample_evidence.json");
      if (!res.ok) throw new Error("Sample file not found in the web app.");
      const blob = await res.blob();
      const file = new File([blob], "sample_evidence.json", {
        type: "application/json",
      });
      await uploadEvidence(caseId, file);
      setMessage("Sample evidence loaded. Click Analyze when ready.");
      await refresh();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Could not load sample");
    } finally {
      setBusy(false);
    }
  }

  async function onAnalyze() {
    setAnalyzing(true);
    setError(null);
    setMessage("Starting analysis…");
    try {
      const job = await startAnalysis(caseId);
      const final = await pollJob(job.id, {
        onUpdate: (j) => setMessage(j.message || j.status),
      });
      if (final.status === "failed") {
        setError(final.error || "Analysis failed");
      } else {
        setMessage("Analysis complete. Open Timeline or Connections.");
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setAnalyzing(false);
    }
  }

  return (
    <div>
      <h1>Import evidence</h1>
      <p className="lead">
        Bring evidence into this investigation — same idea as desktop Offline
        Evidence, with clearer steps.
      </p>

      <section className="panel">
        <h2>Try the sample</h2>
        <p className="muted">
          Demo story: login → PowerShell → temp payload → outbound connection
          (mirrors a typical desktop offline import).
        </p>
        <button
          type="button"
          className="btn btn--ghost"
          disabled={busy}
          onClick={() => void onLoadSample()}
        >
          {busy ? "Loading…" : "Load sample evidence"}
        </button>
      </section>

      <section className="panel">
        <h2>Upload a file</h2>
        <ImportWizard
          caseId={caseId}
          onUploaded={() => {
            void refresh();
          }}
        />
      </section>

      <section className="panel">
        <h2>From desktop capture</h2>
        <p className="muted">
          When to use this: you already captured activity in the{" "}
          <strong>desktop</strong> app. Those files live under{" "}
          <code>data/evidence/</code>. This copies them into{" "}
          <code>web_data/</code> — it does <strong>not</strong> open the desktop
          database.
        </p>
        {bridgeItems.length === 0 ? (
          <p className="muted">
            No desktop folders found yet. Run <code>python main.py</code>, start
            monitoring (or offline import), then refresh this page.
          </p>
        ) : (
          <ul className="bridge-list">
            {bridgeItems.map((item) => (
              <li key={item.path}>
                <button
                  type="button"
                  className="bridge-item"
                  onClick={() => setSourceDir(item.path)}
                >
                  <strong>{item.case_folder}</strong>
                  <span className="muted">
                    {item.file_count} file{item.file_count === 1 ? "" : "s"}
                  </span>
                  <span className="mono bridge-item__path">{item.path}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
        <label className="field">
          <span>Folder path</span>
          <input
            value={sourceDir}
            onChange={(e) => setSourceDir(e.target.value)}
            placeholder="e.g. data/evidence/<case_id>/preserved"
          />
        </label>
        <button
          type="button"
          className="btn btn--ghost"
          disabled={busy}
          onClick={() => void onBridgeImport()}
        >
          {busy ? "Importing…" : "Import from folder"}
        </button>
      </section>

      <section className="panel">
        <h2>Saved records</h2>
        {evidence.length === 0 ? (
          <div className="empty-inline">
            <p className="muted">No files imported yet.</p>
          </div>
        ) : (
          <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>What</th>
                <th>Status</th>
                <th>Size</th>
              </tr>
            </thead>
            <tbody>
              {evidence.map((e) => (
                <tr key={e.id}>
                  <td>{e.filename}</td>
                  <td>
                    <span className={`badge badge--${statusBadge(e.status_label)}`}>
                      {e.status_label}
                    </span>
                  </td>
                  <td className="muted">{formatSize(e.file_size)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )}
        <div className="btn-row" style={{ marginTop: "1rem" }}>
          <button
            type="button"
            className="btn btn--primary"
            disabled={analyzing || evidence.length === 0}
            onClick={() => void onAnalyze()}
          >
            {analyzing ? "Analyzing…" : "Analyze"}
          </button>
          <Link className="btn btn--ghost" to={`/cases/${caseId}`}>
            Overview
          </Link>
        </div>
        {message && <p className="muted">{message}</p>}
        {error && <p className="status-err">{error}</p>}
      </section>
    </div>
  );
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  return `${(bytes / 1024).toFixed(1)} KB`;
}

function statusBadge(label: string): string {
  const lower = label.toLowerCase();
  if (lower.includes("unchanged") || lower.includes("ok") || lower.includes("valid")) {
    return "ok";
  }
  if (lower.includes("fail") || lower.includes("changed") || lower.includes("missing")) {
    return "danger";
  }
  if (lower.includes("pending") || lower.includes("unknown")) return "warn";
  return "neutral";
}
