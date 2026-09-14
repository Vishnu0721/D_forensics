import { Navigate, Route, Routes } from "react-router-dom";
import { CaseLayout } from "./layouts/CaseLayout";
import { HomeLayout } from "./layouts/HomeLayout";
import { CaseOverviewPage } from "./pages/CaseOverviewPage";
import { ConnectionsPage } from "./pages/ConnectionsPage";
import { FindingsPage } from "./pages/FindingsPage";
import { HomePage } from "./pages/HomePage";
import { ImportPage } from "./pages/ImportPage";
import { IntegrityPage } from "./pages/IntegrityPage";
import { NewCasePage } from "./pages/NewCasePage";
import { SettingsPage } from "./pages/SettingsPage";
import { TimelinePage } from "./pages/TimelinePage";

export function App() {
  return (
    <Routes>
      <Route element={<HomeLayout />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/cases/new" element={<NewCasePage />} />
      </Route>
      <Route path="/cases/:caseId" element={<CaseLayout />}>
        <Route index element={<CaseOverviewPage />} />
        <Route path="import" element={<ImportPage />} />
        <Route path="timeline" element={<TimelinePage />} />
        <Route path="findings" element={<FindingsPage />} />
        <Route path="connections" element={<ConnectionsPage />} />
        <Route path="integrity" element={<IntegrityPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
