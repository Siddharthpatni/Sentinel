"use client";

import { useEffect, useState } from "react";

interface Candidate {
  model: string;
  max_cost_usd?: number | null;
  max_latency_ms?: number | null;
}

interface Policy {
  id: string;
  project_id: string;
  name: string;
  match_jsonpath: string;
  candidates: Candidate[];
  fallback_on: { http_5xx?: boolean; timeout?: boolean; low_confidence?: number | null };
  enabled: boolean;
}

interface Project {
  id: string;
  name: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function PoliciesPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  const [name, setName] = useState("");
  const [jsonpath, setJsonpath] = useState("$.model");
  const [candidatesText, setCandidatesText] = useState(
    "gpt-4o-mini\nopenrouter/anthropic/claude-3-haiku",
  );
  const [http5xx, setHttp5xx] = useState(true);
  const [timeoutOn, setTimeoutOn] = useState(true);
  const [lowConf, setLowConf] = useState<string>("");

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [pj, pol] = await Promise.all([
        fetch(`${API_URL}/api/projects`, { cache: "no-store" }).then((r) => r.json()),
        fetch(`${API_URL}/api/routing-policies`, { cache: "no-store" }).then((r) => r.json()),
      ]);
      setProjects(pj.projects);
      if (pj.projects.length > 0 && !projectId) setProjectId(pj.projects[0].id);
      setPolicies(pol.policies);
    } catch (e) {
      setError(e instanceof Error ? e.message : "unknown");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const candidates: Candidate[] = candidatesText
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean)
        .map((model) => ({ model }));
      if (candidates.length === 0) throw new Error("At least one candidate model required");

      const res = await fetch(`${API_URL}/api/routing-policies`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: projectId,
          name,
          match_jsonpath: jsonpath,
          candidates,
          fallback_on: {
            http_5xx: http5xx,
            timeout: timeoutOn,
            low_confidence: lowConf ? parseFloat(lowConf) : null,
          },
          enabled: true,
        }),
      });
      if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
      setName("");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "unknown");
    } finally {
      setSubmitting(false);
    }
  }

  async function toggle(p: Policy) {
    await fetch(`${API_URL}/api/routing-policies/${p.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled: !p.enabled }),
    });
    await load();
  }

  async function remove(p: Policy) {
    if (!confirm(`Delete policy "${p.name}"?`)) return;
    await fetch(`${API_URL}/api/routing-policies/${p.id}`, { method: "DELETE" });
    await load();
  }

  return (
    <main className="p-6 text-fg">
      <h1 className="text-2xl font-semibold mb-1">Routing policies</h1>
      <p className="text-muted mb-6 text-sm">
        Pick the cheapest candidate model and fall back on failure. Middleware
        wiring is Step 8 — this page manages the rules.
      </p>

      {error && (
        <div className="mb-4 rounded border border-bad bg-bad-soft p-3 text-sm text-bad">
          {error}
        </div>
      )}

      <section className="mb-8 rounded border border-default bg-bg p-4">
        <h2 className="text-lg font-medium mb-3">Create policy</h2>
        <form onSubmit={handleCreate} className="grid grid-cols-2 gap-3 text-sm">
          <label className="flex flex-col gap-1">
            <span className="text-muted">Project</span>
            <select
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
              className="rounded border border-default bg-surface px-2 py-1"
            >
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-muted">Name</span>
            <input
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="cheap-first"
              className="rounded border border-default bg-surface px-2 py-1"
            />
          </label>
          <label className="flex flex-col gap-1 col-span-2">
            <span className="text-muted">Match JSONPath (against request body)</span>
            <input
              required
              value={jsonpath}
              onChange={(e) => setJsonpath(e.target.value)}
              className="rounded border border-default bg-surface px-2 py-1 font-mono"
            />
          </label>
          <label className="flex flex-col gap-1 col-span-2">
            <span className="text-muted">
              Candidate models (one per line, in fallback order)
            </span>
            <textarea
              required
              rows={3}
              value={candidatesText}
              onChange={(e) => setCandidatesText(e.target.value)}
              className="rounded border border-default bg-surface px-2 py-1 font-mono text-xs"
            />
          </label>
          <div className="col-span-2 flex flex-wrap gap-4 text-sm">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={http5xx}
                onChange={(e) => setHttp5xx(e.target.checked)}
              />
              <span>Fallback on HTTP 5xx</span>
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={timeoutOn}
                onChange={(e) => setTimeoutOn(e.target.checked)}
              />
              <span>Fallback on timeout</span>
            </label>
            <label className="flex items-center gap-2">
              <span>Min confidence:</span>
              <input
                type="number"
                step="0.05"
                min="0"
                max="1"
                value={lowConf}
                onChange={(e) => setLowConf(e.target.value)}
                placeholder="(off)"
                className="w-20 rounded border border-default bg-surface px-2 py-1"
              />
            </label>
          </div>
          <div className="col-span-2">
            <button
              type="submit"
              disabled={submitting}
              className="rounded bg-accent px-3 py-1.5 text-sm font-medium text-white hover:bg-accent disabled:opacity-50"
            >
              {submitting ? "Creating…" : "Create policy"}
            </button>
          </div>
        </form>
      </section>

      <section>
        <h2 className="text-lg font-medium mb-2">Policies ({policies.length})</h2>
        {loading && <div className="text-sm text-faint">Loading…</div>}
        {!loading && policies.length === 0 && (
          <div className="rounded border border-default bg-bg p-4 text-sm text-muted">
            No policies yet. Create one above.
          </div>
        )}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {policies.map((p) => (
            <div
              key={p.id}
              className="rounded border border-default bg-bg p-4"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="font-mono text-sm font-semibold">{p.name}</div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => toggle(p)}
                    className={
                      p.enabled
                        ? "rounded bg-ok-soft px-2 py-0.5 text-xs text-ok"
                        : "rounded bg-surface-1 px-2 py-0.5 text-xs text-muted"
                    }
                  >
                    {p.enabled ? "on" : "off"}
                  </button>
                  <button
                    onClick={() => remove(p)}
                    className="text-xs text-bad hover:text-bad"
                  >
                    delete
                  </button>
                </div>
              </div>
              <div className="text-xs text-muted mb-2 font-mono">
                {p.match_jsonpath}
              </div>
              <ol className="space-y-1 text-xs">
                {p.candidates.map((c, i) => (
                  <li key={i} className="flex items-center gap-2">
                    <span className="text-faint">#{i + 1}</span>
                    <span className="font-mono text-fg">{c.model}</span>
                  </li>
                ))}
              </ol>
              <div className="mt-2 text-xs text-faint">
                Fallback on:{" "}
                {[
                  p.fallback_on.http_5xx && "5xx",
                  p.fallback_on.timeout && "timeout",
                  p.fallback_on.low_confidence != null &&
                    `confidence < ${p.fallback_on.low_confidence}`,
                ]
                  .filter(Boolean)
                  .join(", ") || "—"}
              </div>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
