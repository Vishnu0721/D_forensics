import { NavLink, Outlet, useParams } from "react-router-dom";
import { useEffect, useState } from "react";
import { AppHeader } from "../components/AppHeader";
import { getCase, type CaseDetail } from "../api";

const PRIMARY = [
  { to: ".", end: true, label: "Overview", job: "What happened? What’s next?" },
  { to: "timeline", label: "Timeline", job: "Activity in order" },
  { to: "connections", label: "Connections", job: "Who and what is linked" },
] as const;

const MORE = [
  { to: "import", label: "Import", job: "Bring evidence in" },
  { to: "findings", label: "Findings", job: "Needs a look + stories" },
  { to: "integrity", label: "Integrity", job: "Are files still intact?" },
  { to: "settings", label: "Settings", job: "About and theme" },
] as const;

export function CaseLayout() {
  const { caseId = "" } = useParams();
  const [caseDetail, setCaseDetail] = useState<CaseDetail | null>(null);

  useEffect(() => {
    if (!caseId) return;
    let cancelled = false;
    getCase(caseId)
      .then((c) => {
        if (!cancelled) setCaseDetail(c);
      })
      .catch(() => {
        if (!cancelled) setCaseDetail(null);
      });
    return () => {
      cancelled = true;
    };
  }, [caseId]);

  return (
    <div className="app-frame">
      <AppHeader
        subtitle={caseDetail?.name ?? "Investigation"}
        backTo="/"
        backLabel="All investigations"
      />
      <div className="shell">
        <aside className="nav" aria-label="Case navigation">
          <p className="nav__section-label">Primary</p>
          <ul className="nav__list">
            {PRIMARY.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  end={"end" in item ? item.end : false}
                  className={({ isActive }) =>
                    isActive ? "nav__item nav__item--active" : "nav__item"
                  }
                >
                  {item.label}
                </NavLink>
                <p className="nav__hint">{item.job}</p>
              </li>
            ))}
          </ul>

          <p className="nav__section-label">More</p>
          <ul className="nav__list">
            {MORE.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  className={({ isActive }) =>
                    isActive ? "nav__item nav__item--active" : "nav__item"
                  }
                >
                  {item.label}
                </NavLink>
                <p className="nav__hint">{item.job}</p>
              </li>
            ))}
          </ul>
        </aside>

        <main className="main">
          <Outlet context={{ caseDetail, setCaseDetail }} />
        </main>
      </div>
    </div>
  );
}

export type CaseOutletContext = {
  caseDetail: CaseDetail | null;
  setCaseDetail: (c: CaseDetail | null) => void;
};
