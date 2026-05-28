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
          <h1 className="text-2xl font-semibold text-fg">Provider keys</h1>
          <p className="mt-1 text-sm text-muted">
            Encrypted at rest with Fernet. Plaintext is never echoed back to the dashboard.
          </p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="rounded bg-accent px-4 py-2 text-sm font-medium text-white hover:opacity-90"
        >
          Add key
        </button>
      </div>

      {projects.length > 1 && (
        <div className="mb-4">
          <label className="mr-2 text-sm text-muted">Project:</label>
          <select
            value={projectId}
            onChange={(e) => setProjectId(e.target.value)}
            className="rounded border border-default bg-surface px-3 py-1.5 text-sm text-fg"
          >
            {projects.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </div>
      )}

      {error && <div className="mb-4 rounded bg-bad-soft p-3 text-sm text-bad">{error}</div>}
      {loading ? (
        <div className="text-faint">Loading…</div>
      ) : creds.length === 0 ? (
        <div className="rounded border border-dashed border-default p-12 text-center text-faint">
          No keys configured. Click <span className="text-fg-soft">Add key</span> to get started.
        </div>
      ) : (
        <table className="w-full text-sm">
          <thead className="border-b border-default text-left text-xs uppercase tracking-wider text-faint">
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
                <tr key={c.id} className="border-b border-subtle">
                  <td className="py-3 pr-4 font-medium text-fg">{c.provider}</td>
                  <td className="py-3 pr-4 text-fg-soft">{c.label}</td>
                  <td className="py-3 pr-4 font-mono text-xs text-muted">{c.key_fingerprint}</td>
                  <td className="py-3 pr-4">
                    <span
                      className={
                        c.is_active
                          ? "rounded bg-ok-soft px-2 py-0.5 text-xs text-ok"
                          : "rounded bg-surface-1 px-2 py-0.5 text-xs text-muted"
                      }
                    >
                      {c.is_active ? "active" : "disabled"}
                    </span>
                    {t && (
                      <span
                        className={
                          "ml-2 text-xs " + (t.ok ? "text-ok" : "text-bad")
                        }
                        title={t.message}
                      >
                        {t.ok ? "✓ valid" : `✗ ${t.status_code || "err"}`}
                      </span>
                    )}
                  </td>
                  <td className="py-3 pr-4 text-xs text-faint">
                    {c.last_used_at ? new Date(c.last_used_at).toLocaleString() : "—"}
                  </td>
                  <td className="py-3 text-right">
                    <button
                      onClick={() => handleTest(c.id)}
                      disabled={testing[c.id]}
                      className="mr-2 text-xs text-muted hover:text-fg"
                    >
                      {testing[c.id] ? "testing…" : "test"}
                    </button>
                    <button
                      onClick={() => handleToggle(c)}
                      className="mr-2 text-xs text-muted hover:text-fg"
                    >
                      {c.is_active ? "disable" : "enable"}
                    </button>
                    <button
                      onClick={() => handleDelete(c.id)}
                      className="text-xs text-bad hover:text-bad"
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
        <div className="fixed inset-0 z-20 flex items-center justify-center bg-bg/60">
          <form
            onSubmit={handleCreate}
            className="w-full max-w-md rounded-lg border border-default bg-bg p-6"
          >
            <h2 className="mb-4 text-lg font-semibold text-fg">Add provider key</h2>
            <label className="mb-3 block text-xs text-muted">
              Provider
              <select
                value={formProvider}
                onChange={(e) => setFormProvider(e.target.value)}
                className="mt-1 w-full rounded border border-default bg-surface px-3 py-2 text-sm text-fg"
              >
                {PROVIDERS.map((p) => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </select>
            </label>
            <label className="mb-3 block text-xs text-muted">
              Label
              <input
                value={formLabel}
                onChange={(e) => setFormLabel(e.target.value)}
                required
                className="mt-1 w-full rounded border border-default bg-surface px-3 py-2 text-sm text-fg"
              />
            </label>
            <label className="mb-3 block text-xs text-muted">
              API key
              <input
                type="password"
                value={formApiKey}
                onChange={(e) => setFormApiKey(e.target.value)}
                required
                minLength={8}
                placeholder="sk-..."
                className="mt-1 w-full rounded border border-default bg-surface px-3 py-2 font-mono text-sm text-fg"
              />
              <span className="mt-1 block text-[10px] text-faint">
                Encrypted with Fernet before storage. Only the fingerprint is shown afterwards.
              </span>
            </label>
            {modalError && (
              <div className="mb-3 rounded bg-bad-soft p-2 text-xs text-bad">{modalError}</div>
            )}
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowModal(false)}
                className="rounded px-3 py-1.5 text-sm text-muted hover:text-fg"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="rounded bg-accent px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
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
