import { useEffect, useState } from "react";

const STORAGE_KEY = "df-web-tour-v1";

const STEPS = [
  {
    title: "Welcome",
    body: "This is the web investigation app on branch feature/webapp. It uses web_data/ only — separate from the desktop app.",
  },
  {
    title: "Create or open a case",
    body: "Every investigation lives in a case. Start from Home → New investigation, then import evidence. Click any case card to open it.",
  },
  {
    title: "Import → Timeline → Findings",
    body: "Use the Import wizard, then read the Timeline and Findings. Connections and Integrity deepen the story.",
  },
  {
    title: "Optional live monitor",
    body: "On Overview you can start local live monitoring for this PC only. Stop it before offline re-analysis.",
  },
];

type Props = {
  forceOpen?: boolean;
  onClose?: () => void;
};

export function GuidedTour({ forceOpen = false, onClose }: Props) {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (forceOpen) {
      setOpen(true);
      setStep(0);
      return;
    }
    try {
      if (!localStorage.getItem(STORAGE_KEY)) setOpen(true);
    } catch {
      setOpen(true);
    }
  }, [forceOpen]);

  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") finish();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, step]);

  function finish() {
    try {
      localStorage.setItem(STORAGE_KEY, "1");
    } catch {
      /* ignore */
    }
    setOpen(false);
    onClose?.();
  }

  if (!open) return null;

  const current = STEPS[step];
  const last = step >= STEPS.length - 1;

  return (
    <div
      className="tour-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="tour-title"
      onClick={finish}
    >
      <div
        className="tour-card panel"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => e.stopPropagation()}
      >
        <p className="badge badge--phase">
          Quick tour · {step + 1}/{STEPS.length}
        </p>
        <h2 id="tour-title">{current.title}</h2>
        <p className="muted">{current.body}</p>
        <p className="muted hint">Press Esc or click outside to close, then open a case card.</p>
        <div className="wizard__actions">
          <button type="button" className="btn btn--ghost" onClick={finish}>
            Skip
          </button>
          {!last ? (
            <button type="button" className="btn btn--primary" onClick={() => setStep((s) => s + 1)}>
              Next
            </button>
          ) : (
            <button type="button" className="btn btn--primary" onClick={finish}>
              Got it
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
