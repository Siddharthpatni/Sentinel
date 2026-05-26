/**
 * Sentinel Dashboard — API client for fetching trace data from the gateway.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
