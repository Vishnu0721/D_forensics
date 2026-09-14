import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { EvidenceSummary, pollJob, startAnalysis, uploadEvidence } from "../api";

export type SourceHint = "auto" | "json" | "csv" | "log" | "sysmon";

const SOURCE_OPTIONS: { value: SourceHint; label: string; help: string }[] = [
  {
    value: "auto",
    label: "Detect automatically",
    help: "Best default — we guess from the file contents and name.",
  },
  {
    value: "json",
    label: "JSON event export",
    help: "Array or object of forensic / Sysmon-style JSON records.",
  },
  {
    value: "csv",
    label: "CSV spreadsheet",
    help: "Rows of events with headers (timestamp, process, etc.).",
  },
  {
    value: "log",
    label: "Text / log file",
    help: "Plain .txt or .log lines we can parse as best-effort.",
  },
  {
    value: "sysmon",
    label: "Sysmon / Windows log JSON",
    help: "Elastic-style winlog / Sysmon event exports.",
  },
];

function guessHint(file: File): SourceHint {
  const name = file.name.toLowerCase();
  if (name.includes("sysmon") || name.includes("winlog")) return "sysmon";
  if (name.endsWith(".csv")) return "csv";
  if (name.endsWith(".log") || name.endsWith(".txt")) return "log";
  if (name.endsWith(".json")) return "json";
  return "auto";
}

function sourceTypeForApi(hint: SourceHint): string | undefined {
  if (hint === "auto") return undefined;
  if (hint === "sysmon") return "windows_log";
  if (hint === "log") return "offline_report";
  return hint === "json" ? "offline_report" : hint;
}

type Step = 1 | 2 | 3 | 4;

type Props = {
  caseId: string;
  onComplete?: () => void;
  compact?: boolean;
};

export function ImportWizard({ caseId, onComplete, compact }: Props) {
  const [step, setStep] = useState<Step>(1);
  const [file, setFile] = useState<File | null>(null);
  const [hint, setHint] = useState<SourceHint>("auto");
  const [error, setError] = useState<string | null>(null);
  const [progressMsg, setProgressMsg] = useState("Preparing…");
  const [uploaded, setUploaded] = useState<EvidenceSummary | null>(null);
  const [summary, setSummary] = useState<Record<string, unknown> | null>(null);

  const steps = useMemo(
    () => [
      { n: 1 as const, label: "Choose file" },
      { n: 2 as const, label: "Confirm type" },
      { n: 3 as const, label: "Analyze" },
      { n: 4 as const, label: "Done" },
    ],
    [],
  );

  function reset() {
    setStep(1);
    setFile(null);
    setHint("auto");
    setError(null);
    setProgressMsg("Preparing…");
    setUploaded(null);
    setSummary(null);
  }

  function onPick(next: File | null) {
    if (!next) return;
    setFile(next);
    setHint(guessHint(next));
    setError(null);
    setStep(2);
  }

  async function runImport() {
    if (!file) return;
    setStep(3);
    setError(null);
    setProgressMsg("Uploading and preserving a hashed copy…");
    try {
      const artifact = await uploadEvidence(caseId, file, sourceTypeForApi(hint));
      setUploaded(artifact);
      setProgressMsg("Starting analysis…");
      const job = await startAnalysis(caseId);
      const done = await pollJob(job.id, (j) => setProgressMsg(j.message || "Working…"));
      if (done.status === "failed") {
        throw new Error(done.error || "Analysis failed");
      }
      setSummary(done.result_summary ?? null);
      setStep(4);
      onComplete?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setStep(2);
    }
  }

  return (
    <div className={`wizard ${compact ? "wizard--compact" : ""}`}>
      <ol className="wizard__steps" aria-label="Import steps">
        {steps.map((s) => (
          <li
            key={s.n}
            className={
              s.n === step
                ? "wizard__step wizard__step--active"
                : s.n < step
                  ? "wizard__step wizard__step--done"
                  : "wizard__step"
            }
          >
            <span className="wizard__step-num">{s.n}</span>
            <span>{s.label}</span>
          </li>
        ))}
      </ol>

      {step === 1 && (
        <div className="wizard__body">
          <h2>Choose evidence file</h2>
          <p className="muted">
            Use a preserved export you are authorized to analyze — JSON, CSV, or logs.
          </p>
          <label className="btn btn--primary file-btn">
            Select file
            <input
              type="file"
              hidden
              accept=".json,.csv,.txt,.log,.evtx,application/json,text/csv,text/plain"
              onChange={(e) => onPick(e.target.files?.[0] ?? null)}
            />
          </label>
          <p className="muted hint">
            Tip: try <code>web/fixtures/sample_evidence.json</code> for a quick demo.
          </p>
        </div>
      )}

      {step === 2 && file && (
        <div className="wizard__body">
          <h2>Confirm file type</h2>
          <p>
            <strong>{file.name}</strong>{" "}
            <span className="muted">({Math.max(1, Math.round(file.size / 1024))} KB)</span>
          </p>
          <fieldset className="source-options">
            <legend className="sr-only">Evidence type</legend>
            {SOURCE_OPTIONS.map((opt) => (
              <label key={opt.value} className="source-option">
                <input
                  type="radio"
                  name="sourceHint"
                  value={opt.value}
                  checked={hint === opt.value}
                  onChange={() => setHint(opt.value)}
                />
                <span>
                  <strong>{opt.label}</strong>
                  <span className="muted">{opt.help}</span>
                </span>
              </label>
            ))}
          </fieldset>
          {error && <p className="error">{error}</p>}
          <div className="wizard__actions">
            <button type="button" className="btn btn--ghost" onClick={reset}>
              Back
            </button>
            <button type="button" className="btn btn--primary" onClick={runImport}>
              Upload & analyze
            </button>
          </div>
        </div>
      )}

      {step === 3 && (
        <div className="wizard__body">
          <h2>Analyzing</h2>
          <p className="muted">{progressMsg}</p>
          <div className="progress" aria-hidden>
            <div className="progress__bar" />
          </div>
          <p className="muted">We keep a hashed copy under this case, then build the timeline.</p>
        </div>
      )}

      {step === 4 && (
        <div className="wizard__body">
          <h2>Import complete</h2>
          <p className="muted">
            {uploaded
              ? `Saved ${uploaded.filename} · fingerprint ${uploaded.sha256_hash.slice(0, 12)}…`
              : "Evidence preserved."}
          </p>
          {summary && (
            <ul className="wizard__summary">
              <li>
                Events stored: <strong>{String(summary.events_stored ?? "—")}</strong>
              </li>
              <li>
                Findings: <strong>{String(summary.finding_count ?? "—")}</strong>
              </li>
              <li>
                Activity stories: <strong>{String(summary.story_count ?? "—")}</strong>
              </li>
            </ul>
          )}
          <div className="wizard__actions">
            <Link className="btn btn--primary" to={`/cases/${caseId}/timeline`}>
              Open Timeline
            </Link>
            <Link className="btn btn--ghost" to={`/cases/${caseId}/findings`}>
              Open Findings
            </Link>
            <button type="button" className="btn btn--ghost" onClick={reset}>
              Import another
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
