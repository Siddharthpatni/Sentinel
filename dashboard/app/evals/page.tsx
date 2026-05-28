"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

interface Eval {
  id: string;
  project_id: string;
  name: string;
  yaml_source: string;
}

interface Project {
  id: string;
  name: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const SAMPLE_YAML = `name: customer-support-quality
target:
  endpoint: /v1/chat/completions
  model: gpt-4o-mini
cases:
  - name: refund-tone
    input:
      messages:
        - role: user
          content: I want a refund for order #1234.
    assertions:
      - type: contains
        path: $.choices[0].message.content
        value: refund
        case_sensitive: false
      - type: max_latency_ms
        value: 5000
`;

export default function EvalsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [evals, setEvals] = useState<Eval[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [yaml, setYaml] = useState(SAMPLE_YAML);
  const [expanded, setExpanded] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [pj, ev] = await Promise.all([
        fetch(`${API_URL}/api/projects`, { cache: "no-store" }).then((r) => r.json()),
        fetch(`${API_URL}/api/evals`, { cache: "no-store" }).then((r) => r.json()),
      ]);
      setProjects(pj.projects);
      if (pj.projects.length > 0 && !projectId) setProjectId(pj.projects[0].id);
      setEvals(ev.evals);
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
      const res = await fetch(`${API_URL}/api/evals`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project_id: projectId, yaml_source: yaml }),
      });
      if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "unknown");
    } finally {
      setSubmitting(false);
    }
  }

  async function remove(e: Eval) {
    if (!confirm(`Delete eval "${e.name}"?`)) return;
    await fetch(`${API_URL}/api/evals/${e.id}`, { method: "DELETE" });
    await load();
  }

  async function runEval(e: Eval) {
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/evals/${e.id}/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ triggered_by: "manual" }),
      });
      if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
      const run = await res.json();
      window.location.href = `/evals/${e.id}/runs/${run.id}`;
    } catch (err) {
      setError(err instanceof Error ? err.message : "run failed");
    }
  }

  return (
    <main className="p-6 text-fg">
      <h1 className="text-2xl font-semibold mb-1">Evals</h1>
      <p className="text-muted mb-6 text-sm">
        YAML-defined regression suites. Parser + 7 assertion types live now;
        runner + CI script land in Steps 11–14.
      </p>

      {error && (
        <div className="mb-4 rounded border border-bad bg-bad-soft p-3 text-sm text-bad">
          {error}
        </div>
      )}

      <section className="mb-8 rounded border border-default bg-bg p-4">
        <h2 className="text-lg font-medium mb-3">Create or update a suite</h2>
        <form onSubmit={handleCreate} className="space-y-3 text-sm">
          <label className="flex flex-col gap-1">
            <span className="text-muted">Project</span>
            <select
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
              className="w-64 rounded border border-default bg-surface px-2 py-1"
            >
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-muted">
              YAML suite (validated server-side; upsert on suite name)
            </span>
            <textarea
              required
              rows={14}
              value={yaml}
              onChange={(e) => setYaml(e.target.value)}
              className="rounded border border-default bg-surface px-3 py-2 font-mono text-xs"
            />
          </label>
          <button
            type="submit"
            disabled={submitting}
            className="rounded bg-accent px-3 py-1.5 text-sm font-medium text-white hover:bg-accent disabled:opacity-50"
          >
            {submitting ? "Saving…" : "Save suite"}
          </button>
        </form>
      </section>

      <section>
        <h2 className="text-lg font-medium mb-2">Suites ({evals.length})</h2>
        {loading && <div className="text-sm text-faint">Loading…</div>}
        {!loading && evals.length === 0 && (
          <div className="rounded border border-default bg-bg p-4 text-sm text-muted">
            No suites yet. Paste a YAML suite above to get started.
          </div>
        )}
        <div className="space-y-2">
          {evals.map((e) => (
            <div
              key={e.id}
              className="rounded border border-default bg-bg"
            >
              <div className="flex items-center justify-between px-4 py-3">
                <button
                  onClick={() => setExpanded(expanded === e.id ? null : e.id)}
                  className="font-mono text-sm font-semibold text-left hover:text-ok"
                >
                  {expanded === e.id ? "▾" : "▸"} {e.name}
                </button>
                <div className="flex items-center gap-3 text-xs">
                  <Link
                    href={`/evals/${e.id}`}
                    className="rounded border border-default px-2 py-0.5 text-fg-soft hover:bg-surface-1"
                  >
                    runs
                  </Link>
                  <button
                    onClick={() => runEval(e)}
                    className="rounded bg-accent px-2 py-0.5 text-white hover:bg-accent"
                  >
                    run now
                  </button>
                  <button
                    onClick={() => remove(e)}
                    className="text-bad hover:text-bad"
                  >
                    delete
                  </button>
                </div>
              </div>
              {expanded === e.id && (
                <pre className="border-t border-default bg-bg px-4 py-3 text-xs text-fg-soft overflow-x-auto">
                  {e.yaml_source}
                </pre>
              )}
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
