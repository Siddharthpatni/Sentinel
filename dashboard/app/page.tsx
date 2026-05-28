"use client";

import { useEffect, useState, useCallback, useMemo, useRef } from "react";
import { useRouter } from "next/navigation";
import {
  fetchTraces,
  fetchTraceStats,
  fetchTraceTimeseries,
  type TimeseriesPoint,
  type Trace,
  type TraceStats,
} from "@/lib/api";
import { Sparkline } from "@/components/sparkline";
import { ErrorBanner } from "@/components/error-banner";

/* ================================================================
   Helper Functions
   ================================================================ */

function formatCost(usd: number): string {
  if (usd < 0.01) return `$${usd.toFixed(6)}`;
  if (usd < 1) return `$${usd.toFixed(4)}`;
  return `$${usd.toFixed(2)}`;
}

function formatLatency(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function getProviderBadge(provider: string): string {
  switch (provider.toLowerCase()) {
    case "openai":
      return "badge-openai";
    case "anthropic":
      return "badge-anthropic";
    default:
      return "";
  }
}

function getStatusBadge(code: number): string {
  return code >= 400 ? "badge-error" : "badge-success";
}

/* ================================================================
   Stat Card Icons (inline SVG)
   ================================================================ */

function IconActivity() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
    </svg>
  );
}

function IconDollar() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <line x1="12" y1="1" x2="12" y2="23" />
      <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
    </svg>
  );
}

function IconClock() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  );
}

function IconZap() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
    </svg>
  );
}

function IconAlertTriangle() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}

function IconRefresh() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <polyline points="23 4 23 10 17 10" />
      <polyline points="1 20 1 14 7 14" />
      <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
    </svg>
  );
}

function IconRadar() {
  return (
    <svg
      width="28"
      height="28"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="12" cy="12" r="10" opacity="0.3" />
      <circle cx="12" cy="12" r="6" opacity="0.5" />
      <circle cx="12" cy="12" r="2" />
      <line x1="12" y1="2" x2="12" y2="6" />
    </svg>
  );
}

function IconEmpty() {
  return (
    <svg
      className="empty-state-icon"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
      <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
      <line x1="12" y1="22.08" x2="12" y2="12" />
    </svg>
  );
}

/* ================================================================
   Main Dashboard Page
   ================================================================ */

