"use client";

import { useEffect, useState } from "react";

interface Project {
  id: string;
  name: string;
}

interface Credential {
  id: string;
  project_id: string;
  provider: string;
  label: string;
  key_fingerprint: string;
  is_active: boolean;
  created_at: string;
  last_used_at: string | null;
}

interface TestResult {
  ok: boolean;
  status_code: number;
  message: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const PROVIDERS = ["openai", "anthropic", "openrouter", "gemini"];

export default function KeysPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [creds, setCreds] = useState<Credential[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, TestResult>>({});
  const [testing, setTesting] = useState<Record<string, boolean>>({});

  const [showModal, setShowModal] = useState(false);
  const [formProvider, setFormProvider] = useState("openai");
  const [formLabel, setFormLabel] = useState("primary");
  const [formApiKey, setFormApiKey] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const pj = await fetch(`${API_URL}/api/projects`, { cache: "no-store" }).then((r) => r.json());
      setProjects(pj.projects);
      const pid = projectId || pj.projects[0]?.id || "";
      if (!projectId && pid) setProjectId(pid);
      if (pid) {
        const c = await fetch(`${API_URL}/api/credentials?project_id=${pid}`, {
          cache: "no-store",
        }).then((r) => r.json());
        setCreds(c.credentials);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "unknown");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setModalError(null);
    try {
      const res = await fetch(`${API_URL}/api/credentials`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: projectId,
          provider: formProvider,
          label: formLabel,
          api_key: formApiKey,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${res.status}`);
      }
      setShowModal(false);
      setFormApiKey("");
      setFormLabel("primary");
      await load();
    } catch (e) {
      setModalError(e instanceof Error ? e.message : "unknown");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleTest(id: string) {
    setTesting((t) => ({ ...t, [id]: true }));
    try {
      const res = await fetch(`${API_URL}/api/credentials/${id}/test`, { method: "POST" });
      const body: TestResult = await res.json();
      setTestResults((r) => ({ ...r, [id]: body }));
    } catch (e) {
      setTestResults((r) => ({
        ...r,
        [id]: { ok: false, status_code: 0, message: e instanceof Error ? e.message : "unknown" },
      }));
    } finally {
      setTesting((t) => ({ ...t, [id]: false }));
    }
  }

  async function handleToggle(c: Credential) {
    await fetch(`${API_URL}/api/credentials/${c.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_active: !c.is_active }),
    });
    await load();
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this credential? Requests will fall back to env vars or fail.")) return;
    await fetch(`${API_URL}/api/credentials/${id}`, { method: "DELETE" });
    await load();
  }

  return (
    <div className="mx-auto max-w-5xl p-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-neutral-100">Provider keys</h1>
          <p className="mt-1 text-sm text-neutral-400">
            Encrypted at rest with Fernet. Plaintext is never echoed back to the dashboard.
          </p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="rounded bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500"
        >
          Add key
        </button>
      </div>

      {projects.length > 1 && (
        <div className="mb-4">
          <label className="mr-2 text-sm text-neutral-400">Project:</label>
          <select
            value={projectId}
            onChange={(e) => setProjectId(e.target.value)}
            className="rounded border border-neutral-700 bg-neutral-900 px-3 py-1.5 text-sm text-neutral-100"
          >
            {projects.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </div>
      )}

      {error && <div className="mb-4 rounded bg-red-950 p-3 text-sm text-red-200">{error}</div>}
      {loading ? (
        <div className="text-neutral-500">Loading…</div>
      ) : creds.length === 0 ? (
        <div className="rounded border border-dashed border-neutral-700 p-12 text-center text-neutral-500">
          No keys configured. Click <span className="text-neutral-300">Add key</span> to get started.
        </div>
      ) : (
        <table className="w-full text-sm">
          <thead className="border-b border-neutral-800 text-left text-xs uppercase tracking-wider text-neutral-500">
            <tr>
              <th className="py-2 pr-4">Provider</th>
              <th className="py-2 pr-4">Label</th>
              <th className="py-2 pr-4">Fingerprint</th>
              <th className="py-2 pr-4">Status</th>
              <th className="py-2 pr-4">Last used</th>
              <th className="py-2"></th>
            </tr>
          </thead>
          <tbody>
            {creds.map((c) => {
              const t = testResults[c.id];
              return (
                <tr key={c.id} className="border-b border-neutral-900">
                  <td className="py-3 pr-4 font-medium text-neutral-100">{c.provider}</td>
                  <td className="py-3 pr-4 text-neutral-300">{c.label}</td>
                  <td className="py-3 pr-4 font-mono text-xs text-neutral-400">{c.key_fingerprint}</td>
                  <td className="py-3 pr-4">
                    <span
                      className={
                        c.is_active
                          ? "rounded bg-emerald-900/40 px-2 py-0.5 text-xs text-emerald-300"
                          : "rounded bg-neutral-800 px-2 py-0.5 text-xs text-neutral-400"
                      }
                    >
                      {c.is_active ? "active" : "disabled"}
                    </span>
                    {t && (
                      <span
                        className={
                          "ml-2 text-xs " + (t.ok ? "text-emerald-400" : "text-red-400")
                        }
                        title={t.message}
                      >
                        {t.ok ? "✓ valid" : `✗ ${t.status_code || "err"}`}
                      </span>
                    )}
                  </td>
                  <td className="py-3 pr-4 text-xs text-neutral-500">
                    {c.last_used_at ? new Date(c.last_used_at).toLocaleString() : "—"}
                  </td>
                  <td className="py-3 text-right">
                    <button
                      onClick={() => handleTest(c.id)}
                      disabled={testing[c.id]}
                      className="mr-2 text-xs text-neutral-400 hover:text-neutral-100"
                    >
                      {testing[c.id] ? "testing…" : "test"}
                    </button>
                    <button
                      onClick={() => handleToggle(c)}
                      className="mr-2 text-xs text-neutral-400 hover:text-neutral-100"
                    >
                      {c.is_active ? "disable" : "enable"}
                    </button>
                    <button
                      onClick={() => handleDelete(c.id)}
                      className="text-xs text-red-400 hover:text-red-300"
                    >
                      delete
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}

      {showModal && (
        <div className="fixed inset-0 z-20 flex items-center justify-center bg-black/60">
          <form
            onSubmit={handleCreate}
            className="w-full max-w-md rounded-lg border border-neutral-800 bg-neutral-950 p-6"
          >
            <h2 className="mb-4 text-lg font-semibold text-neutral-100">Add provider key</h2>
            <label className="mb-3 block text-xs text-neutral-400">
              Provider
              <select
                value={formProvider}
                onChange={(e) => setFormProvider(e.target.value)}
                className="mt-1 w-full rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-neutral-100"
              >
                {PROVIDERS.map((p) => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </select>
            </label>
            <label className="mb-3 block text-xs text-neutral-400">
              Label
              <input
                value={formLabel}
                onChange={(e) => setFormLabel(e.target.value)}
                required
                className="mt-1 w-full rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-neutral-100"
              />
            </label>
            <label className="mb-3 block text-xs text-neutral-400">
              API key
              <input
                type="password"
                value={formApiKey}
                onChange={(e) => setFormApiKey(e.target.value)}
                required
                minLength={8}
                placeholder="sk-..."
                className="mt-1 w-full rounded border border-neutral-700 bg-neutral-900 px-3 py-2 font-mono text-sm text-neutral-100"
              />
              <span className="mt-1 block text-[10px] text-neutral-500">
                Encrypted with Fernet before storage. Only the fingerprint is shown afterwards.
              </span>
            </label>
            {modalError && (
              <div className="mb-3 rounded bg-red-950 p-2 text-xs text-red-200">{modalError}</div>
            )}
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowModal(false)}
                className="rounded px-3 py-1.5 text-sm text-neutral-400 hover:text-neutral-100"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="rounded bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
              >
                {submitting ? "Saving…" : "Save"}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
