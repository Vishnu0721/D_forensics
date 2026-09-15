import { useEffect, useState } from "react";
import { GuidedTour } from "../components/GuidedTour";

const THEME_KEY = "df-theme";

export function SettingsPage() {
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [showTour, setShowTour] = useState(false);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(THEME_KEY);
      if (stored === "dark" || stored === "light") {
        setTheme(stored);
        document.documentElement.setAttribute("data-theme", stored);
      }
    } catch {
      /* ignore */
    }
  }, []);

  function toggleTheme() {
    const next = theme === "light" ? "dark" : "light";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch {
      /* ignore */
    }
  }

  return (
    <div>
      <h1>Settings</h1>
      <p className="lead">About this web app and display preferences.</p>

      <section className="panel">
        <h2>Theme</h2>
        <p className="muted">
          Light white + blue is the default. Dark is optional for low-light rooms.
        </p>
        <button type="button" className="btn btn--ghost" onClick={toggleTheme}>
          Switch to {theme === "light" ? "dark" : "light"} theme
        </button>
        <p className="muted" style={{ marginTop: "0.75rem" }}>
          Current: <strong>{theme}</strong>
        </p>
      </section>

      <section className="panel">
        <h2>About</h2>
        <p>
          Digital Forensics web investigation UI. Same offline pipeline as the
          desktop app, with one job per screen and plain language.
        </p>
        <ul className="list-plain">
          <li>No sign-in in this academic build</li>
          <li>Data stays under <code>web_data/</code> — not the desktop database</li>
          <li>
            Product decisions:{" "}
            <a href="/docs/webapp/PHASE_A.md" onClick={(e) => e.preventDefault()}>
              docs/webapp/PHASE_A.md
            </a>{" "}
            (see repo)
          </li>
        </ul>
        <p className="muted">
          Open <code>docs/webapp/PHASE_A.md</code> in the repository for the clarity
          contract, glossary, and information architecture.
        </p>
      </section>

      <section className="panel">
        <h2>Quick tour</h2>
        <p className="muted">Replay the short optional tips overlay.</p>
        <button
          type="button"
          className="btn btn--ghost"
          onClick={() => setShowTour(true)}
        >
          Show tour
        </button>
      </section>

      {showTour && (
        <GuidedTour forceOpen onClose={() => setShowTour(false)} />
      )}
    </div>
  );
}
