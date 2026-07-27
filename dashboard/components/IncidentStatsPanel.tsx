"use client";

import { useEffect, useState } from "react";
import { fetchTriageExecutions, type TriageExecution, type TriageStatus } from "@/lib/api";
import { HudPanel } from "@/components/HudPanel";

/* ================================================================
   IncidentStatsPanel — fleet-wide telemetry sidebar ("side of
   graphs"): cache hit rate, status mix, risk-tier mix, avg
   resolution time. Computed client-side from the executions list —
   no new backend endpoint needed, the fields already round-trip.
   ================================================================ */

const STATUS_ORDER: TriageStatus[] = [
  "completed",
  "paused_for_approval",
  "running",
  "approved",
  "rejected",
  "failed",
];

const STATUS_COLOR: Record<TriageStatus, string> = {
  completed: "var(--sentinel-success)",
  paused_for_approval: "var(--sentinel-warning)",
  running: "var(--shield-cyan)",
  approved: "var(--shield-cyan)",
  rejected: "var(--sentinel-error)",
  failed: "var(--sentinel-error)",
};

const RISK_ORDER = ["low", "medium", "high"] as const;
const RISK_COLOR: Record<(typeof RISK_ORDER)[number], string> = {
  low: "var(--sentinel-success)",
  medium: "var(--sentinel-warning)",
  high: "var(--sentinel-error)",
};

function formatDuration(ms: number): string {
  if (ms < 1000) return "<1s";
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  return `${m}m ${s % 60}s`;
}

function MiniBar({ label, value, total, color }: { label: string; value: number; total: number; color: string }) {
  const pct = total > 0 ? Math.round((value / total) * 100) : 0;
  return (
    <div className="mini-bar-row">
      <span className="mini-bar-label">{label.replace(/_/g, " ")}</span>
      <div className="mini-bar-track">
        <div className="mini-bar-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="mini-bar-value">{value}</span>
    </div>
  );
}

export function IncidentStatsPanel() {
  const [executions, setExecutions] = useState<TriageExecution[] | null>(null);

  useEffect(() => {
    (async () => {
      try {
        setExecutions(await fetchTriageExecutions());
      } catch {
        setExecutions([]);
      }
    })();
  }, []);

  if (executions === null) {
    return (
      <div className="glass-panel p-5 space-y-3">
        <div className="skeleton h-4 w-32" />
        <div className="skeleton h-20 w-20 rounded-full mx-auto" />
        <div className="skeleton h-3 w-full" />
        <div className="skeleton h-3 w-full" />
      </div>
    );
  }

  const total = executions.length;
  const cacheHits = executions.filter((e) => e.diagnosis?.cache_hit).length;
  const cacheRate = total > 0 ? Math.round((cacheHits / total) * 100) : 0;

  const statusCounts = STATUS_ORDER.map((s) => ({
    key: s,
    count: executions.filter((e) => e.status === s).length,
  })).filter((s) => s.count > 0);

  const riskCounts = RISK_ORDER.map((r) => ({
    key: r,
    count: executions.filter((e) => e.patch_risk_tier === r).length,
  }));
  const riskTotal = riskCounts.reduce((sum, r) => sum + r.count, 0);

  const resolved = executions.filter((e) =>
    ["completed", "rejected", "failed"].includes(e.status),
  );
  const avgResolutionMs =
    resolved.length > 0
      ? resolved.reduce(
          (sum, e) => sum + (new Date(e.updated_at).getTime() - new Date(e.created_at).getTime()),
          0,
        ) / resolved.length
      : null;

  return (
    <HudPanel title="Fleet Telemetry" className="space-y-6">
      <div className="flex items-center gap-4">
        <div className="radial-gauge" style={{ "--gauge-pct": cacheRate } as React.CSSProperties}>
          <span className="radial-gauge-value">{cacheRate}%</span>
        </div>
        <div>
          <div className="stat-label" style={{ marginBottom: 2 }}>
            Cache hit rate
          </div>
          <div className="text-xs" style={{ color: "var(--sentinel-text-muted)" }}>
            {cacheHits} of {total} incidents resolved instantly from the local
            SQLite cache registry — no LLM call.
          </div>
        </div>
      </div>

      <div className="space-y-3">
        <div className="stat-card p-3 flex items-center justify-between gap-3">
          <span className="stat-label" style={{ marginBottom: 0 }}>
            Total incidents
          </span>
          <span className="stat-value text-lg">{total}</span>
        </div>
        <div className="stat-card p-3 flex items-center justify-between gap-3">
          <span className="stat-label" style={{ marginBottom: 0 }}>
            Avg resolution
          </span>
          <span className="stat-value text-lg whitespace-nowrap">
            {avgResolutionMs !== null ? formatDuration(avgResolutionMs) : "—"}
          </span>
        </div>
      </div>

      {statusCounts.length > 0 && (
        <div>
          <div className="hud-label mb-2">Status mix</div>
          <div className="space-y-2">
            {statusCounts.map((s) => (
              <MiniBar key={s.key} label={s.key} value={s.count} total={total} color={STATUS_COLOR[s.key]} />
            ))}
          </div>
        </div>
      )}

      {riskTotal > 0 && (
        <div>
          <div className="hud-label mb-2">Patch risk mix</div>
          <div className="space-y-2">
            {riskCounts
              .filter((r) => r.count > 0)
              .map((r) => (
                <MiniBar key={r.key} label={r.key} value={r.count} total={riskTotal} color={RISK_COLOR[r.key]} />
              ))}
          </div>
        </div>
      )}
    </HudPanel>
  );
}
