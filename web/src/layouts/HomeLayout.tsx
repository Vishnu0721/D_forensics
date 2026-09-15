import { Outlet } from "react-router-dom";
import { AppHeader } from "../components/AppHeader";
import { GuidedTour } from "../components/GuidedTour";

export function HomeLayout() {
  return (
    <div className="app-frame">
      <AppHeader />
      <main className="main main--home">
        <Outlet />
      </main>
      <GuidedTour />
    </div>
  );
}
