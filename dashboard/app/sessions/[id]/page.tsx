"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  type SessionSummary,
  fetchSession,
} from "@/lib/api";

export default function SessionDetailPage() {
  const params = useParams();
  const sessionId = params.id as string;
  const [session, setSession] = useState<SessionSummary | null>(null);
  const [traceIds, setTraceIds] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchSession(sessionId)
      .then((r) => {
        setSession(r.session);
        setTraceIds(r.trace_ids);
      })
      .catch((e) => setError(e.message));
  }, [sessionId]);

  if (error) {
    return (
      <main className="px-6 py-8 max-w-[1000px] mx-auto">
        <p className="text-red-400">{error}</p>
        <Link href="/sessions" className="text-emerald-400 hover:underline">
          ← Back to sessions
        </Link>
      </main>
    );
  }

  if (!session) {
    return (
      <main className="px-6 py-8 max-w-[1000px] mx-auto text-neutral-500">
        Loading…
      </main>
    );
  }

  return (
    <main className="px-6 py-8 max-w-[1000px] w-full mx-auto">
      <Link
        href="/sessions"
        className="text-sm text-neutral-400 hover:text-neutral-200"
      >
        ← All sessions
      </Link>
      <h1
        className="mt-2 text-2xl font-bold tracking-tight"
        style={{ color: "var(--sentinel-text-primary)" }}
      >
        {session.name || session.external_id}
      </h1>
      <p className="text-sm text-neutral-500 mt-1">
        <span className="font-mono">{session.external_id}</span> ·{" "}
        {traceIds.length} traces · last seen{" "}
        {new Date(session.last_seen_at).toLocaleString()}
      </p>

      {Object.keys(session.metadata_json || {}).length > 0 && (
        <pre className="mt-4 glass-panel p-3 text-xs overflow-x-auto text-neutral-300">
          {JSON.stringify(session.metadata_json, null, 2)}
        </pre>
      )}

      <h2 className="mt-8 mb-3 text-sm font-semibold text-neutral-300 uppercase tracking-wide">
        Traces in order
      </h2>
      <ol className="space-y-2">
        {traceIds.map((id, i) => (
          <li key={id} className="flex items-center gap-3">
            <span className="text-neutral-600 text-xs w-6 text-right">
              {i + 1}.
            </span>
            <Link
              href={`/traces/${id}`}
              className="font-mono text-xs text-emerald-400 hover:underline"
            >
              {id}
            </Link>
          </li>
        ))}
        {traceIds.length === 0 && (
          <li className="text-neutral-500 text-sm">
            No traces stamped with this session yet.
          </li>
        )}
      </ol>
    </main>
  );
}
