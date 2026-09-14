import { useParams } from "react-router-dom";
import { ImportWizard } from "../components/ImportWizard";

export function ImportPage() {
  const { caseId } = useParams();
  if (!caseId) return null;

  return (
    <section className="panel">
      <span className="badge badge--phase">Phase 3 · import wizard</span>
      <h1>Import evidence</h1>
      <p className="muted">
        Four clear steps: choose a file, confirm the type, analyze, then open Timeline or Findings.
      </p>
      <ImportWizard caseId={caseId} />
    </section>
  );
}
