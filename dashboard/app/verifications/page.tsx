"use client";

import { useEffect, useState } from "react";

interface Rule {
  id: string;
  project_id: string;
  name: string;
  match_jsonpath: string;
  sample_rate: number;
  judge_model: string;
  judge_prompt_template: string;
  enabled: boolean;
}

interface Project {
  id: string;
  name: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const DEFAULT_TEMPLATE =
  "You are a strict grader. Given the model output below, answer PASS or FAIL.\n\nOutput:\n{{ output }}";

export default function VerificationsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState<string>("");
  const [rules, setRules] = useState<Rule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [name, setName] = useState("");
  const [jsonpath, setJsonpath] = useState("$.choices[0].message.content");
  const [sampleRate, setSampleRate] = useState(1.0);
  const [judgeModel, setJudgeModel] = useState("gpt-4o-mini");
  const [template, setTemplate] = useState(DEFAULT_TEMPLATE);

  async function loadProjects() {
    const res = await fetch(`${API_URL}/api/projects`, { cache: "no-store" });
    if (!res.ok) throw new Error(`projects: ${res.status}`);
    const data = await res.json();
    setProjects(data.projects);
    if (data.projects.length > 0 && !projectId) {
      setProjectId(data.projects[0].id);
    }
  }

  async function loadRules() {
    const res = await fetch(`${API_URL}/api/verification-rules`, { cache: "no-store" });
    if (!res.ok) throw new Error(`rules: ${res.status}`);
    const data = await res.json();
    setRules(data.rules);
  }

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      await Promise.all([loadProjects(), loadRules()]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "unknown error");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!projectId) {
      setError("Select a project first");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/verification-rules`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: projectId,
          name,
          match_jsonpath: jsonpath,
          sample_rate: sampleRate,
          judge_model: judgeModel,
          judge_prompt_template: template,
          enabled: true,
        }),
      });
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(`${res.status}: ${detail}`);
      }
      setName("");
      await loadRules();
    } catch (e) {
      setError(e instanceof Error ? e.message : "unknown error");
    } finally {
      setSubmitting(false);
    }
  }

  async function toggleRule(rule: Rule) {
    const res = await fetch(`${API_URL}/api/verification-rules/${rule.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled: !rule.enabled }),
    });
    if (res.ok) await loadRules();
  }

  async function deleteRule(rule: Rule) {
    if (!confirm(`Delete rule "${rule.name}"?`)) return;
    const res = await fetch(`${API_URL}/api/verification-rules/${rule.id}`, {
      method: "DELETE",
    });
    if (res.ok) await loadRules();
  }

  return (
    <main className="p-6 text-neutral-100">
      <h1 className="text-2xl font-semibold mb-1">Verifications</h1>
      <p className="text-neutral-400 mb-6 text-sm">
        Judge-model evaluations of primary calls. Phase 2 — Step 2 of 15.
      </p>

      {error && (
        <div className="mb-4 rounded border border-red-800 bg-red-950/40 p-3 text-sm text-red-300">
          {error}
        </div>
      )}

      <section className="mb-8 rounded border border-neutral-800 bg-neutral-950 p-4">
        <h2 className="text-lg font-medium mb-3">Create rule</h2>
        <form onSubmit={handleCreate} className="grid grid-cols-2 gap-3 text-sm">
          <label className="flex flex-col gap-1">
            <span className="text-neutral-400">Project</span>
            <select
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
              className="rounded border border-neutral-700 bg-neutral-900 px-2 py-1"
            >
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-neutral-400">Name</span>
            <input
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="answer-quality"
              className="rounded border border-neutral-700 bg-neutral-900 px-2 py-1"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-neutral-400">Match JSONPath</span>
            <input
              required
              value={jsonpath}
              onChange={(e) => setJsonpath(e.target.value)}
              className="rounded border border-neutral-700 bg-neutral-900 px-2 py-1 font-mono"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-neutral-400">Sample rate (0–1)</span>
            <input
              required
              type="number"
              step="0.01"
              min="0"
              max="1"
              value={sampleRate}
              onChange={(e) => setSampleRate(parseFloat(e.target.value))}
              className="rounded border border-neutral-700 bg-neutral-900 px-2 py-1"
            />
          </label>
          <label className="flex flex-col gap-1 col-span-2">
            <span className="text-neutral-400">Judge model</span>
            <input
              required
              value={judgeModel}
              onChange={(e) => setJudgeModel(e.target.value)}
              className="rounded border border-neutral-700 bg-neutral-900 px-2 py-1 font-mono"
            />
          </label>
          <label className="flex flex-col gap-1 col-span-2">
            <span className="text-neutral-400">Judge prompt template</span>
            <textarea
              required
              rows={4}
              value={template}
              onChange={(e) => setTemplate(e.target.value)}
              className="rounded border border-neutral-700 bg-neutral-900 px-2 py-1 font-mono text-xs"
            />
          </label>
          <div className="col-span-2">
            <button
              type="submit"
              disabled={submitting}
              className="rounded bg-emerald-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-600 disabled:opacity-50"
            >
              {submitting ? "Creating…" : "Create rule"}
            </button>
          </div>
        </form>
      </section>

      <section>
        <h2 className="text-lg font-medium mb-2">
          Verification rules ({rules.length})
        </h2>
        {loading && (
          <div className="text-sm text-neutral-500">Loading…</div>
        )}
        {!loading && rules.length === 0 && (
          <div className="rounded border border-neutral-800 bg-neutral-950 p-4 text-sm text-neutral-400">
            No rules yet. Create one above.
          </div>
        )}
        {rules.length > 0 && (
          <table className="w-full text-sm border border-neutral-800 rounded">
            <thead className="bg-neutral-900 text-neutral-400 text-left">
              <tr>
                <th className="px-3 py-2">Name</th>
                <th className="px-3 py-2">Judge model</th>
                <th className="px-3 py-2">Sample</th>
                <th className="px-3 py-2">Enabled</th>
                <th className="px-3 py-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rules.map((r) => (
                <tr key={r.id} className="border-t border-neutral-800">
                  <td className="px-3 py-2 font-mono">{r.name}</td>
                  <td className="px-3 py-2">{r.judge_model}</td>
                  <td className="px-3 py-2">{r.sample_rate}</td>
                  <td className="px-3 py-2">
                    <button
                      onClick={() => toggleRule(r)}
                      className={
                        r.enabled
                          ? "rounded bg-emerald-900/40 px-2 py-0.5 text-emerald-300 hover:bg-emerald-900/60"
                          : "rounded bg-neutral-800 px-2 py-0.5 text-neutral-400 hover:bg-neutral-700"
                      }
                    >
                      {r.enabled ? "on" : "off"}
                    </button>
                  </td>
                  <td className="px-3 py-2 text-right">
                    <button
                      onClick={() => deleteRule(r)}
                      className="text-red-400 hover:text-red-300"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </main>
  );
}
