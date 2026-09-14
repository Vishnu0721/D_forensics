import { useEffect, useState } from "react";
import { NavLink, Outlet, useParams } from "react-router-dom";
import { AppHeader } from "../components/AppHeader";
import { getCase } from "../api";

const primary = [
  { to: "", label: "Overview", end: true },
  { to: "timeline", label: "Timeline", end: false },
  { to: "connections", label: "Connections", end: false },
] as const;

const secondary = [
  { to: "import", label: "Import" },
  { to: "findings", label: "Findings" },
  { to: "integrity", label: "Integrity" },
  { to: "settings", label: "Settings" },
] as const;

export function CaseLayout() {
  const { caseId } = useParams();
  const [caseName, setCaseName] = useState<string | undefined>();
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    if (!caseId) return;
    let cancelled = false;
    getCase(caseId)
      .then((c) => {
        if (!cancelled) setCaseName(c.name);
      })
      .catch(() => {
        if (!cancelled) setCaseName(undefined);
      });
    return () => {
      cancelled = true;
    };
  }, [caseId]);

  return (
    <div className="app-frame">
      <AppHeader caseId={caseId} caseName={caseName} />
      <div className="shell">
        <button
          type="button"
          className="nav-toggle"
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen((v) => !v)}
        >
          {menuOpen ? "Close menu" : "Case menu"}
        </button>

        <aside
          className={menuOpen ? "nav nav--open" : "nav"}
          aria-label="Case navigation"
        >
          <p className="nav__section-label">Primary</p>
          <ul className="nav__list">
            {primary.map((item) => (
              <li key={item.to || "overview"}>
                <NavLink
                  to={item.to ? `/cases/${caseId}/${item.to}` : `/cases/${caseId}`}
                  end={item.end}
                  onClick={() => setMenuOpen(false)}
                  className={({ isActive }) =>
                    isActive ? "nav__link nav__link--active" : "nav__link"
                  }
                >
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>

          <p className="nav__section-label">More</p>
          <ul className="nav__list">
            {secondary.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={`/cases/${caseId}/${item.to}`}
                  onClick={() => setMenuOpen(false)}
                  className={({ isActive }) =>
                    isActive ? "nav__link nav__link--active" : "nav__link"
                  }
                >
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </aside>

        <main className="main">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
