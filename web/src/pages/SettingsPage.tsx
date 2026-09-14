import { useTheme } from "../theme/ThemeProvider";
import { GuidedTour } from "../components/GuidedTour";
import { useState } from "react";

export function SettingsPage() {
  const { theme, setTheme } = useTheme();
  const [tourOpen, setTourOpen] = useState(false);

  return (
    <section className="panel">
      {tourOpen && <GuidedTour forceOpen onClose={() => setTourOpen(false)} />}
      <h1>Settings</h1>
      <p className="muted">
        Local academic use on <code>feature/webapp</code> — no sign-in required in v1.
      </p>

      <div className="settings-block">
        <h2>Appearance</h2>
        <p className="muted">Professional white &amp; blue light theme, with optional dark mode.</p>
        <div className="view-toggle" role="group" aria-label="Theme">
          <button
            type="button"
            className={theme === "light" ? "filter-chip filter-chip--active" : "filter-chip"}
            onClick={() => setTheme("light")}
          >
            Light
          </button>
          <button
            type="button"
            className={theme === "dark" ? "filter-chip filter-chip--active" : "filter-chip"}
            onClick={() => setTheme("dark")}
          >
            Dark
          </button>
        </div>
      </div>

      <div className="settings-block">
        <h2>Help</h2>
        <button type="button" className="btn btn--ghost" onClick={() => setTourOpen(true)}>
          Replay quick tour
        </button>
      </div>

      <div className="settings-block">
        <h2>Data locations (web only)</h2>
        <ul className="settings-list">
          <li>
            Web database: <code>web_data/forensics_web.db</code>
          </li>
          <li>
            Preserved evidence: <code>web_data/evidence/</code>
          </li>
          <li>
            Graphs: <code>web_data/graphs/</code>
          </li>
        </ul>
        <p className="muted">
          Desktop app keeps <code>forensics.db</code> / <code>data/</code>. Do not mix the two while
          developing.
        </p>
      </div>

      <div className="settings-block">
        <h2>Live agent</h2>
        <p className="muted">
          Process + network collectors run inside the API process and write to{" "}
          <code>web_data/</code>. Start/stop from Case Overview. Optional EVTX support:{" "}
          <code>pip install python-evtx</code>.
        </p>
      </div>
    </section>
  );
}
