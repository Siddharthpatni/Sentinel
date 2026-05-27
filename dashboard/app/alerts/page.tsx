"use client";

import { useCallback, useEffect, useState } from "react";
import {
  type Alert,
  type Project,
  checkAlert,
  createAlert,
  deleteAlert,
  fetchAlerts,
  fetchProjects,
} from "@/lib/api";

const METRICS: { value: Alert["metric"]; label: string; unit: string }[] = [
  { value: "cost_per_hour_usd", label: "Cost / hour", unit: "USD" },
  { value: "error_rate_pct", label: "Error rate", unit: "%" },
  { value: "latency_p95_ms", label: "Latency p95", unit: "ms" },
];

export default function AlertsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState<string>("");
  const [rows, setRows] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);

  const [name, setName] = useState("");
  const [metric, setMetric] = useState<Alert["metric"]>("cost_per_hour_usd");
  const [threshold, setThreshold] = useState<string>("1.00");
  const [window, setWindow] = useState<number>(60);
  const [comparator, setComparator] = useState<Alert["comparator"]>("gt");
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    fetchProjects().then((p) => {
      setProjects(p);
      if (p.length > 0) setProjectId(p[0].id);
    });
  }, []);

  const reload = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    try {
      setRows(await fetchAlerts(projectId));
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    reload();
  }, [reload]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setSubmitting(true);
    try {
      await createAlert({
        project_id: projectId,
        name,
        metric,
        comparator,
        threshold: parseFloat(threshold),
        window_minutes: window,
      });
      setName("");
      await reload();
    } catch (e: unknown) {
      setErr((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  async function remove(id: string) {
    if (!confirm("Delete this alert?")) return;
    await deleteAlert(id);
    await reload();
  }

  async function check(id: string) {
    await checkAlert(id);
    await reload();
  }

  return (
    <main className="mx-auto max-w-5xl space-y-6 px-6 py-8 text-neutral-200">
      <header>
        <h1 className="text-xl font-semibold tracking-tight">Alerts</h1>
        <p className="text-sm text-neutral-400">
          Threshold checks over a rolling window. Evaluated on demand — click
          <span className="mx-1 font-mono">check</span> to refresh a row.
        </p>
      </header>

      <section className="rounded border border-neutral-800 bg-neutral-950 p-4">
        <label className="block text-xs font-medium text-neutral-400">
          Project
        </label>
        <select
          className="mt-1 rounded border border-neutral-800 bg-neutral-900 px-2 py-1 text-sm"
          value={projectId}
          onChange={(e) => setProjectId(e.target.value)}
        >
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      </section>

      <section className="rounded border border-neutral-800 bg-neutral-950 p-4">
        <h2 className="text-sm font-semibold">New alert</h2>
        <form onSubmit={submit} className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-6">
          <input
            className="md:col-span-2 rounded border border-neutral-800 bg-neutral-900 px-2 py-1 text-sm"
            placeholder="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
          <select
            className="md:col-span-2 rounded border border-neutral-800 bg-neutral-900 px-2 py-1 text-sm"
            value={metric}
            onChange={(e) => setMetric(e.target.value as Alert["metric"])}
          >
            {METRICS.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label} ({m.unit})
              </option>
            ))}
          </select>
          <select
            className="rounded border border-neutral-800 bg-neutral-900 px-2 py-1 text-sm"
            value={comparator}
            onChange={(e) => setComparator(e.target.value as Alert["comparator"])}
          >
            <option value="gt">&gt;</option>
            <option value="lt">&lt;</option>
          </select>
          <input
            type="number"
            step="0.01"
            className="rounded border border-neutral-800 bg-neutral-900 px-2 py-1 text-sm"
            placeholder="threshold"
            value={threshold}
            onChange={(e) => setThreshold(e.target.value)}
            required
          />
          <label className="md:col-span-2 flex items-center gap-2 text-sm">
            Window:
            <input
              type="number"
              min={1}
              max={10080}
              className="w-24 rounded border border-neutral-800 bg-neutral-900 px-2 py-1 text-sm"
              value={window}
              onChange={(e) => setWindow(parseInt(e.target.value, 10) || 60)}
            />
            min
          </label>
          <button
            type="submit"
            disabled={submitting || !projectId}
            className="md:col-span-4 rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50"
          >
            {submitting ? "Creating…" : "Create alert"}
          </button>
          {err && <div className="col-span-full text-xs text-red-400">{err}</div>}
        </form>
      </section>

      <section className="rounded border border-neutral-800 bg-neutral-950">
        <table className="w-full text-sm">
          <thead className="text-xs text-neutral-400">
            <tr>
              <th className="px-4 py-2 text-left">Name</th>
              <th className="px-4 py-2 text-left">Metric</th>
              <th className="px-4 py-2 text-left">Threshold</th>
              <th className="px-4 py-2 text-left">Window</th>
              <th className="px-4 py-2 text-left">Last value</th>
              <th className="px-4 py-2 text-left">State</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td className="px-4 py-3 text-neutral-500" colSpan={7}>
                  Loading…
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td className="px-4 py-3 text-neutral-500" colSpan={7}>
                  No alerts yet.
                </td>
              </tr>
            ) : (
              rows.map((r) => (
                <tr key={r.id} className="border-t border-neutral-900">
                  <td className="px-4 py-2 font-medium">{r.name}</td>
                  <td className="px-4 py-2 font-mono text-xs">{r.metric}</td>
                  <td className="px-4 py-2 font-mono text-xs">
                    {r.comparator} {Number(r.threshold).toFixed(2)}
                  </td>
                  <td className="px-4 py-2 text-xs">{r.window_minutes}m</td>
                  <td className="px-4 py-2 font-mono text-xs">
                    {r.last_value === null
                      ? "—"
                      : Number(r.last_value).toFixed(3)}
                  </td>
                  <td className="px-4 py-2">
                    {r.last_checked_at === null ? (
                      <span className="text-xs text-neutral-500">unchecked</span>
                    ) : r.last_triggered ? (
                      <span className="rounded bg-red-950 px-2 py-0.5 text-xs text-red-300">
                        triggered
                      </span>
                    ) : (
                      <span className="rounded bg-emerald-950 px-2 py-0.5 text-xs text-emerald-300">
                        ok
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-2">
                    <button
                      onClick={() => check(r.id)}
                      className="mr-3 text-xs text-blue-400 hover:text-blue-300"
                    >
                      check
                    </button>
                    <button
                      onClick={() => remove(r.id)}
                      className="text-xs text-red-400 hover:text-red-300"
                    >
                      delete
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </section>
    </main>
  );
}
