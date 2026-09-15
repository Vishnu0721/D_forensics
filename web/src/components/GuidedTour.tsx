import { useEffect, useState } from "react";

const TOUR_KEY = "df-guided-tour-dismissed";

const STEPS = [
  {
    title: "Start with Import",
    body: "Bring evidence files into a case first. Analysis runs after you have saved records.",
  },
  {
    title: "Overview tells you what’s next",
    body: "Each case overview shows a plain next step — not a wall of counters.",
  },
  {
    title: "Timeline and Connections",
    body: "Timeline is the only activity list. Connections shows who and what is linked.",
  },
] as const;

type GuidedTourProps = {
  forceOpen?: boolean;
  onClose?: () => void;
};

export function GuidedTour({ forceOpen = false, onClose }: GuidedTourProps) {
  const [open, setOpen] = useState(false);
  const [index, setIndex] = useState(0);

  useEffect(() => {
    if (forceOpen) {
      setOpen(true);
      setIndex(0);
      return;
    }
    try {
      if (localStorage.getItem(TOUR_KEY) !== "1") setOpen(true);
    } catch {
      setOpen(true);
    }
  }, [forceOpen]);

  function dismiss(permanent: boolean) {
    if (permanent) {
      try {
        localStorage.setItem(TOUR_KEY, "1");
      } catch {
        /* ignore */
      }
    }
    setOpen(false);
    onClose?.();
  }

  if (!open) return null;

  const step = STEPS[index];
  const last = index === STEPS.length - 1;

  return (
    <div className="tour-backdrop" role="dialog" aria-label="Quick tour">
      <div className="tour-card">
        <p className="tour-card__progress">
          Tip {index + 1} of {STEPS.length}
        </p>
        <h2>{step.title}</h2>
        <p className="muted">{step.body}</p>
        <div className="btn-row">
          <button
            type="button"
            className="btn btn--ghost"
            onClick={() => dismiss(true)}
          >
            Skip
          </button>
          {!last ? (
            <button
              type="button"
              className="btn btn--primary"
              onClick={() => setIndex((i) => i + 1)}
            >
              Next
            </button>
          ) : (
            <button
              type="button"
              className="btn btn--primary"
              onClick={() => dismiss(true)}
            >
              Got it
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
