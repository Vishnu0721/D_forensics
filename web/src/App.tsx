import { Navigate, Route, Routes } from "react-router-dom";
import { HomeLayout } from "./layouts/HomeLayout";
import { CaseLayout } from "./layouts/CaseLayout";
import { HomePage } from "./pages/HomePage";
import { NewCasePage } from "./pages/NewCasePage";
import { CaseOverviewPage } from "./pages/CaseOverviewPage";
import { TimelinePage } from "./pages/TimelinePage";
import { ConnectionsPage } from "./pages/ConnectionsPage";
import { ImportPage } from "./pages/ImportPage";
import { FindingsPage } from "./pages/FindingsPage";
import { IntegrityPage } from "./pages/IntegrityPage";
import { SettingsPage } from "./pages/SettingsPage";

export function App() {
  return (
    <Routes>
      <Route element={<HomeLayout />}>
        <Route index element={<HomePage />} />
        <Route path="cases/new" element={<NewCasePage />} />
      </Route>

      <Route path="cases/:caseId" element={<CaseLayout />}>
        <Route index element={<CaseOverviewPage />} />
        <Route path="timeline" element={<TimelinePage />} />
        <Route path="connections" element={<ConnectionsPage />} />
        <Route path="import" element={<ImportPage />} />
        <Route path="findings" element={<FindingsPage />} />
        <Route path="integrity" element={<IntegrityPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
