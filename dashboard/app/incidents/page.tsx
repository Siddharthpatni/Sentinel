"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { fetchTriageExecutions, simulateTriage, type TriageExecution } from "@/lib/api";
import { HudPanel } from "@/components/HudPanel";

const STATUS_BADGE: Record<string, string> = {
  running: "badge-openai",
  paused_for_approval: "badge-warning",
  approved: "badge-openai",
  rejected: "badge-error",
  completed: "badge-success",
  failed: "badge-error",
};

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function IncidentsPage() {
  const router = useRouter();
  const [rows, setRows] = useState<TriageExecution[]>([]);
  const [loading, setLoading] = useState(true);
  const [simulating, setSimulating] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setRows(await fetchTriageExecutions());
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    (async () => {
      await reload();
    })();
  }, [reload]);

  async function simulate() {
    setSimulating(true);
    setErr(null);
    try {
      const execution = await simulateTriage();
      router.push(`/incidents/${execution.id}`);
    } catch (e) {
      setErr(String(e));
    } finally {
      setSimulating(false);
    }
  }

  return (
    <main className="hud-grid-bg mx-auto max-w-5xl space-y-6 px-6 py-8 text-fg">
      <header className="flex items-start justify-between gap-4">
        <div>
          <div className="hud-title mb-2">
            <span className="hud-status-dot" /> Autonomous Incident Response
          </div>
          <h1 className="text-xl font-semibold tracking-tight">Incidents</h1>
          <p className="text-sm text-muted">
            Diagnosis, proposed fix, compliance check, and human approval —
            for failing or high-risk traces. Runs fully offline on a local
            Ollama model by default.
          </p>
        </div>
        <button type="button" className="btn-hud whitespace-nowrap" onClick={simulate} disabled={simulating}>
          {simulating ? "Starting…" : "Simulate Incident"}
        </button>
      </header>

      {err && <p className="text-xs text-bad">{err}</p>}

      <HudPanel className="p-0 overflow-hidden">
        <table className="hud-table">
          <thead>
            <tr>
              <th>Incident</th>
              <th>Status</th>
              <th>Node</th>
              <th>Patch risk</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td className="px-4 py-3 text-faint" colSpan={5}>
                  Loading…
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td className="px-4 py-3 text-faint" colSpan={5}>
                  No incidents yet — click Simulate Incident above to see
                  the pipeline run end to end, or trigger one from a
                  failing trace.
                </td>
              </tr>
            ) : (
              rows.map((r) => (
                <tr key={r.id} onClick={() => router.push(`/incidents/${r.id}`)}>
                  <td className="font-mono text-xs">
                    {r.id.slice(0, 8)}
                    {r.diagnosis?.cache_hit && (
                      <span
                        className="ml-2 text-[0.65rem] font-mono"
                        style={{ color: "var(--shield-cyan-light)" }}
                      >
                        ⚡cached
                      </span>
                    )}
                  </td>
                  <td>
                    <span className={`badge ${STATUS_BADGE[r.status] ?? ""}`}>{r.status}</span>
                  </td>
                  <td className="text-xs">{r.current_node}</td>
                  <td className="text-xs">{r.patch_risk_tier ?? "—"}</td>
                  <td className="text-xs">{formatDate(r.created_at)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </HudPanel>
    </main>
  );
}
