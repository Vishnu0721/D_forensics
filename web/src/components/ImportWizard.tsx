import { useRef, useState } from "react";
import { uploadEvidence, type EvidenceSummary } from "../api";

type ImportWizardProps = {
  caseId: string;
  onUploaded: (item: EvidenceSummary) => void;
};

const STEPS = ["Choose a file", "Upload", "Done"] as const;

export function ImportWizard({ caseId, onUploaded }: ImportWizardProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [step, setStep] = useState(0);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpload, setLastUpload] = useState<EvidenceSummary | null>(null);

  function onPick(next: File | null) {
    setFile(next);
    setError(null);
    setLastUpload(null);
    setStep(next ? 1 : 0);
  }

  async function onUpload() {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const item = await uploadEvidence(caseId, file);
      setLastUpload(item);
      setStep(2);
      onUploaded(item);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  function reset() {
    setFile(null);
    setLastUpload(null);
    setError(null);
    setStep(0);
    if (inputRef.current) inputRef.current.value = "";
  }

  return (
    <div className="wizard">
      <ol className="wizard__steps" aria-label="Import steps">
        {STEPS.map((label, i) => (
          <li
            key={label}
            className={
              i === step
                ? "wizard__step wizard__step--active"
                : i < step
                  ? "wizard__step wizard__step--done"
                  : "wizard__step"
            }
          >
            <span className="wizard__step-num">{i + 1}</span>
            {label}
          </li>
        ))}
      </ol>

      <div className="wizard__panel">
        {step === 0 && (
          <>
            <p className="muted">
              Upload a JSON or CSV evidence file into this investigation. Try the
              sample under <code>web/fixtures/sample_evidence.json</code>.
            </p>
            <input
              ref={inputRef}
              type="file"
              accept=".json,.csv,.txt,.log,.xml"
              onChange={(e) => onPick(e.target.files?.[0] ?? null)}
            />
          </>
        )}

        {step === 1 && file && (
          <>
            <p>
              Ready to upload <strong>{file.name}</strong> (
              {(file.size / 1024).toFixed(1)} KB).
            </p>
            <div className="btn-row">
              <button
                type="button"
                className="btn btn--primary"
                disabled={busy}
                onClick={() => void onUpload()}
              >
                {busy ? "Uploading…" : "Upload file"}
              </button>
              <button type="button" className="btn btn--ghost" onClick={reset} disabled={busy}>
                Choose another
              </button>
            </div>
          </>
        )}

        {step === 2 && lastUpload && (
          <>
            <p className="status-ok">Saved as a record: {lastUpload.filename}</p>
            <p className="muted">
              Integrity: {lastUpload.status_label}. Run Analyze when you are ready
              to build the timeline and connections.
            </p>
            <button type="button" className="btn btn--ghost" onClick={reset}>
              Import another file
            </button>
          </>
        )}

        {error && <p className="status-err">{error}</p>}
      </div>
    </div>
  );
}
