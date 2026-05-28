"use client";

import { useState } from "react";
import type { Span } from "@/lib/api";

interface TreeNode {
  span: Span;
  children: TreeNode[];
  depth: number;
}

function buildTree(spans: Span[]): TreeNode[] {
  const byId = new Map<string, TreeNode>();
  spans.forEach((s) =>
    byId.set(s.id, { span: s, children: [], depth: 0 })
  );
  const roots: TreeNode[] = [];
  byId.forEach((node) => {
    const pid = node.span.parent_span_id;
    if (pid && byId.has(pid)) {
      const parent = byId.get(pid)!;
      node.depth = parent.depth + 1;
      parent.children.push(node);
    } else {
      roots.push(node);
    }
  });
  // re-flow depth via DFS in case insertion order miscalculated
  const fix = (n: TreeNode, d: number) => {
    n.depth = d;
    n.children.forEach((c) => fix(c, d + 1));
  };
  roots.forEach((r) => fix(r, 0));
  return roots;
}

function flatten(nodes: TreeNode[]): TreeNode[] {
  const out: TreeNode[] = [];
  const walk = (n: TreeNode) => {
    out.push(n);
    n.children.forEach(walk);
  };
  nodes.forEach(walk);
  return out;
}

function ts(s: string | null): number {
  return s ? new Date(s).getTime() : 0;
}

function typeColor(t: string): string {
  switch (t) {
    case "agent":
      return "var(--sentinel-accent)";
    case "llm":
      return "var(--sentinel-success)";
    case "tool":
      return "var(--sentinel-warning)";
    case "chain":
      return "var(--sentinel-accent-light)";
    case "retriever":
      return "#5ec5ff";
    default:
      return "var(--sentinel-text-muted)";
  }
}

function fmtMs(ms: number): string {
  if (ms < 1) return "<1ms";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

export function SpanWaterfall({ spans }: { spans: Span[] }) {
  const [selectedId, setSelectedId] = useState<string | null>(null);

  if (!spans || spans.length === 0) {
    return (
      <div className="glass-panel p-5">
        <h3
          className="text-sm font-semibold mb-2"
          style={{ color: "var(--sentinel-text-primary)" }}
        >
          Span Tree
        </h3>
        <p className="text-xs text-faint">
          No spans recorded for this trace. Wrap your agent run in{" "}
          <code className="text-fg-soft">sentinel.trace(...)</code> to emit a
          span tree.
        </p>
      </div>
    );
  }

  const flat = flatten(buildTree(spans));
  const t0 = Math.min(...spans.map((s) => ts(s.start_ts)));
  const t1 = Math.max(
    ...spans.map((s) => ts(s.end_ts) || ts(s.start_ts))
  );
  const totalMs = Math.max(t1 - t0, 1);
  const selected = flat.find((n) => n.span.id === selectedId)?.span ?? null;

  return (
    <div className="glass-panel p-5">
      <div className="flex items-baseline justify-between mb-4">
        <h3
          className="text-sm font-semibold"
          style={{ color: "var(--sentinel-text-primary)" }}
        >
          Span Tree
        </h3>
        <span className="text-xs text-faint">
          {spans.length} spans · {fmtMs(totalMs)} total
        </span>
      </div>

      <div className="space-y-0.5">
        {flat.map((node) => {
          const s = node.span;
          const start = ts(s.start_ts) - t0;
          const end = (ts(s.end_ts) || ts(s.start_ts)) - t0;
          const leftPct = (start / totalMs) * 100;
          const widthPct = Math.max(((end - start) / totalMs) * 100, 0.5);
          const isSel = s.id === selectedId;
          const isErr = s.status === "error";
          return (
            <button
              key={s.id}
              type="button"
              onClick={() => setSelectedId(isSel ? null : s.id)}
              className={
                "w-full grid grid-cols-[minmax(0,1fr)_minmax(0,2fr)] gap-3 items-center px-2 py-1.5 rounded text-left transition " +
                (isSel
                  ? "bg-surface-1"
                  : "hover:bg-surface-1")
              }
            >
              <div
                className="flex items-center gap-2 min-w-0"
                style={{ paddingLeft: `${node.depth * 16}px` }}
              >
                <span
                  className="inline-block h-2 w-2 rounded-full shrink-0"
                  style={{ backgroundColor: typeColor(s.span_type) }}
                />
                <span className="text-xs uppercase tracking-wide text-faint shrink-0">
                  {s.span_type}
                </span>
                <span
                  className="text-sm truncate"
                  style={{
                    color: isErr
                      ? "var(--sentinel-error)"
                      : "var(--sentinel-text-primary)",
                  }}
                >
                  {s.name}
                </span>
              </div>
              <div className="relative h-5">
                <div
                  className="absolute inset-y-0 rounded-sm"
                  style={{
                    left: `${leftPct}%`,
                    width: `${widthPct}%`,
                    backgroundColor: isErr
                      ? "var(--sentinel-error-dim)"
                      : typeColor(s.span_type),
                    opacity: isErr ? 1 : 0.55,
                  }}
                />
                <span
                  className="absolute inset-y-0 flex items-center text-[10px] text-faint"
                  style={{
                    left: `min(${leftPct + widthPct}%, calc(100% - 60px))`,
                    paddingLeft: 6,
                  }}
                >
                  {fmtMs(end - start)}
                </span>
              </div>
            </button>
          );
        })}
      </div>

      {selected && (
        <div className="mt-4 border-t border-default pt-3">
          <div className="flex items-baseline justify-between mb-2">
            <h4 className="text-sm font-semibold text-fg">
              {selected.name}{" "}
              <span className="text-xs font-normal text-faint">
                · {selected.span_type} · {selected.status}
              </span>
            </h4>
            <button
              type="button"
              onClick={() => setSelectedId(null)}
              className="text-xs text-faint hover:text-fg"
            >
              Close
            </button>
          </div>
          <pre className="json-viewer text-xs">
            {JSON.stringify(selected.attributes, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
