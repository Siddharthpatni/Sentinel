"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";

interface AssertionLog {
  type: string;
  passed: boolean;
  detail: string;
}

interface EvalCase {
  id: string;
  run_id: string;
  case_name: string;
  input: Record<string, unknown>;
  actual: Record<string, unknown> | null;
  passed: boolean;
  assertion_log: AssertionLog[];
  trace_id: string | null;
}

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

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function EvalRunDetailPage({
  params,
}: {
  params: Promise<{ id: string; runId: string }>;
}) {
  const { id, runId } = use(params);
  const [run, setRun] = useState<EvalRun | null>(null);
  const [cases, setCases] = useState<EvalCase[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API_URL}/api/evals/${id}/runs/${runId}`, {
          cache: "no-store",
        });
        if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
        const data = await res.json();
        setRun(data.run);
        setCases(data.cases);
      } catch (e) {
        setError(e instanceof Error ? e.message : "unknown");
      } finally {
        setLoading(false);
      }
    })();
  }, [id, runId]);

  return (
    <main className="p-6 text-fg">
      <Link href={`/evals/${id}`} className="text-sm text-ok hover:underline">
        ← Back to run history
      </Link>
      <h1 className="text-2xl font-semibold mt-2 mb-1">Run detail</h1>
      {run && (
        <p className="text-muted mb-6 text-sm">
          {new Date(run.started_at).toLocaleString()} — {run.passed}/{run.total} passed,{" "}
          {run.failed} failed — triggered by {run.triggered_by}
        </p>
      )}

      {error && (
        <div className="mb-4 rounded border border-bad bg-bad-soft p-3 text-sm text-bad">
          {error}
        </div>
      )}
      {loading && <div className="text-sm text-faint">Loading…</div>}

      <div className="space-y-2">
        {cases.map((c) => (
          <div key={c.id} className="rounded border border-default bg-bg">
            <button
              onClick={() => setExpanded(expanded === c.id ? null : c.id)}
              className="flex w-full items-center justify-between px-4 py-3 text-left"
            >
              <div className="flex items-center gap-2">
                <span
                  className={`inline-block h-2 w-2 rounded-full ${
                    c.passed ? "bg-ok" : "bg-bad"
                  }`}
                />
                <span className="font-mono text-sm">{c.case_name}</span>
              </div>
              <div className="flex items-center gap-3 text-xs text-muted">
                <span>
                  {c.assertion_log.filter((a) => a.passed).length}/{c.assertion_log.length}{" "}
                  assertions
                </span>
                {c.trace_id && (
                  <Link
                    href={`/?trace=${c.trace_id}`}
                    onClick={(e) => e.stopPropagation()}
                    className="text-ok hover:underline"
                  >
                    trace
                  </Link>
                )}
                <span>{expanded === c.id ? "▾" : "▸"}</span>
              </div>
            </button>
            {expanded === c.id && (
              <div className="space-y-3 border-t border-default px-4 py-3 text-xs">
                <div>
                  <div className="mb-1 text-faint">assertions</div>
                  <ul className="space-y-1">
                    {c.assertion_log.map((a, i) => (
                      <li
                        key={i}
                        className={`font-mono ${a.passed ? "text-ok" : "text-bad"}`}
                      >
                        [{a.passed ? "PASS" : "FAIL"}] {a.type} — {a.detail}
                      </li>
                    ))}
                  </ul>
                </div>
                <details>
                  <summary className="cursor-pointer text-muted">request</summary>
                  <pre className="mt-1 overflow-x-auto text-fg-soft">
                    {JSON.stringify(c.input, null, 2)}
                  </pre>
                </details>
                <details>
                  <summary className="cursor-pointer text-muted">response</summary>
                  <pre className="mt-1 overflow-x-auto text-fg-soft">
                    {JSON.stringify(c.actual, null, 2)}
                  </pre>
                </details>
              </div>
            )}
          </div>
        ))}
      </div>
    </main>
  );
}