export default function DashboardPage() {
  const router = useRouter();
  const [traces, setTraces] = useState<Trace[]>([]);
  const [stats, setStats] = useState<TraceStats | null>(null);
  const [series, setSeries] = useState<TimeseriesPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [providerFilter, setProviderFilter] = useState("");
  const [modelFilter, setModelFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState<"" | "ok" | "err">("");
  const [err, setErr] = useState<string | null>(null);
  const [focusedRow, setFocusedRow] = useState(0);
  const rowRefs = useRef<(HTMLTableRowElement | null)[]>([]);

  const loadData = useCallback(async () => {
    try {
      setErr(null);
      const [tracesRes, statsRes, seriesRes] = await Promise.all([
        fetchTraces({
          limit: 50,
          provider: providerFilter || undefined,
          model: modelFilter || undefined,
        }),
        fetchTraceStats(),
        fetchTraceTimeseries(24, "hour"),
      ]);
      setTraces(tracesRes.traces);
      setNextCursor(tracesRes.next_cursor);
      setStats(statsRes);
      setSeries(seriesRes.points);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [providerFilter, modelFilter]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Auto-refresh every 3 seconds
  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(loadData, 3000);
    return () => clearInterval(interval);
  }, [autoRefresh, loadData]);

  const loadMore = async () => {
    if (!nextCursor || loadingMore) return;
    setLoadingMore(true);
    try {
      const res = await fetchTraces({
        cursor: nextCursor,
        limit: 50,
        provider: providerFilter || undefined,
        model: modelFilter || undefined,
      });
      setTraces((prev) => [...prev, ...res.traces]);
      setNextCursor(res.next_cursor);
    } catch (err) {
      console.error("Failed to load more:", err);
    } finally {
      setLoadingMore(false);
    }
  };

  // Status filter is client-side (server has no status param)
  const filteredTraces = useMemo(() => {
    if (!statusFilter) return traces;
    return traces.filter((t) =>
      statusFilter === "err" ? t.status_code >= 400 : t.status_code < 400,
    );
  }, [traces, statusFilter]);

  // Visible window rollup (sum across filteredTraces)
  const windowRollup = useMemo(() => {
    return filteredTraces.reduce(
      (acc, t) => ({
        cost: acc.cost + t.cost_usd,
        tokens: acc.tokens + t.prompt_tokens + t.completion_tokens,
        latencyTotal: acc.latencyTotal + t.latency_ms,
      }),
      { cost: 0, tokens: 0, latencyTotal: 0 },
    );
  }, [filteredTraces]);

  // Distinct models for filter dropdown (from current page)
  const modelOptions = useMemo(() => {
    const s = new Set<string>();
    traces.forEach((t) => s.add(t.model));
    if (stats) Object.keys(stats.traces_by_model).forEach((m) => s.add(m));
    return Array.from(s).sort();
  }, [traces, stats]);

  // Keyboard nav: j/k row movement, enter to open
  useEffect(() => {
    function handler(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;
      if (filteredTraces.length === 0) return;
      if (e.key === "j" || e.key === "ArrowDown") {
        e.preventDefault();
        setFocusedRow((i) => Math.min(filteredTraces.length - 1, i + 1));
      } else if (e.key === "k" || e.key === "ArrowUp") {
        e.preventDefault();
        setFocusedRow((i) => Math.max(0, i - 1));
      } else if (e.key === "Enter") {
        const t = filteredTraces[focusedRow];
        if (t) router.push(`/traces/${t.id}`);
      }
    }
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [filteredTraces, focusedRow, router]);

  useEffect(() => {
    const row = rowRefs.current[focusedRow];
    if (row) row.focus();
  }, [focusedRow]);

  return (
    <div className="min-h-screen flex flex-col" style={{ background: "var(--sentinel-bg)" }}>
      {/* ── Page header (page-scoped controls; global nav lives in layout NavBar) ── */}
      <header
        className="flex items-center justify-between px-6 py-4"
        style={{
          background: "transparent",
          borderBottom: "1px solid var(--sentinel-border-subtle)",
        }}
      >
        <div>
          <h1
            className="text-lg font-bold tracking-tight"
            style={{ color: "var(--sentinel-text-primary)" }}
          >
            Traces
          </h1>
          <p
            className="text-xs"
            style={{ color: "var(--sentinel-text-muted)" }}
          >
            Live LLM API call observability
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            className="btn-ghost"
            onClick={() => {
              setAutoRefresh(!autoRefresh);
            }}
            title={autoRefresh ? "Pause auto-refresh" : "Enable auto-refresh"}
          >
            <span
              className="inline-block w-2 h-2 rounded-full"
              style={{
                background: autoRefresh
                  ? "var(--sentinel-success)"
                  : "var(--sentinel-text-muted)",
                boxShadow: autoRefresh
                  ? "0 0 6px var(--sentinel-success)"
                  : "none",
              }}
            />
            {autoRefresh ? "Live" : "Paused"}
          </button>
          <button
            className="btn-ghost"
            onClick={() => {
              setLoading(true);
              loadData();
            }}
          >
            <IconRefresh />
            Refresh
          </button>
        </div>
      </header>

      {/* ── Main Content ── */}
      <main className="flex-1 px-6 py-6 max-w-[1400px] w-full mx-auto">
        {err && <ErrorBanner message={err} onRetry={loadData} />}

        {/* Stats Grid */}
        <div
          className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-8 stagger-children"
        >
          <StatCard
            icon={<IconActivity />}
            label="Total Traces"
            value={stats ? formatTokens(stats.total_traces) : "—"}
            sub={
              stats && stats.error_count > 0
                ? `${stats.error_count} errors`
                : undefined
            }
            loading={loading}
          />
          <StatCard
            icon={<IconDollar />}
            label="Total Spend"
            value={stats ? formatCost(stats.total_cost_usd) : "—"}
            loading={loading}
            accent
          />
          <StatCard
            icon={<IconClock />}
            label="Avg Latency"
            value={
              stats ? formatLatency(Math.round(stats.avg_latency_ms)) : "—"
            }
            loading={loading}
          />
          <StatCard
            icon={<IconZap />}
            label="Tokens Used"
            value={
              stats
                ? formatTokens(
                    stats.total_prompt_tokens +
                      stats.total_completion_tokens
                  )
                : "—"
            }
            sub={
              stats
                ? `${formatTokens(stats.total_prompt_tokens)} in / ${formatTokens(stats.total_completion_tokens)} out`
                : undefined
            }
            loading={loading}
          />
          <StatCard
            icon={<IconAlertTriangle />}
            label="Error Rate"
            value={
              stats && stats.total_traces > 0
                ? `${((stats.error_count / stats.total_traces) * 100).toFixed(1)}%`
                : "0%"
            }
            loading={loading}
            error={!!stats && stats.error_count > 0}
          />
        </div>

        {/* Cost over time chart (Week 10) */}
        {series.length > 0 && (
          <div className="glass-panel mb-8 p-5 animate-slide-up">
            <div className="flex items-center justify-between mb-3">
              <div>
                <h2
                  className="text-sm font-semibold"
                  style={{ color: "var(--sentinel-text-primary)" }}
                >
                  Spend (last 24h)
                </h2>
                <p
                  className="text-xs"
                  style={{ color: "var(--sentinel-text-muted)" }}
                >
                  Total: {formatCost(series.reduce((s, p) => s + p.cost_usd, 0))}
                </p>
              </div>
              <span
                className="text-xs"
                style={{ color: "var(--sentinel-text-muted)" }}
              >
                bucket: hour
              </span>
            </div>
            <Sparkline
              width={1200}
              height={90}
              points={series.map((p, i) => ({
                x: i,
                y: p.cost_usd,
                label: p.bucket,
              }))}
            />
          </div>
        )}

        {/* Traces Table */}
        <div className="glass-panel overflow-hidden animate-slide-up">
          <div
            className="flex items-center justify-between px-5 py-4"
            style={{ borderBottom: "1px solid var(--sentinel-border-subtle)" }}
          >
            <div className="flex items-center gap-2">
              <h2
                className="text-sm font-semibold"
                style={{ color: "var(--sentinel-text-primary)" }}
              >
                Recent Traces
              </h2>
              {stats && (
                <span
                  className="text-xs px-2 py-0.5 rounded-full"
                  style={{
                    background: "var(--sentinel-accent-dim)",
                    color: "var(--sentinel-accent-light)",
                  }}
                >
                  {stats.total_traces}
                </span>
              )}
            </div>
            {stats && Object.keys(stats.traces_by_provider).length > 0 && (
              <div className="flex items-center gap-2">
                {Object.entries(stats.traces_by_provider).map(([prov, count]) => (
                  <span
                    key={prov}
                    className={`badge ${getProviderBadge(prov)}`}
                  >
                    {prov} · {count}
                  </span>
                ))}
              </div>
            )}
          </div>

          <div className="filter-bar">
            <label>
              Provider
              <select
                value={providerFilter}
                onChange={(e) => {
                  setLoading(true);
                  setProviderFilter(e.target.value);
                }}
              >
                <option value="">all</option>
                {stats &&
                  Object.keys(stats.traces_by_provider).map((p) => (
                    <option key={p} value={p}>
                      {p}
                    </option>
                  ))}
              </select>
            </label>
            <label>
              Model
              <select
                value={modelFilter}
                onChange={(e) => {
                  setLoading(true);
                  setModelFilter(e.target.value);
                }}
              >
                <option value="">all</option>
                {modelOptions.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Status
              <select
                value={statusFilter}
                onChange={(e) =>
                  setStatusFilter(e.target.value as "" | "ok" | "err")
                }
              >
                <option value="">all</option>
                <option value="ok">2xx/3xx</option>
                <option value="err">4xx/5xx</option>
              </select>
            </label>
            {(providerFilter || modelFilter || statusFilter) && (
              <button
                type="button"
                className="btn-ghost"
                style={{ padding: "4px 10px", fontSize: "0.75rem" }}
                onClick={() => {
                  setProviderFilter("");
                  setModelFilter("");
                  setStatusFilter("");
                  setLoading(true);
                }}
              >
                Clear
              </button>
            )}
            <span
              className="ml-auto text-xs"
              style={{ color: "var(--sentinel-text-muted)" }}
            >
              {filteredTraces.length} shown · spend{" "}
              <strong style={{ color: "var(--sentinel-accent-light)" }}>
                {formatCost(windowRollup.cost)}
              </strong>{" "}
              · {formatTokens(windowRollup.tokens)} tokens ·{" "}
              <span className="kbd">j</span> <span className="kbd">k</span>{" "}
              <span className="kbd">↵</span>
            </span>
          </div>

          {loading ? (
            <div className="p-6 space-y-3">
              {Array.from({ length: 8 }).map((_, i) => (
                <div key={i} className="skeleton h-12 w-full" />
              ))}
            </div>
          ) : filteredTraces.length === 0 ? (
            traces.length === 0 ? (
              <ZeroStateHero />
            ) : (
              <div className="empty-state">
                <IconEmpty />
                <p className="empty-state-title">No matching traces</p>
                <p className="empty-state-desc">
                  Try clearing a filter above.
                </p>
              </div>
            )
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="trace-table">
                  <thead>
                    <tr>
                      <th>Time</th>
                      <th>Provider</th>
                      <th>Model</th>
                      <th>Status</th>
                      <th>Latency</th>
                      <th>Tokens</th>
                      <th>Cost</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredTraces.map((trace, i) => (
                      <tr
                        key={trace.id}
                        tabIndex={i === focusedRow ? 0 : -1}
                        ref={(el) => {
                          rowRefs.current[i] = el;
                        }}
                        onClick={() => router.push(`/traces/${trace.id}`)}
                      >
                        <td
                          className="whitespace-nowrap"
                          style={{ fontFamily: "var(--font-geist-mono)" }}
                        >
                          {timeAgo(trace.created_at)}
                        </td>
                        <td>
                          <span
                            className={`badge ${getProviderBadge(trace.provider)}`}
                          >
                            {trace.provider}
                          </span>
                        </td>
                        <td
                          className="font-medium whitespace-nowrap"
                          style={{
                            color: "var(--sentinel-text-primary)",
                            fontFamily: "var(--font-geist-mono)",
                            fontSize: "0.8rem",
                          }}
                        >
                          {trace.model}
                        </td>
                        <td>
                          <span
                            className={`badge ${getStatusBadge(trace.status_code)}`}
                          >
                            {trace.status_code}
                          </span>
                        </td>
                        <td
                          style={{ fontFamily: "var(--font-geist-mono)" }}
                        >
                          {formatLatency(trace.latency_ms)}
                        </td>
                        <td
                          className="whitespace-nowrap"
                          style={{
                            fontFamily: "var(--font-geist-mono)",
                            fontSize: "0.8rem",
                          }}
                        >
                          <span style={{ color: "var(--sentinel-text-muted)" }}>
                            {formatTokens(trace.prompt_tokens)}
                          </span>
                          <span
                            className="mx-1"
                            style={{ color: "var(--sentinel-border)" }}
                          >
                            →
                          </span>
                          <span>
                            {formatTokens(trace.completion_tokens)}
                          </span>
                        </td>
                        <td
                          className="font-medium"
                          style={{
                            color: "var(--sentinel-accent-light)",
                            fontFamily: "var(--font-geist-mono)",
                          }}
                        >
                          {formatCost(trace.cost_usd)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {nextCursor && (
                <div
                  className="flex justify-center py-4"
                  style={{
                    borderTop: "1px solid var(--sentinel-border-subtle)",
                  }}
                >
                  <button
                    className="btn-ghost"
                    onClick={loadMore}
                    disabled={loadingMore}
                  >
                    {loadingMore ? "Loading..." : "Load More"}
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </main>

      {/* ── Footer ── */}
      <footer
        className="text-center py-4 text-xs"
        style={{
          color: "var(--sentinel-text-muted)",
          borderTop: "1px solid var(--sentinel-border-subtle)",
        }}
      >
        Sentinel v0.1.0 — Open Source LLM Observability
      </footer>
    </div>
  );
}

/* ================================================================
   Zero-State Hero (shown when there are no traces at all)
   ================================================================ */

function ZeroStateHero() {
  const sdkSnippet = `from sentinel import OpenAI

client = OpenAI(
    sentinel_api_key="sk-sentinel-dev-000",
    sentinel_url="http://localhost:8000",
    provider_api_key="sk-...",  # your real OpenAI key
)

client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello, Sentinel!"}],
)`;

  const curlSnippet = `curl http://localhost:8000/v1/chat/completions \\
  -H "Authorization: Bearer sk-sentinel-dev-000" \\
  -H "x-provider-key: sk-..." \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "Hi"}]
  }'`;

  return (
    <div className="px-8 py-12">
      <div className="max-w-3xl mx-auto text-center mb-8">
        <h2
          className="text-2xl font-bold mb-2"
          style={{ color: "var(--sentinel-text-primary)" }}
        >
          Welcome to Sentinel
        </h2>
        <p
          className="text-sm"
          style={{ color: "var(--sentinel-text-muted)" }}
        >
          No traces yet. Point any OpenAI/Anthropic client at{" "}
          <code
            className="px-2 py-0.5 rounded text-xs"
            style={{
              background: "var(--sentinel-surface-hover)",
              color: "var(--sentinel-accent-light)",
            }}
          >
            localhost:8000
          </code>{" "}
          and your first call will appear here in real time.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 max-w-5xl mx-auto">
        <div className="glass-panel-elevated p-4">
          <div className="flex items-center justify-between mb-2">
            <h3
              className="text-xs font-semibold uppercase tracking-wider"
              style={{ color: "var(--sentinel-text-muted)" }}
            >
              Python SDK
            </h3>
            <span
              className="text-xs"
              style={{ color: "var(--sentinel-text-faint)" }}
            >
              pip install sentinel-sdk
            </span>
          </div>
          <pre
            className="json-viewer text-xs"
            style={{ maxHeight: "none" }}
          >
            {sdkSnippet}
          </pre>
        </div>

        <div className="glass-panel-elevated p-4">
          <div className="flex items-center justify-between mb-2">
            <h3
              className="text-xs font-semibold uppercase tracking-wider"
              style={{ color: "var(--sentinel-text-muted)" }}
            >
              curl (no install)
            </h3>
            <span
              className="text-xs"
              style={{ color: "var(--sentinel-text-faint)" }}
            >
              works with any HTTP client
            </span>
          </div>
          <pre
            className="json-viewer text-xs"
            style={{ maxHeight: "none" }}
          >
            {curlSnippet}
          </pre>
        </div>
      </div>

      <div
        className="max-w-3xl mx-auto mt-8 text-center text-xs"
        style={{ color: "var(--sentinel-text-muted)" }}
      >
        Want canned data? Run{" "}
        <code
          className="px-2 py-0.5 rounded"
          style={{
            background: "var(--sentinel-surface-hover)",
            color: "var(--sentinel-accent-light)",
          }}
        >
          make demo
        </code>{" "}
        (requires{" "}
        <code style={{ color: "var(--sentinel-text-secondary)" }}>
          OPENAI_API_KEY
        </code>
        ) to seed ~12 varied traces, a span tree, a routing policy, and a
        dataset.
      </div>
    </div>
  );
}

/* ================================================================
   Stat Card Component
   ================================================================ */

function StatCard({
  icon,
  label,
  value,
  sub,
  loading,
  accent,
  error,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub?: string;
  loading?: boolean;
  accent?: boolean;
  error?: boolean;
}) {
  if (loading) {
    return (
      <div className="stat-card">
        <div className="skeleton h-4 w-20 mb-3" />
        <div className="skeleton h-8 w-24" />
      </div>
    );
  }

  return (
    <div className="stat-card">
      <div className="flex items-center gap-2 mb-2">
        <span
          style={{
            color: error
              ? "var(--sentinel-error)"
              : accent
                ? "var(--sentinel-accent)"
                : "var(--sentinel-text-muted)",
          }}
        >
          {icon}
        </span>
        <span className="stat-label" style={{ marginBottom: 0 }}>
          {label}
        </span>
      </div>
      <div
        className="stat-value animate-count-up"
        style={{
          color: error
            ? "var(--sentinel-error)"
            : accent
              ? "var(--sentinel-accent-light)"
              : undefined,
        }}
      >
        {value}
      </div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}
