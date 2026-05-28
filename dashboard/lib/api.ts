/**
 * Sentinel Dashboard — API client for fetching trace data from the gateway.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface Span {
  id: string;
  trace_id: string;
  parent_span_id: string | null;
  name: string;
  span_type: string;
  start_ts: string;
  end_ts: string | null;
  status: string;
  attributes: Record<string, unknown>;
}

export interface Trace {
  id: string;
  project_id: string;
  provider: string;
  model: string;
  latency_ms: number;
  prompt_tokens: number;
  completion_tokens: number;
  cost_usd: number;
  status_code: number;
  request_body: Record<string, unknown> | null;
  response_body: Record<string, unknown> | null;
  error_message: string | null;
  created_at: string;
  spans?: Span[];
}

export interface TraceListResponse {
  traces: Trace[];
  next_cursor: string | null;
  total_count: number;
}

export interface TraceStats {
  total_traces: number;
  total_cost_usd: number;
  avg_latency_ms: number;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  traces_by_provider: Record<string, number>;
  traces_by_model: Record<string, number>;
  error_count: number;
}

export async function fetchTraces(params?: {
  cursor?: string;
  limit?: number;
  provider?: string;
  model?: string;
}): Promise<TraceListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.cursor) searchParams.set("cursor", params.cursor);
  if (params?.limit) searchParams.set("limit", String(params.limit));
  if (params?.provider) searchParams.set("provider", params.provider);
  if (params?.model) searchParams.set("model", params.model);

  const url = `${API_URL}/api/traces?${searchParams.toString()}`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to fetch traces: ${res.status}`);
  return res.json();
}

export async function fetchTrace(id: string): Promise<Trace> {
  const res = await fetch(`${API_URL}/api/traces/${id}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to fetch trace: ${res.status}`);
  return res.json();
}

export async function fetchTraceStats(): Promise<TraceStats> {
  const res = await fetch(`${API_URL}/api/traces/stats`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to fetch stats: ${res.status}`);
  return res.json();
}

/* ────────────────────────────────────────────────────────────────
   Timeseries (Week 10)
   ──────────────────────────────────────────────────────────────── */

export interface TimeseriesPoint {
  bucket: string;
  count: number;
  cost_usd: number;
  avg_latency_ms: number;
}

export interface TimeseriesResponse {
  bucket: "hour" | "day";
  points: TimeseriesPoint[];
}

export async function fetchTraceTimeseries(
  hours = 24,
  bucket: "hour" | "day" = "hour",
): Promise<TimeseriesResponse> {
  const url = `${API_URL}/api/traces/timeseries?hours=${hours}&bucket=${bucket}`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to fetch timeseries: ${res.status}`);
  return res.json();
}

/* ────────────────────────────────────────────────────────────────
   Audit (Week 9 — surfaced in Week 10 UI)
   ──────────────────────────────────────────────────────────────── */

export interface AuditClassifier {
  id: string;
  project_id: string;
  name: string;
  match_jsonpath: string;
  risk_tier: string;
  enabled: boolean;
}

export async function fetchClassifiers(projectId?: string): Promise<AuditClassifier[]> {
  const qs = projectId ? `?project_id=${projectId}` : "";
  const res = await fetch(`${API_URL}/api/audit/classifiers${qs}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to fetch classifiers: ${res.status}`);
  const body = await res.json();
  return body.classifiers;
}

export async function createClassifier(payload: {
  project_id: string;
  name: string;
  match_jsonpath: string;
  risk_tier: string;
}): Promise<AuditClassifier> {
  const res = await fetch(`${API_URL}/api/audit/classifiers`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Failed to create classifier: ${res.status}`);
  return res.json();
}

export async function deleteClassifier(id: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/audit/classifiers/${id}`, { method: "DELETE" });
  if (!res.ok && res.status !== 204) {
    throw new Error(`Failed to delete classifier: ${res.status}`);
  }
}

export async function verifyAuditChain(projectId: string): Promise<{
  ok: boolean;
  checked: number;
  error: string | null;
}> {
  const res = await fetch(`${API_URL}/api/audit/verify?project_id=${projectId}`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Failed to verify: ${res.status}`);
  return res.json();
}

/* ────────────────────────────────────────────────────────────────
   Alerts (Week 10)
   ──────────────────────────────────────────────────────────────── */

export interface Alert {
  id: string;
  project_id: string;
  name: string;
  metric: "cost_per_hour_usd" | "error_rate_pct" | "latency_p95_ms";
  comparator: "gt" | "lt";
  threshold: number;
  window_minutes: number;
  enabled: boolean;
  last_checked_at: string | null;
  last_value: number | null;
  last_triggered: boolean;
}

export async function fetchAlerts(projectId?: string): Promise<Alert[]> {
  const qs = projectId ? `?project_id=${projectId}` : "";
  const res = await fetch(`${API_URL}/api/alerts${qs}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to fetch alerts: ${res.status}`);
  const body = await res.json();
  return body.alerts;
}

export async function createAlert(payload: {
  project_id: string;
  name: string;
  metric: Alert["metric"];
  comparator: Alert["comparator"];
  threshold: number;
  window_minutes: number;
}): Promise<Alert> {
  const res = await fetch(`${API_URL}/api/alerts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Failed to create alert: ${res.status}`);
  return res.json();
}

