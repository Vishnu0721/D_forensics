import { Navigate, Route, Routes } from "react-router-dom";
import { CaseLayout } from "./layouts/CaseLayout";
import { CaseOverviewPage } from "./pages/CaseOverviewPage";
import { ComingSoonPage } from "./pages/ComingSoonPage";
import { FindingsPage } from "./pages/FindingsPage";
import { HomePage } from "./pages/HomePage";
import { ImportPage } from "./pages/ImportPage";
import { NewCasePage } from "./pages/NewCasePage";
import { TimelinePage } from "./pages/TimelinePage";

export function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/cases/new" element={<NewCasePage />} />
      <Route path="/cases/:caseId" element={<CaseLayout />}>
        <Route index element={<CaseOverviewPage />} />
        <Route path="import" element={<ImportPage />} />
        <Route path="timeline" element={<TimelinePage />} />
        <Route path="findings" element={<FindingsPage />} />
        <Route
          path="connections"
          element={
            <ComingSoonPage
              title="Connections"
              body="Evidence graph UI arrives in Phase 4. Graph API is ready now."
            />
          }
        />
        <Route
          path="integrity"
          element={
            <ComingSoonPage
              title="Integrity"
              body="Integrity table UI in Phase 4. Verify API is ready now."
            />
          }
        />
        <Route
          path="settings"
          element={
            <ComingSoonPage
              title="Settings"
              body="About and data paths. Auth is not required in v1."
            />
          }
        />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
