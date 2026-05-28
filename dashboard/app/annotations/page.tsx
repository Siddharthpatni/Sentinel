"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { type Trace, fetchUnannotatedTraces } from "@/lib/api";

export default function AnnotationsQueuePage() {
  const [traces, setTraces] = useState<Trace[]>([]);
  const [total, setTotal] = useState(0);
  const [err, setErr] = useState<string | null>(null);

  async function load() {
    try {
      const r = await fetchUnannotatedTraces(50);
      setTraces(r.traces);
      setTotal(r.total_count);
    } catch (e) {
      setErr(String(e));
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <main className="flex-1 px-6 py-8 max-w-[1200px] w-full mx-auto">
      <header className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-fg">
          Annotation queue
        </h1>
        <p className="text-sm text-muted">
          Traces with no human feedback yet. Open one to thumbs-up / down and
          add a comment.
        </p>
        <p className="text-xs text-faint mt-1">
          {total} unannotated · showing {traces.length}
        </p>
      </header>

      {err && <p className="text-bad text-sm mb-4">{err}</p>}

      <div className="glass-panel overflow-hidden">
        {traces.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-title">Inbox zero</div>
            <p className="empty-state-desc">
              Every trace has at least one annotation. Nice.
            </p>
          </div>
        ) : (
          <table className="trace-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Provider</th>
                <th>Model</th>
                <th>Latency</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {traces.map((t) => (
                <tr
                  key={t.id}
                  onClick={() => {
                    window.location.href = `/traces/${t.id}`;
                  }}
                >
                  <td className="text-faint">
                    {new Date(t.created_at).toLocaleString()}
                  </td>
                  <td>
                    <span className={`badge badge-${t.provider}`}>
                      {t.provider}
                    </span>
                  </td>
                  <td className="font-mono">{t.model}</td>
                  <td className="font-mono">{t.latency_ms}ms</td>
                  <td>
                    <span
                      className={
                        t.status_code >= 400
                          ? "badge badge-error"
                          : "badge badge-success"
                      }
                    >
                      {t.status_code}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <p className="text-xs text-faint mt-4">
        Annotate from{" "}
        <Link href="/" className="text-accent hover:underline">
          any trace detail page
        </Link>
        .
      </p>
    </main>
  );
}
