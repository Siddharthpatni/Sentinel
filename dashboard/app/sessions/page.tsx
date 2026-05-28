"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  type Project,
  type SessionSummary,
  fetchProjects,
  fetchSessions,
} from "@/lib/api";
import { ErrorBanner } from "@/components/error-banner";
import { EmptyState, TableSkeleton } from "@/components/empty-state";

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
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    fetchProjects()
      .then((p) => {
        setProjects(p);
        if (p.length > 0) setProjectId(p[0].id);
      })
      .catch((e) => setErr(e instanceof Error ? e.message : String(e)));
  }, []);

  const reload = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      setRows(await fetchSessions(projectId || undefined));
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
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
            className="bg-surface border border-default rounded px-2 py-1 text-sm text-fg"
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
        {err && (
          <div className="p-4">
            <ErrorBanner message={err} onRetry={reload} />
          </div>
        )}
        {loading ? (
          <TableSkeleton rows={6} />
        ) : rows.length === 0 ? (
          <EmptyState
            title="No sessions yet"
            description={
              <>
                Tag a request with{" "}
                <code>
                  extra_body=&#123;&quot;_sentinel&quot;:
                  &#123;&quot;session_id&quot;: &quot;…&quot;&#125;&#125;
                </code>{" "}
                to group traces into conversation threads.
              </>
            }
          />
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left border-b border-default">
                <th className="px-4 py-3 text-muted font-medium">Name</th>
                <th className="px-4 py-3 text-muted font-medium">External ID</th>
                <th className="px-4 py-3 text-muted font-medium">Traces</th>
                <th className="px-4 py-3 text-muted font-medium">Last seen</th>
                <th className="px-4 py-3 text-muted font-medium">Created</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((s) => (
                <tr
                  key={s.id}
                  className="border-b border-subtle hover:bg-surface/40"
                >
                  <td className="px-4 py-3">
                    <Link
                      href={`/sessions/${s.id}`}
                      className="text-ok hover:underline"
                    >
                      {s.name || <span className="text-faint">(unnamed)</span>}
                    </Link>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-fg-soft">
                    {s.external_id}
                  </td>
                  <td className="px-4 py-3 text-fg">{s.trace_count}</td>
                  <td className="px-4 py-3 text-muted">
                    {formatDate(s.last_seen_at)}
                  </td>
                  <td className="px-4 py-3 text-faint">
                    {formatDate(s.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </main>
  );
}
