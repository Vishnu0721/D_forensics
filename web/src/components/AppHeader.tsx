import { Link } from "react-router-dom";

type AppHeaderProps = {
  title?: string;
  subtitle?: string;
  backTo?: string;
  backLabel?: string;
};

export function AppHeader({
  title = "Digital Forensics",
  subtitle,
  backTo,
  backLabel = "All investigations",
}: AppHeaderProps) {
  return (
    <header className="header">
      <div className="header__left">
        <Link className="header__brand" to="/">
          {title}
        </Link>
        {subtitle && <span className="header__case">{subtitle}</span>}
      </div>
      <div className="header__meta">
        {backTo && (
          <Link className="header__back" to={backTo}>
            {backLabel}
          </Link>
        )}
      </div>
    </header>
  );
}
