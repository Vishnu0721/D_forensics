import { Outlet } from "react-router-dom";
import { AppHeader } from "../components/AppHeader";

/** Full-width shell for Home and New investigation. */
export function HomeLayout() {
  return (
    <div className="app-frame">
      <AppHeader />
      <div className="page-wide">
        <Outlet />
      </div>
    </div>
  );
}
