"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  fetchTraces,
  fetchTraceStats,
  type Trace,
  type TraceStats,
} from "@/lib/api";

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
  const [loading, setLoading] = useState(true);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const loadData = useCallback(async () => {
    try {
      const [tracesRes, statsRes] = await Promise.all([
        fetchTraces({ limit: 50 }),
        fetchTraceStats(),
      ]);
      setTraces(tracesRes.traces);
      setNextCursor(tracesRes.next_cursor);
      setStats(statsRes);
    } catch (err) {
      console.error("Failed to load data:", err);
    } finally {
      setLoading(false);
    }
  }, []);

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
      const res = await fetchTraces({ cursor: nextCursor, limit: 50 });
      setTraces((prev) => [...prev, ...res.traces]);
      setNextCursor(res.next_cursor);
    } catch (err) {
      console.error("Failed to load more:", err);
    } finally {
      setLoadingMore(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col" style={{ background: "var(--sentinel-bg)" }}>
      {/* ── Header ── */}
      <header
        className="sticky top-0 z-50 flex items-center justify-between px-6 py-4"
        style={{
          background: "rgba(10, 10, 15, 0.85)",
          backdropFilter: "blur(12px)",
          borderBottom: "1px solid var(--sentinel-border-subtle)",
        }}
      >
        <div className="flex items-center gap-3">
          <div
            className="flex items-center justify-center rounded-lg p-1.5"
            style={{ background: "var(--sentinel-accent-dim)" }}
          >
            <span style={{ color: "var(--sentinel-accent)" }}>
              <IconRadar />
            </span>
          </div>
          <div>
            <h1
              className="text-lg font-bold tracking-tight"
              style={{ color: "var(--sentinel-text-primary)" }}
            >
              Sentinel
            </h1>
            <p
              className="text-xs"
              style={{ color: "var(--sentinel-text-muted)" }}
            >
              LLM Observability
            </p>
          </div>
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

          {loading ? (
            <div className="p-6 space-y-3">
              {Array.from({ length: 8 }).map((_, i) => (
                <div key={i} className="skeleton h-12 w-full" />
              ))}
            </div>
          ) : traces.length === 0 ? (
            <div className="empty-state">
              <IconEmpty />
              <p className="empty-state-title">No traces yet</p>
              <p className="empty-state-desc">
                Point your OpenAI or Anthropic SDK at{" "}
                <code
                  className="px-2 py-1 rounded text-xs"
                  style={{
                    background: "var(--sentinel-surface-hover)",
                    color: "var(--sentinel-accent-light)",
                  }}
                >
                  http://localhost:8000
                </code>{" "}
                and make your first API call. Traces will appear here
                automatically.
              </p>
            </div>
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
                    {traces.map((trace) => (
                      <tr
                        key={trace.id}
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
