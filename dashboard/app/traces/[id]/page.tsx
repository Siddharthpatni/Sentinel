"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { fetchTrace, type Trace } from "@/lib/api";
import { AnnotationPanel } from "@/components/annotation-panel";
import { SpanWaterfall } from "@/components/span-waterfall";
import { TraceActions } from "@/components/trace-actions";

/* ================================================================
   Helpers
   ================================================================ */

function formatCost(usd: number): string {
  if (usd < 0.01) return `$${usd.toFixed(6)}`;
  if (usd < 1) return `$${usd.toFixed(4)}`;
  return `$${usd.toFixed(2)}`;
}

function formatLatency(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

/* ================================================================
   JSON Syntax Highlighter
   ================================================================ */

function syntaxHighlight(json: string): string {
  return json.replace(
    /("(\\u[a-fA-F0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)/g,
    (match) => {
      let cls = "json-number";
      if (/^"/.test(match)) {
        cls = /:$/.test(match) ? "json-key" : "json-string";
      } else if (/true|false/.test(match)) {
        cls = "json-boolean";
      } else if (/null/.test(match)) {
        cls = "json-null";
      }
      return `<span class="${cls}">${match}</span>`;
    }
  );
}

function JsonViewer({ data, title }: { data: unknown; title: string }) {
  const [collapsed, setCollapsed] = useState(false);

  if (!data) {
    return (
      <div>
        <h3
          className="text-sm font-semibold mb-3"
          style={{ color: "var(--sentinel-text-primary)" }}
        >
          {title}
        </h3>
        <div
          className="json-viewer text-center py-8"
          style={{ color: "var(--sentinel-text-muted)" }}
        >
          No data available
        </div>
      </div>
    );
  }

  const formatted = JSON.stringify(data, null, 2);
  const highlighted = syntaxHighlight(formatted);

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h3
          className="text-sm font-semibold"
          style={{ color: "var(--sentinel-text-primary)" }}
        >
          {title}
        </h3>
        <button
          className="btn-ghost text-xs"
          onClick={() => setCollapsed(!collapsed)}
        >
          {collapsed ? "Expand" : "Collapse"}
        </button>
      </div>
      {!collapsed && (
        <div
          className="json-viewer"
          dangerouslySetInnerHTML={{ __html: highlighted }}
        />
      )}
    </div>
  );
}

/* ================================================================
   Icons
   ================================================================ */

function IconArrowLeft() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <line x1="19" y1="12" x2="5" y2="12" />
      <polyline points="12 19 5 12 12 5" />
    </svg>
  );
}

/* ================================================================
   Trace Detail Page
   ================================================================ */

