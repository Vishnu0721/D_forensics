import { NavLink, Outlet, useLocation, useParams } from "react-router-dom";
import { useEffect, useMemo, useState } from "react";
import { AppHeader } from "../components/AppHeader";
import { ApiBanner } from "../components/ApiBanner";
import { getCase, type CaseDetail } from "../api";

export function CaseLayout() {
  const { caseId = "" } = useParams();
  const location = useLocation();
  const [caseDetail, setCaseDetail] = useState<CaseDetail | null>(null);
  const [navOpen, setNavOpen] = useState(false);

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

  useEffect(() => {
    setNavOpen(false);
  }, [caseId, location.pathname]);

  const empty = (caseDetail?.evidence_count ?? 0) === 0;

  const primary = useMemo(() => {
    const base = [
      { to: ".", end: true as const, label: "Overview", job: "What happened? What’s next?" },
      { to: "timeline", label: "Timeline", job: "Activity in order" },
      { to: "connections", label: "Connections", job: "Who and what is linked" },
    ];
    if (empty) {
      return [
        base[0],
        { to: "import", label: "Import", job: "Bring evidence in first" },
        base[1],
        base[2],
      ];
    }
    return base;
  }, [empty]);

  const more = useMemo(() => {
    const items = [
      { to: "import", label: "Import", job: "Bring evidence in" },
      { to: "findings", label: "Findings", job: "Needs a look + stories" },
      { to: "integrity", label: "Integrity", job: "Are files still intact?" },
      { to: "settings", label: "Settings", job: "About and theme" },
    ];
    return empty ? items.filter((i) => i.to !== "import") : items;
  }, [empty]);

  return (
    <div className="app-frame">
      <AppHeader
        subtitle={caseDetail?.name ?? "Investigation"}
        backTo="/"
        backLabel="All investigations"
      />
      <ApiBanner />
      <div className="shell">
        <button
          type="button"
          className="nav-toggle"
          aria-expanded={navOpen}
          aria-controls="case-nav"
          onClick={() => setNavOpen((v) => !v)}
        >
          {navOpen ? "Close menu" : "Investigation menu"}
        </button>

        <aside
          id="case-nav"
          className={navOpen ? "nav nav--open" : "nav"}
          aria-label="Investigation navigation"
        >
          <p className="nav__section-label">Primary</p>
          <ul className="nav__list">
            {primary.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  end={"end" in item ? item.end : false}
                  onClick={() => setNavOpen(false)}
                  className={({ isActive }) =>
                    isActive ? "nav__item nav__item--active" : "nav__item"
                  }
                >
                  <span className="nav__item-label">{item.label}</span>
                  <span className="nav__hint">{item.job}</span>
                </NavLink>
              </li>
            ))}
          </ul>

          <p className="nav__section-label">More</p>
          <ul className="nav__list">
            {more.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  onClick={() => setNavOpen(false)}
                  className={({ isActive }) =>
                    isActive ? "nav__item nav__item--active" : "nav__item"
                  }
                >
                  <span className="nav__item-label">{item.label}</span>
                  <span className="nav__hint">{item.job}</span>
                </NavLink>
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
