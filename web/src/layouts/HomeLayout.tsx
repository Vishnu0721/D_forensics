import { Outlet } from "react-router-dom";
import { AppHeader } from "../components/AppHeader";
import { ApiBanner } from "../components/ApiBanner";
import { GuidedTour } from "../components/GuidedTour";

export function HomeLayout() {
  return (
    <div className="app-frame">
      <AppHeader />
      <ApiBanner />
      <main className="main main--home">
        <Outlet />
      </main>
      <GuidedTour />
    </div>
  );
}
