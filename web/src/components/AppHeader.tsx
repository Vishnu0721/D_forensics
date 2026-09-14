import { Link, NavLink } from "react-router-dom";
import { useTheme } from "../theme/ThemeProvider";

type Props = {
  caseId?: string;
  caseName?: string;
};

export function AppHeader({ caseId, caseName }: Props) {
  const { theme, toggleTheme } = useTheme();

  return (
    <header className="app-header">
      <div className="app-header__inner">
        <div className="app-header__brand">
          <Link to="/" className="app-header__logo">
            <span className="app-header__mark" aria-hidden />
            <span>
              <strong>Digital Forensics</strong>
              <span className="app-header__tagline">Investigate evidence clearly</span>
            </span>
          </Link>
          {caseName && (
            <span className="app-header__case muted" title={caseName}>
              / {caseName}
            </span>
          )}
        </div>

        <nav className="app-header__nav" aria-label="Site">
          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              isActive ? "app-header__link app-header__link--active" : "app-header__link"
            }
          >
            Home
          </NavLink>
          {caseId && (
            <NavLink
              to={`/cases/${caseId}`}
              end
              className={({ isActive }) =>
                isActive ? "app-header__link app-header__link--active" : "app-header__link"
              }
            >
              Case
            </NavLink>
          )}
          <Link to="/cases/new" className="app-header__link">
            New investigation
          </Link>
          <button
            type="button"
            className="theme-toggle"
            onClick={toggleTheme}
            aria-label={theme === "light" ? "Switch to dark mode" : "Switch to light mode"}
          >
            {theme === "light" ? "Dark" : "Light"}
          </button>
        </nav>
      </div>
    </header>
  );
}
