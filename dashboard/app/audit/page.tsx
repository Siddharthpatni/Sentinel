"use client";

import { useCallback, useEffect, useState } from "react";
import {
  type AuditClassifier,
  type Project,
  createClassifier,
  deleteClassifier,
  fetchClassifiers,
  fetchProjects,
  verifyAuditChain,
} from "@/lib/api";

const TIERS = ["unacceptable", "high", "limited", "minimal"] as const;

export default function AuditPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState<string>("");
  const [rows, setRows] = useState<AuditClassifier[]>([]);
  const [loading, setLoading] = useState(true);
  const [verifyResult, setVerifyResult] = useState<{
    ok: boolean;
    checked: number;
    error: string | null;
  } | null>(null);

  const [name, setName] = useState("");
  const [pattern, setPattern] = useState("$.messages[?(@.role == 'user')]");
  const [tier, setTier] = useState<(typeof TIERS)[number]>("high");
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
      setRows(await fetchClassifiers(projectId));
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
      await createClassifier({
        project_id: projectId,
        name,
        match_jsonpath: pattern,
        risk_tier: tier,
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
    if (!confirm("Delete this classifier?")) return;
    await deleteClassifier(id);
    await reload();
  }

  async function verify() {
    if (!projectId) return;
    setVerifyResult(await verifyAuditChain(projectId));
  }

  const exportUrl = projectId
    ? `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/audit/export?project_id=${projectId}`
    : "#";

  return (
    <main className="mx-auto max-w-5xl space-y-6 px-6 py-8 text-fg">
      <header>
        <h1 className="text-xl font-semibold tracking-tight">EU AI Act Audit</h1>
        <p className="text-sm text-muted">
          Tier classifiers tag inbound requests; the tamper-evident ledger
          records every decision.
        </p>
      </header>

      <section className="rounded border border-default bg-bg p-4">
        <label className="block text-xs font-medium text-muted">
          Project
        </label>
        <select
          className="mt-1 rounded border border-default bg-surface px-2 py-1 text-sm"
          value={projectId}
          onChange={(e) => setProjectId(e.target.value)}
        >
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>

        <div className="mt-3 flex items-center gap-2">
          <button
            className="rounded bg-accent px-3 py-1.5 text-sm font-medium text-white hover:opacity-90"
            onClick={verify}
          >
            Verify chain
          </button>
          <a
            className="rounded border border-default px-3 py-1.5 text-sm hover:bg-surface"
            href={exportUrl}
            target="_blank"
            rel="noreferrer"
          >
            Export NDJSON
          </a>
          {verifyResult && (
            <span
              className={
                "ml-2 rounded px-2 py-1 text-xs " +
                (verifyResult.ok
                  ? "bg-ok-soft text-ok"
                  : "bg-bad-soft text-bad")
              }
            >
              {verifyResult.ok
                ? `OK · ${verifyResult.checked} entries`
                : `BROKEN · ${verifyResult.error}`}
            </span>
          )}
        </div>
      </section>

      <section className="rounded border border-default bg-bg p-4">
        <h2 className="text-sm font-semibold">New classifier</h2>
        <form onSubmit={submit} className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-4">
          <input
            className="rounded border border-default bg-surface px-2 py-1 text-sm"
            placeholder="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
          <input
            className="col-span-2 rounded border border-default bg-surface px-2 py-1 text-sm font-mono"
            placeholder="$.messages[?(@.role == 'user')]"
            value={pattern}
            onChange={(e) => setPattern(e.target.value)}
            required
          />
          <select
            className="rounded border border-default bg-surface px-2 py-1 text-sm"
            value={tier}
            onChange={(e) => setTier(e.target.value as (typeof TIERS)[number])}
          >
            {TIERS.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
          <button
            type="submit"
            disabled={submitting || !projectId}
            className="col-span-full rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50"
          >
            {submitting ? "Creating…" : "Create classifier"}
          </button>
          {err && <div className="col-span-full text-xs text-bad">{err}</div>}
        </form>
      </section>

      <section className="rounded border border-default bg-bg">
        <table className="w-full text-sm">
          <thead className="text-xs text-muted">
            <tr>
              <th className="px-4 py-2 text-left">Name</th>
              <th className="px-4 py-2 text-left">Pattern</th>
              <th className="px-4 py-2 text-left">Tier</th>
              <th className="px-4 py-2 text-left">Enabled</th>
              <th />
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
                  No classifiers yet.
                </td>
              </tr>
            ) : (
              rows.map((r) => (
                <tr key={r.id} className="border-t border-subtle">
                  <td className="px-4 py-2 font-medium">{r.name}</td>
                  <td className="px-4 py-2 font-mono text-xs text-fg-soft">
                    {r.match_jsonpath}
                  </td>
                  <td className="px-4 py-2">
                    <span className="rounded bg-surface-1 px-2 py-0.5 text-xs">
                      {r.risk_tier}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-xs">
                    {r.enabled ? "yes" : "no"}
                  </td>
                  <td className="px-4 py-2">
                    <button
                      onClick={() => remove(r.id)}
                      className="text-xs text-bad hover:text-bad"
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
