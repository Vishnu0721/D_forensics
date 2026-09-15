import { Link } from "react-router-dom";
import { PRODUCT_NAME } from "../product";

type AppHeaderProps = {
  title?: string;
  subtitle?: string;
  backTo?: string;
  backLabel?: string;
};

export function AppHeader({
  title = PRODUCT_NAME,
  subtitle,
  backTo,
  backLabel = "All investigations",
}: AppHeaderProps) {
  return (
    <header className="header">
      <div className="header__left">
        <Link className="header__brand" to="/">
          <span className="header__mark" aria-hidden />
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