export default function TraceDetailPage() {
  const params = useParams();
  const router = useRouter();
  const [trace, setTrace] = useState<Trace | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const id = params.id as string;
    fetchTrace(id)
      .then(setTrace)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [params.id]);

  if (loading) {
    return (
      <div
        className="min-h-screen flex items-center justify-center"
        style={{ background: "var(--sentinel-bg)" }}
      >
        <div className="space-y-4 w-full max-w-3xl px-6">
          <div className="skeleton h-8 w-64" />
          <div className="skeleton h-4 w-96" />
          <div className="skeleton h-48 w-full" />
          <div className="skeleton h-48 w-full" />
        </div>
      </div>
    );
  }

  if (error || !trace) {
    return (
      <div
        className="min-h-screen flex items-center justify-center"
        style={{ background: "var(--sentinel-bg)" }}
      >
        <div className="text-center">
          <p
            className="text-lg font-semibold mb-2"
            style={{ color: "var(--sentinel-error)" }}
          >
            Trace not found
          </p>
          <p
            className="text-sm mb-6"
            style={{ color: "var(--sentinel-text-muted)" }}
          >
            {error || "The requested trace does not exist."}
          </p>
          <button className="btn-primary" onClick={() => router.push("/")}>
            Back to Dashboard
          </button>
        </div>
      </div>
    );
  }

  const isError = trace.status_code >= 400;
  const providerBadge =
    trace.provider === "openai"
      ? "badge-openai"
      : trace.provider === "anthropic"
        ? "badge-anthropic"
        : "";

  return (
    <div
      className="min-h-screen flex flex-col"
      style={{ background: "var(--sentinel-bg)" }}
    >
      {/* Header */}
      <header
        className="sticky top-0 z-50 flex items-center gap-4 px-6 py-4"
        style={{
          background: "rgba(10, 10, 15, 0.85)",
          backdropFilter: "blur(12px)",
          borderBottom: "1px solid var(--sentinel-border-subtle)",
        }}
      >
        <button
          className="btn-ghost"
          onClick={() => router.push("/")}
        >
          <IconArrowLeft />
          Back
        </button>
        <div className="flex-1" />
        <span className={`badge ${providerBadge}`}>{trace.provider}</span>
        <span
          className={`badge ${isError ? "badge-error" : "badge-success"}`}
        >
          {trace.status_code}
        </span>
      </header>

      <main className="flex-1 px-6 py-8 max-w-[1200px] w-full mx-auto">
        {/* Title */}
        <div className="mb-8 animate-fade-in">
          <h1
            className="text-2xl font-bold mb-2 tracking-tight"
            style={{
              color: "var(--sentinel-text-primary)",
              fontFamily: "var(--font-geist-mono)",
            }}
          >
            {trace.model}
          </h1>
          <p
            className="text-sm"
            style={{ color: "var(--sentinel-text-muted)" }}
          >
            {formatDate(trace.created_at)} ·{" "}
            <span
              className="font-mono text-xs px-2 py-0.5 rounded"
              style={{
                background: "var(--sentinel-surface)",
                color: "var(--sentinel-text-secondary)",
              }}
            >
              {trace.id}
            </span>
          </p>
        </div>

        {/* Metrics Grid */}
        <div
          className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8 stagger-children"
        >
          <MetricCard label="Latency" value={formatLatency(trace.latency_ms)} />
          <MetricCard
            label="Prompt Tokens"
            value={trace.prompt_tokens.toLocaleString()}
          />
          <MetricCard
            label="Completion Tokens"
            value={trace.completion_tokens.toLocaleString()}
          />
          <MetricCard
            label="Cost"
            value={formatCost(trace.cost_usd)}
            accent
          />
        </div>

        {/* Error Message */}
        {trace.error_message && (
          <div
            className="mb-8 p-4 rounded-lg animate-fade-in"
            style={{
              background: "var(--sentinel-error-dim)",
              border: "1px solid rgba(248, 113, 113, 0.2)",
            }}
          >
            <p
              className="text-sm font-semibold mb-1"
              style={{ color: "var(--sentinel-error)" }}
            >
              Error
            </p>
            <p
              className="text-sm font-mono"
              style={{ color: "var(--sentinel-text-secondary)" }}
            >
              {trace.error_message}
            </p>
          </div>
        )}

        {/* Span tree waterfall */}
        <div className="mb-6 animate-slide-up">
          <SpanWaterfall spans={trace.spans ?? []} />
        </div>

        {/* Trace actions */}
        <div className="mb-6 animate-slide-up">
          <TraceActions trace={trace} />
        </div>

        {/* Request / Response Split */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 animate-slide-up">
          <div className="glass-panel p-5">
            <JsonViewer data={trace.request_body} title="Request Body" />
          </div>
          <div className="glass-panel p-5">
            <JsonViewer data={trace.response_body} title="Response Body" />
          </div>
        </div>

        {/* Annotations */}
        <div className="mt-6 animate-slide-up">
          <AnnotationPanel traceId={trace.id} />
        </div>
      </main>
    </div>
  );
}

/* ================================================================
   Metric Card
   ================================================================ */

function MetricCard({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: boolean;
}) {
  return (
    <div className="stat-card">
      <span className="stat-label">{label}</span>
      <span
        className="stat-value text-xl"
        style={{
          color: accent ? "var(--sentinel-accent-light)" : undefined,
        }}
      >
        {value}
      </span>
    </div>
  );
}