export async function deleteAlert(id: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/alerts/${id}`, { method: "DELETE" });
  if (!res.ok && res.status !== 204) {
    throw new Error(`Failed to delete alert: ${res.status}`);
  }
}

export async function checkAlert(id: string): Promise<{
  alert_id: string;
  metric: string;
  value: number;
  threshold: number;
  comparator: string;
  triggered: boolean;
  checked_at: string;
}> {
  const res = await fetch(`${API_URL}/api/alerts/${id}/check`, { method: "POST" });
  if (!res.ok) throw new Error(`Failed to check alert: ${res.status}`);
  return res.json();
}

/* ────────────────────────────────────────────────────────────────
   Projects helper (Week 10 — needed by audit/alerts pages)
   ──────────────────────────────────────────────────────────────── */

export interface Project {
  id: string;
  name: string;
  api_key: string;
}

export async function fetchProjects(): Promise<Project[]> {
  const res = await fetch(`${API_URL}/api/projects`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to fetch projects: ${res.status}`);
  const body = await res.json();
  return body.projects;
}

/* ────────────────────────────────────────────────────────────────
   Annotations (LangSmith-style human feedback on traces)
   ──────────────────────────────────────────────────────────────── */

export interface Annotation {
  id: string;
  trace_id: string;
  rating: "thumbs_up" | "thumbs_down" | "neutral";
  dimension: string;
  comment: string | null;
  author: string | null;
  created_at: string;
}

export async function fetchAnnotations(traceId: string): Promise<Annotation[]> {
  const res = await fetch(`${API_URL}/api/annotations?trace_id=${traceId}`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Failed to fetch annotations: ${res.status}`);
  return (await res.json()).annotations;
}

export async function createAnnotation(payload: {
  trace_id: string;
  rating: Annotation["rating"];
  dimension?: string;
  comment?: string | null;
  author?: string | null;
}): Promise<Annotation> {
  const res = await fetch(`${API_URL}/api/annotations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Failed to create annotation: ${res.status}`);
  return res.json();
}

export async function deleteAnnotation(id: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/annotations/${id}`, { method: "DELETE" });
  if (!res.ok && res.status !== 204) {
    throw new Error(`Failed to delete annotation: ${res.status}`);
  }
}

/* ────────────────────────────────────────────────────────────────
   Sessions (conversation threads)
   ──────────────────────────────────────────────────────────────── */

export interface SessionSummary {
  id: string;
  project_id: string;
  name: string | null;
  external_id: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
  last_seen_at: string;
  trace_count: number;
}

export async function fetchSessions(projectId?: string): Promise<SessionSummary[]> {
  const qs = projectId ? `?project_id=${projectId}` : "";
  const res = await fetch(`${API_URL}/api/sessions${qs}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to fetch sessions: ${res.status}`);
  return (await res.json()).sessions;
}

export async function fetchSession(id: string): Promise<{
  session: SessionSummary;
  trace_ids: string[];
}> {
  const res = await fetch(`${API_URL}/api/sessions/${id}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to fetch session: ${res.status}`);
  return res.json();
}

/* ────────────────────────────────────────────────────────────────
   Datasets (Phase 3 — Session 3)
   ──────────────────────────────────────────────────────────────── */

export interface Dataset {
  id: string;
  project_id: string;
  name: string;
  description: string | null;
  created_at: string;
  item_count: number;
}

export interface DatasetItem {
  id: string;
  dataset_id: string;
  input: Record<string, unknown>;
  expected_output: Record<string, unknown> | null;
  item_metadata: Record<string, unknown>;
  source_trace_id: string | null;
  created_at: string;
}

export async function fetchDatasets(projectId: string): Promise<Dataset[]> {
  const res = await fetch(
    `${API_URL}/api/datasets?project_id=${projectId}`,
    { cache: "no-store" },
  );
  if (!res.ok) throw new Error(`Failed to fetch datasets: ${res.status}`);
  return res.json();
}

export async function fetchDataset(id: string): Promise<Dataset> {
  const res = await fetch(`${API_URL}/api/datasets/${id}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to fetch dataset: ${res.status}`);
  return res.json();
}

export async function createDataset(payload: {
  project_id: string;
  name: string;
  description?: string | null;
}): Promise<Dataset> {
  const res = await fetch(`${API_URL}/api/datasets`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Failed to create dataset: ${res.status}`);
  return res.json();
}

export async function deleteDataset(id: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/datasets/${id}`, { method: "DELETE" });
  if (!res.ok && res.status !== 204)
    throw new Error(`Failed to delete dataset: ${res.status}`);
}

export async function fetchDatasetItems(
  datasetId: string,
): Promise<DatasetItem[]> {
  const res = await fetch(
    `${API_URL}/api/datasets/${datasetId}/items`,
    { cache: "no-store" },
  );
  if (!res.ok) throw new Error(`Failed to fetch items: ${res.status}`);
  return res.json();
}

export async function addDatasetItem(
  datasetId: string,
  payload: {
    input: Record<string, unknown>;
    expected_output?: Record<string, unknown> | null;
    item_metadata?: Record<string, unknown>;
    source_trace_id?: string | null;
  },
): Promise<DatasetItem> {
  const res = await fetch(`${API_URL}/api/datasets/${datasetId}/items`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Failed to add item: ${res.status}`);
  return res.json();
}

export async function deleteDatasetItem(
  datasetId: string,
  itemId: string,
): Promise<void> {
  const res = await fetch(
    `${API_URL}/api/datasets/${datasetId}/items/${itemId}`,
    { method: "DELETE" },
  );
  if (!res.ok && res.status !== 204)
    throw new Error(`Failed to delete item: ${res.status}`);
}
