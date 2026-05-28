"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { use } from "react";

interface EvalRun {
  id: string;
  eval_id: string;
  started_at: string;
  finished_at: string | null;
  total: number;
  passed: number;
  failed: number;
  triggered_by: string;
  git_sha: string | null;
}

interface EvalSummary {
  id: string;
  name: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function EvalRunsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [evalRow, setEvalRow] = useState<EvalSummary | null>(null);
  const [runs, setRuns] = useState<EvalRun[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [evList, runList] = await Promise.all([
          fetch(`${API_URL}/api/evals`, { cache: "no-store" }).then((r) => r.json()),
          fetch(`${API_URL}/api/evals/${id}/runs`, { cache: "no-store" }).then((r) => r.json()),
        ]);
        const row = (evList.evals || []).find((e: EvalSummary) => e.id === id) ?? null;
        setEvalRow(row);
        setRuns(runList.runs || []);
      } catch (e) {
        setError(e instanceof Error ? e.message : "unknown");
      } finally {
        setLoading(false);
      }
    })();
  }, [id]);

  return (
    <main className="p-6 text-fg">
      <Link href="/evals" className="text-sm text-ok hover:underline">
        ← Back to evals
      </Link>
      <h1 className="text-2xl font-semibold mt-2 mb-1">
        {evalRow?.name ?? "Eval"}
      </h1>
      <p className="text-muted mb-6 text-sm">Run history</p>

      {error && (
        <div className="mb-4 rounded border border-bad bg-bad-soft p-3 text-sm text-bad">
          {error}
        </div>
      )}
      {loading && <div className="text-sm text-faint">Loading…</div>}
      {!loading && runs.length === 0 && (
        <div className="rounded border border-default bg-bg p-4 text-sm text-muted">
          No runs yet. Trigger one from the evals page.
        </div>
      )}

      <div className="space-y-2">
        {runs.map((r) => {
          const passRate = r.total > 0 ? Math.round((r.passed / r.total) * 100) : 0;
          const colour =
            r.failed === 0 ? "text-ok" : r.passed === 0 ? "text-bad" : "text-warn";
          return (
            <Link
              key={r.id}
              href={`/evals/${id}/runs/${r.id}`}
              className="block rounded border border-default bg-bg px-4 py-3 hover:border-accent"
            >
              <div className="flex items-center justify-between text-sm">
                <div>
                  <div className="font-mono text-xs text-faint">
                    {new Date(r.started_at).toLocaleString()}
                  </div>
                  <div className="text-fg-soft">
                    triggered by <span className="text-fg">{r.triggered_by}</span>
                    {r.git_sha && (
                      <span className="ml-2 font-mono text-xs text-faint">
                        {r.git_sha.slice(0, 7)}
                      </span>
                    )}
                  </div>
                </div>
                <div className={`text-right ${colour}`}>
                  <div className="text-lg font-semibold">{passRate}%</div>
                  <div className="text-xs">
                    {r.passed}/{r.total} passed
                  </div>
                </div>
              </div>
            </Link>
          );
        })}
      </div>
    </main>
  );
}
