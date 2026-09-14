import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createCase } from "../api";

export function NewCasePage() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const created = await createCase(name.trim(), description.trim());
      navigate(`/cases/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setSaving(false);
    }
  }

  return (
    <div className="home">
      <section className="panel narrow">
        <Link to="/" className="nav__back">
          ← Back
        </Link>
        <h1>New investigation</h1>
        <p className="muted">Give the case a clear name so anyone can find it later.</p>
        <form className="form" onSubmit={onSubmit}>
          <label>
            Case name
            <input
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Lab exercise — USB sample"
              maxLength={200}
            />
          </label>
          <label>
            Description (optional)
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              placeholder="What are you investigating?"
            />
          </label>
          {error && <p className="error">{error}</p>}
          <button className="btn btn--primary" type="submit" disabled={saving || !name.trim()}>
            {saving ? "Creating…" : "Create case"}
          </button>
        </form>
      </section>
    </div>
  );
}
