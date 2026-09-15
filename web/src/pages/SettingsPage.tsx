import { useEffect, useState } from "react";
import { GuidedTour } from "../components/GuidedTour";
import { getMeta, type MetaResponse } from "../api";
import { useLabels, type LabelMode } from "../context/LabelMode";
import { PRODUCT_NAME, PRODUCT_TAGLINE, PRODUCT_VERSION_FALLBACK } from "../product";

const THEME_KEY = "df-theme";

export function SettingsPage() {
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [showTour, setShowTour] = useState(false);
  const [meta, setMeta] = useState<MetaResponse | null>(null);
  const { mode, setMode } = useLabels();

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
    getMeta()
      .then(setMeta)
      .catch(() => setMeta(null));
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
      <p className="lead">About this workspace and display preferences.</p>

      <section className="panel">
        <h2>Theme</h2>
        <p className="muted">
          Light white + blue is the product default (best for demos and reports).
          Dark is optional.
        </p>
        <button type="button" className="btn btn--ghost" onClick={toggleTheme}>
          Switch to {theme === "light" ? "dark" : "light"} theme
        </button>
        <p className="muted" style={{ marginTop: "0.75rem" }}>
          Current: <strong>{theme}</strong>
        </p>
      </section>

      <section className="panel">
        <h2>Label style</h2>
        <p className="muted">
          Plain language matches the clarity goal. Formal wording is closer to
          classic forensic reports.
        </p>
        <div className="btn-row">
          {(["plain", "formal"] as LabelMode[]).map((m) => (
            <button
              key={m}
              type="button"
              className={mode === m ? "btn btn--primary" : "btn btn--ghost"}
              onClick={() => setMode(m)}
            >
              {m === "plain" ? "Plain" : "Formal"}
            </button>
          ))}
        </div>
      </section>

      <section className="panel">
        <h2>About</h2>
        <p>
          <strong>{meta?.product_name ?? PRODUCT_NAME}</strong>
          <br />
          {meta?.tagline ?? PRODUCT_TAGLINE}
        </p>
        <ul className="list-plain">
          <li>
            Version{" "}
            <code>{meta?.version ?? PRODUCT_VERSION_FALLBACK}</code>
            {meta?.phase ? (
              <>
                {" "}
                · build <code>{meta.phase}</code>
              </>
            ) : null}
          </li>
          <li>License: {meta?.license ?? "MIT"}</li>
          <li>No sign-in — local academic / authorized use only</li>
          <li>
            Data under <code>web_data/</code> — desktop keeps{" "}
            <code>forensics.db</code> / <code>data/</code>
          </li>
          <li>Best experienced on a desktop browser</li>
        </ul>
        {meta?.message && <p className="muted">{meta.message}</p>}
        <p className="muted">
          Docs in the repo: <code>README.md</code>, <code>web/README.md</code>,{" "}
          <code>docs/webapp/PUBLISH.md</code>
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
