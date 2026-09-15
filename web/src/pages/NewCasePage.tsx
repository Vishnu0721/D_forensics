import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createCase } from "../api";

export function NewCasePage() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) {
      setError("Give this investigation a name.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const created = await createCase({
        name: trimmed,
        description: description.trim() || undefined,
      });
      navigate(`/cases/${created.id}`, { replace: true });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Could not create case");
      setBusy(false);
    }
  }

  return (
    <div>
      <h1>New investigation</h1>
      <p className="lead">Name this investigation, then import evidence.</p>

      <form className="panel form" onSubmit={(e) => void onSubmit(e)}>
        <label className="field">
          <span>Name</span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Laptop review — Sept 2025"
            maxLength={200}
            autoFocus
            required
          />
        </label>
        <label className="field">
          <span>Description (optional)</span>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            placeholder="Short note about what you are looking into"
          />
        </label>
        {error && <p className="status-err">{error}</p>}
        <div className="btn-row">
          <button type="submit" className="btn btn--primary" disabled={busy}>
            {busy ? "Creating…" : "Create investigation"}
          </button>
          <Link className="btn btn--ghost" to="/">
            Cancel
          </Link>
        </div>
      </form>
    </div>
  );
}
