import { NavLink, Outlet, useParams } from "react-router-dom";

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

  return (
    <div className="shell">
      <aside className="nav" aria-label="Case navigation">
        <div className="brand">
          <p className="brand__name">Digital Forensics</p>
          <p className="brand__tagline">Investigate evidence clearly</p>
          <NavLink to="/" className="nav__back">
            ← All cases
          </NavLink>
        </div>

        <div>
          <p className="nav__section-label">Primary</p>
          <ul className="nav__list">
            {primary.map((item) => (
              <li key={item.to || "overview"}>
                <NavLink
                  to={item.to ? `/cases/${caseId}/${item.to}` : `/cases/${caseId}`}
                  end={item.end}
                  className={({ isActive }) =>
                    isActive ? "nav__link nav__link--active" : "nav__link"
                  }
                >
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </div>

        <div>
          <p className="nav__section-label">More</p>
          <ul className="nav__list">
            {secondary.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={`/cases/${caseId}/${item.to}`}
                  className={({ isActive }) =>
                    isActive ? "nav__link nav__link--active" : "nav__link"
                  }
                >
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </div>
      </aside>

      <main className="main">
        <Outlet />
      </main>
    </div>
  );
}
