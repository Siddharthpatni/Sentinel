"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  type Project,
  type SessionSummary,
  fetchProjects,
  fetchSessions,
} from "@/lib/api";

function formatDate(s: string): string {
  return new Date(s).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

export default function SessionsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState<string>("");
  const [rows, setRows] = useState<SessionSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchProjects().then((p) => {
      setProjects(p);
      if (p.length > 0) setProjectId(p[0].id);
    });
  }, []);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setRows(await fetchSessions(projectId || undefined));
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    reload();
  }, [reload]);

  return (
    <main className="px-6 py-8 max-w-[1200px] w-full mx-auto">
      <div className="mb-6 flex items-center gap-4">
        <h1
          className="text-2xl font-bold tracking-tight"
          style={{ color: "var(--sentinel-text-primary)" }}
        >
          Sessions
        </h1>
        <span
          className="text-sm"
          style={{ color: "var(--sentinel-text-muted)" }}
        >
          Conversation threads grouped by <code>_sentinel.session_id</code>
        </span>
        <div className="ml-auto">
          <select
            className="bg-neutral-900 border border-neutral-700 rounded px-2 py-1 text-sm text-neutral-100"
            value={projectId}
            onChange={(e) => setProjectId(e.target.value)}
          >
            <option value="">All projects</option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="glass-panel overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left border-b border-neutral-800">
              <th className="px-4 py-3 text-neutral-400 font-medium">Name</th>
              <th className="px-4 py-3 text-neutral-400 font-medium">External ID</th>
              <th className="px-4 py-3 text-neutral-400 font-medium">Traces</th>
              <th className="px-4 py-3 text-neutral-400 font-medium">Last seen</th>
              <th className="px-4 py-3 text-neutral-400 font-medium">Created</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-neutral-500">
                  Loading…
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-neutral-500">
                  No sessions yet. Tag a request with{" "}
                  <code>extra_body=&#123;&quot;_sentinel&quot;: &#123;&quot;session_id&quot;: &quot;…&quot;&#125;&#125;</code>.
                </td>
              </tr>
            ) : (
              rows.map((s) => (
                <tr
                  key={s.id}
                  className="border-b border-neutral-900 hover:bg-neutral-900/40"
                >
                  <td className="px-4 py-3">
                    <Link
                      href={`/sessions/${s.id}`}
                      className="text-emerald-400 hover:underline"
                    >
                      {s.name || <span className="text-neutral-500">(unnamed)</span>}
                    </Link>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-neutral-300">
                    {s.external_id}
                  </td>
                  <td className="px-4 py-3 text-neutral-200">{s.trace_count}</td>
                  <td className="px-4 py-3 text-neutral-400">
                    {formatDate(s.last_seen_at)}
                  </td>
                  <td className="px-4 py-3 text-neutral-500">
                    {formatDate(s.created_at)}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </main>
  );
}
