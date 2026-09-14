type Props = { title: string; body: string };

export function ComingSoonPage({ title, body }: Props) {
  return (
    <section className="panel">
      <span className="badge badge--phase">Phase 3–4</span>
      <h1>{title}</h1>
      <p className="muted">{body}</p>
      <p className="muted">API endpoints for this view already exist — UI wiring comes next.</p>
    </section>
  );
}
