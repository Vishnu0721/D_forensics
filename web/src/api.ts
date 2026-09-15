/** Typed fetch helpers for the Digital Forensics web API. */

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
  next_step: string;
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

export type EventFilter =
  | "all"
  | "user"
  | "background"
  | "findings"
  | "linked"
  | "unclear";

export type FindingsResponse = {
  findings: FindingSummary[];
  stories: FindingSummary[];
};

export type GraphNode = {
  id: string;
  label: string;
  kind: string;
  story: string;
};

export type GraphEdge = {
  id: string;
  source: string;
  target: string;
  relationship: string;
  confidence?: number | null;
};

export type GraphResponse = {
  view: "simple" | "detailed";
  nodes: GraphNode[];
  edges: GraphEdge[];
};

export type IntegrityRow = {
  evidence_id: string;
  what: string;
  sha256_hash: string;
  status: string;
  status_label: string;
  collected_at?: string | null;
};

export type IntegrityResponse = {
  items: IntegrityRow[];
  legend: Record<string, string>;
};

export type LiveStatus = {
  available: boolean;
  running: boolean;
  case_id?: string | null;
  started_at?: string | null;
  events_captured: number;
  last_error?: string | null;
  collectors?: string[];
  note?: string;
  this_case_active?: boolean;
};

export type DesktopBridgeScanItem = {
  case_folder: string;
  path: string;
  file_count: number;
};

export type DesktopBridgeImportResult = {
  imported_count?: number;
  skipped_count?: number;
  source_dir?: string;
  recent_evidence?: EvidenceSummary[];
  [key: string]: unknown;
};

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function parseError(res: Response): Promise<string> {
  try {
    const data = (await res.json()) as { detail?: unknown };
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail)) {
      return data.detail
        .map((d) => (typeof d === "object" && d && "msg" in d ? String((d as { msg: unknown }).msg) : String(d)))
        .join("; ");
    }
    return res.statusText || `Request failed (${res.status})`;
  } catch {
    return res.statusText || `Request failed (${res.status})`;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) {
    throw new ApiError(res.status, await parseError(res));
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export async function listCases(): Promise<CaseSummary[]> {
  const data = await request<{ items: CaseSummary[] }>("/api/v1/cases");
  return data.items;
}

export async function createCase(body: {
  name: string;
  description?: string;
}): Promise<CaseSummary> {
  return request<CaseSummary>("/api/v1/cases", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function getCase(caseId: string): Promise<CaseDetail> {
  return request<CaseDetail>(`/api/v1/cases/${caseId}`);
}

export async function listEvidence(caseId: string): Promise<EvidenceSummary[]> {
  const data = await request<{ items: EvidenceSummary[] }>(
    `/api/v1/cases/${caseId}/evidence`,
  );
  return data.items;
}

export async function uploadEvidence(
  caseId: string,
  file: File,
  sourceHint?: string,
): Promise<EvidenceSummary> {
  const form = new FormData();
  form.append("file", file);
  if (sourceHint) form.append("source_hint", sourceHint);
  return request<EvidenceSummary>(`/api/v1/cases/${caseId}/evidence`, {
    method: "POST",
    body: form,
  });
}

export async function startAnalysis(
  caseId: string,
  evidenceIds?: string[],
): Promise<JobStatus> {
  return request<JobStatus>(`/api/v1/cases/${caseId}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(evidenceIds ? { evidence_ids: evidenceIds } : {}),
  });
}

export async function getJob(jobId: string): Promise<JobStatus> {
  return request<JobStatus>(`/api/v1/jobs/${jobId}`);
}

export async function pollJob(
  jobId: string,
  opts?: {
    intervalMs?: number;
    onUpdate?: (job: JobStatus) => void;
    signal?: AbortSignal;
  },
): Promise<JobStatus> {
  const intervalMs = opts?.intervalMs ?? 800;
  for (;;) {
    if (opts?.signal?.aborted) {
      throw new DOMException("Aborted", "AbortError");
    }
    const job = await getJob(jobId);
    opts?.onUpdate?.(job);
    if (job.status === "completed" || job.status === "failed") return job;
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
}

export async function listEvents(
  caseId: string,
  filter: EventFilter = "all",
  opts?: { limit?: number; offset?: number },
): Promise<EventPage> {
  const params = new URLSearchParams({ filter });
  if (opts?.limit != null) params.set("limit", String(opts.limit));
  if (opts?.offset != null) params.set("offset", String(opts.offset));
  return request<EventPage>(`/api/v1/cases/${caseId}/events?${params}`);
}

export async function getEvent(
  caseId: string,
  eventId: string,
): Promise<EventDetail> {
  return request<EventDetail>(`/api/v1/cases/${caseId}/events/${eventId}`);
}

export async function listFindings(caseId: string): Promise<FindingsResponse> {
  return request<FindingsResponse>(`/api/v1/cases/${caseId}/findings`);
}

export async function getGraph(
  caseId: string,
  view: "simple" | "detailed" = "simple",
): Promise<GraphResponse> {
  return request<GraphResponse>(
    `/api/v1/cases/${caseId}/graph?view=${encodeURIComponent(view)}`,
  );
}

export async function listIntegrity(caseId: string): Promise<IntegrityResponse> {
  return request<IntegrityResponse>(`/api/v1/cases/${caseId}/integrity`);
}

export async function verifyIntegrity(
  caseId: string,
): Promise<IntegrityResponse> {
  return request<IntegrityResponse>(`/api/v1/cases/${caseId}/integrity`, {
    method: "POST",
  });
}

export function exportCaseUrl(
  caseId: string,
  format: "markdown" | "html" = "markdown",
): string {
  return `/api/v1/cases/${caseId}/export?format=${format}`;
}

export async function getCaseLiveStatus(caseId: string): Promise<LiveStatus> {
  return request<LiveStatus>(`/api/v1/cases/${caseId}/live`);
}

export async function startLive(caseId: string): Promise<LiveStatus> {
  return request<LiveStatus>(`/api/v1/cases/${caseId}/live/start`, {
    method: "POST",
  });
}

export async function stopLive(caseId: string): Promise<LiveStatus> {
  return request<LiveStatus>(`/api/v1/cases/${caseId}/live/stop`, {
    method: "POST",
  });
}

export async function listDesktopBridge(): Promise<DesktopBridgeScanItem[]> {
  const data = await request<{ items: DesktopBridgeScanItem[] }>(
    "/api/v1/bridge/desktop",
  );
  return data.items;
}

export async function importDesktopBridge(
  caseId: string,
  sourceDir: string,
): Promise<DesktopBridgeImportResult> {
  return request<DesktopBridgeImportResult>(
    `/api/v1/cases/${caseId}/bridge/desktop`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source_dir: sourceDir }),
    },
  );
}
