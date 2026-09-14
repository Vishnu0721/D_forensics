/** Thin fetch helpers for the web API (Vite proxies /api and /health). */

export type CaseSummary = {
  id: string;
  name: string;
  description?: string | null;
  mode: "imported" | "live";
  created_at?: string | null;
  evidence_count: number;
  event_count: number;
};

export type FindingSummary = {
  id: string;
  kind: "rule" | "story";
  headline: string;
  detail: string;
  severity_label: string;
  related_event_ids: string[];
};

export type CaseDetail = CaseSummary & {
  last_analysis_at?: string | null;
  top_findings: FindingSummary[];
  relationship_count: number;
  finding_count: number;
  story_count: number;
};

export type EvidenceSummary = {
  id: string;
  filename: string;
  source_type: string;
  sha256_hash: string;
  file_size: number;
  integrity_status: string;
  status_label: string;
  created_at?: string | null;
};

export type JobStatus = {
  id: string;
  case_id: string;
  status: "queued" | "running" | "completed" | "failed";
  progress: number;
  message: string;
  error?: string | null;
  result_summary?: Record<string, unknown> | null;
};

export type EventFilter = "all" | "user" | "findings" | "linked" | "unclear";

export type EventSummary = {
  id: string;
  timestamp?: string | null;
  source_type: string;
  event_type: string;
  classification: string;
  headline: string;
  detail: string;
  severity_label: string;
};

export type EventDetail = EventSummary & {
  evidence_id?: string | null;
  technical: Record<string, unknown>;
};

export type EventPage = {
  total: number;
  items: EventSummary[];
};

export type FindingsResponse = {
  findings: FindingSummary[];
  stories: FindingSummary[];
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return res.json() as Promise<T>;
}

export function listCases() {
  return request<{ items: CaseSummary[] }>("/api/v1/cases");
}

export function createCase(name: string, description?: string) {
  return request<CaseSummary>("/api/v1/cases", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, description: description || null }),
  });
}

export function getCase(caseId: string) {
  return request<CaseDetail>(`/api/v1/cases/${caseId}`);
}

export function listEvidence(caseId: string) {
  return request<{ items: EvidenceSummary[] }>(`/api/v1/cases/${caseId}/evidence`);
}

export async function uploadEvidence(caseId: string, file: File, sourceHint?: string) {
  const form = new FormData();
  form.append("file", file);
  if (sourceHint) form.append("source_hint", sourceHint);
  return request<EvidenceSummary>(`/api/v1/cases/${caseId}/evidence`, {
    method: "POST",
    body: form,
  });
}

export function startAnalysis(caseId: string, evidenceIds?: string[]) {
  return request<JobStatus>(`/api/v1/cases/${caseId}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ evidence_ids: evidenceIds ?? null }),
  });
}

export function getJob(jobId: string) {
  return request<JobStatus>(`/api/v1/jobs/${jobId}`);
}

export async function pollJob(
  jobId: string,
  onUpdate?: (job: JobStatus) => void,
  intervalMs = 700,
): Promise<JobStatus> {
  for (;;) {
    const job = await getJob(jobId);
    onUpdate?.(job);
    if (job.status === "completed" || job.status === "failed") {
      return job;
    }
    await new Promise((r) => setTimeout(r, intervalMs));
  }
}

export function listEvents(
  caseId: string,
  opts: {
    filter?: EventFilter;
    evidenceId?: string;
    limit?: number;
    offset?: number;
  } = {},
) {
  const params = new URLSearchParams();
  params.set("filter", opts.filter ?? "all");
  params.set("limit", String(opts.limit ?? 100));
  params.set("offset", String(opts.offset ?? 0));
  if (opts.evidenceId) params.set("evidence_id", opts.evidenceId);
  return request<EventPage>(`/api/v1/cases/${caseId}/events?${params}`);
}

export function getEvent(caseId: string, eventId: string) {
  return request<EventDetail>(`/api/v1/cases/${caseId}/events/${eventId}`);
}

export function listFindings(caseId: string) {
  return request<FindingsResponse>(`/api/v1/cases/${caseId}/findings`);
}
