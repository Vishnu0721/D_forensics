import { useCallback, useEffect, useState } from "react";
import { Link, useOutletContext, useParams } from "react-router-dom";
import {
  exportCaseUrl,
  getCase,
  getCaseLiveStatus,
  pollJob,
  startAnalysis,
  startLive,
  stopLive,
  type LiveStatus,
} from "../api";
import type { CaseOutletContext } from "../layouts/CaseLayout";

export function CaseOverviewPage() {
  const { caseId = "" } = useParams();
  const { caseDetail, setCaseDetail } = useOutletContext<CaseOutletContext>();
  const [live, setLive] = useState<LiveStatus | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [liveBusy, setLiveBusy] = useState(false);
  const [jobMessage, setJobMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const [detail, liveStatus] = await Promise.all([
      getCase(caseId),
      getCaseLiveStatus(caseId),
    ]);
    setCaseDetail(detail);
    setLive(liveStatus);
  }, [caseId, setCaseDetail]);

  useEffect(() => {
    let cancelled = false;
    refresh()
      .then(() => {
        if (!cancelled) setError(null);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Could not load case");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [refresh]);

  async function onAnalyze() {
    setAnalyzing(true);
    setError(null);
    setJobMessage("Starting analysis…");
    try {
      const job = await startAnalysis(caseId);
      const final = await pollJob(job.id, {
        onUpdate: (j) => setJobMessage(j.message || j.status),
      });
      if (final.status === "failed") {
        setError(final.error || "Analysis failed");
      } else {
        setJobMessage("Analysis complete");
      }
      await refresh();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setAnalyzing(false);
    }
  }

  async function onLiveToggle() {
    setError(null);
    if (!live?.this_case_active) {
      const ok = window.confirm(
        "Start live watch on this PC?\n\nThis records process and network activity locally under web_data/ (same idea as the desktop Start Monitoring button). Stop before Analyze.",
      );
      if (!ok) return;
    }
    setLiveBusy(true);
    try {
      if (live?.this_case_active) {
        await stopLive(caseId);
      } else {
        await startLive(caseId);
      }
      await refresh();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Live control failed");
    } finally {
      setLiveBusy(false);
    }
  }

  if (error && !caseDetail) {
    return <p className="status-err">{error}</p>;
  }

  if (!caseDetail) {
    return <p className="muted">Loading overview…</p>;
  }

  const cards = [
    { label: "Activity", value: caseDetail.event_count, hint: "Timeline events" },
    {
      label: "Needs a look",
      value: caseDetail.finding_count,
      hint: "Findings that need attention",
    },
    {
      label: "Links",
      value: caseDetail.relationship_count,
      hint: "Connections between things",
    },
    {
      label: "Saved records",
      value: caseDetail.evidence_count,
      hint: "Imported evidence files",
    },
  ];

  return (
    <div>
      <h1>{caseDetail.name}</h1>
      {caseDetail.description && <p className="lead">{caseDetail.description}</p>}

      <section className="panel next-step">
        <h2>What next?</h2>
        <p>{caseDetail.next_step || "Open Import to add evidence, then Analyze."}</p>
        <div className="btn-row">
          <button
            type="button"
            className="btn btn--primary"
            disabled={
              analyzing ||
              caseDetail.evidence_count === 0 ||
              Boolean(live?.this_case_active)
            }
            onClick={() => void onAnalyze()}
            title={
              live?.this_case_active
                ? "Stop live watch before Analyze"
                : undefined
            }
          >
            {analyzing ? "Analyzing…" : "Analyze"}
          </button>
          <Link className="btn btn--ghost" to={`/cases/${caseId}/import`}>
            Import evidence
          </Link>
        </div>
        {jobMessage && <p className="muted">{jobMessage}</p>}
        {error && <p className="status-err">{error}</p>}
      </section>

      <section className="stat-grid" aria-label="Case summary">
        {cards.map((c) => (
          <div key={c.label} className="stat-card">
            <p className="stat-card__value">{c.value}</p>
            <p className="stat-card__label">{c.label}</p>
            <p className="stat-card__hint muted">{c.hint}</p>
          </div>
        ))}
      </section>

      <section className="panel">
        <h2>Top findings</h2>
        {caseDetail.top_findings.length === 0 ? (
          <div className="empty-inline">
            <p className="muted">Nothing flagged yet. Import evidence and run Analyze.</p>
            <Link className="btn btn--ghost" to={`/cases/${caseId}/import`}>
              Import evidence
            </Link>
          </div>
        ) : (
          <ul className="finding-list">
            {caseDetail.top_findings.map((f) => (
              <li key={f.id} className="finding-item">
                <span className={`badge badge--${sev(f.severity_label)}`}>
                  {f.severity_label}
                </span>
                <div>
                  <strong>{f.headline}</strong>
                  {f.detail && <p className="muted">{f.detail}</p>}
                </div>
              </li>
            ))}
          </ul>
        )}
        {caseDetail.finding_count + caseDetail.story_count > 0 && (
          <Link className="text-link" to={`/cases/${caseId}/findings`}>
            See all findings
          </Link>
        )}
      </section>

      <section className="panel">
        <h2>Export</h2>
        <p className="muted">Download a plain report of this investigation.</p>
        <div className="btn-row">
          <a className="btn btn--ghost" href={exportCaseUrl(caseId, "markdown")}>
            Markdown
          </a>
          <a className="btn btn--ghost" href={exportCaseUrl(caseId, "html")}>
            HTML
          </a>
        </div>
      </section>

      <section className="panel">
        <h2>Live watch (this PC)</h2>
        <p className="muted">
          Optional: capture process and network activity while you work. Stop live
          watch before Analyze.
        </p>
        {live && (
          <p>
            Status:{" "}
            <strong>
              {live.this_case_active
                ? "Watching this case"
                : live.running
                  ? "Watching another case"
                  : "Stopped"}
            </strong>
            {live.this_case_active
              ? ` · ${live.events_captured} event${live.events_captured === 1 ? "" : "s"} captured`
              : null}
          </p>
        )}
        <button
          type="button"
          className="btn btn--ghost"
          disabled={
            liveBusy ||
            analyzing ||
            Boolean(live?.running && !live.this_case_active)
          }
          onClick={() => void onLiveToggle()}
          title={
            live?.running && !live.this_case_active
              ? "Stop live watch on the other case first"
              : analyzing
                ? "Wait for analysis to finish"
                : undefined
          }
        >
          {liveBusy
            ? "Please wait…"
            : live?.this_case_active
              ? "Stop live watch"
              : live?.running
                ? "Live watch busy (other case)"
                : "Start live watch"}
        </button>
      </section>

      {caseDetail.last_analysis_at && (
        <p className="muted page-foot">
          Last analyzed {formatWhen(caseDetail.last_analysis_at)}
        </p>
      )}
    </div>
  );
}

function sev(label: string): string {
  const lower = label.toLowerCase();
  if (lower.includes("warn") || lower.includes("look") || lower.includes("medium")) {
    return "warn";
  }
  if (lower.includes("high") || lower.includes("critical") || lower.includes("danger")) {
    return "danger";
  }
  return "ok";
}

function formatWhen(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}
