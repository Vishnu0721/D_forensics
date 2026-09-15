import { useEffect, useState } from "react";

/** Shows when the FastAPI backend is unreachable (common for new testers). */
export function ApiBanner() {
  const [down, setDown] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const check = () => {
      fetch("/health")
        .then((r) => {
          if (!cancelled) setDown(!r.ok);
        })
        .catch(() => {
          if (!cancelled) setDown(true);
        });
    };
    check();
    const id = window.setInterval(check, 15000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  if (!down) return null;

  return (
    <div className="api-banner" role="status">
      API unreachable. Start the backend from the repo root:{" "}
      <code>uvicorn api.main:app --reload --app-dir .</code> (set{" "}
      <code>PYTHONPATH</code> first). See <code>web/README.md</code>.
    </div>
  );
}
