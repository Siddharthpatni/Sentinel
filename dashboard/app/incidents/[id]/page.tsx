"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { fetchTriageExecution, type TriageExecution } from "@/lib/api";
import { ControlRoom } from "@/components/ControlRoom";
import { IncidentStatsPanel } from "@/components/IncidentStatsPanel";

const STATUS_BADGE: Record<string, string> = {
  running: "badge-openai",
  paused_for_approval: "badge-warning",
  approved: "badge-openai",
  rejected: "badge-error",
  completed: "badge-success",
  failed: "badge-error",
};

function IconArrowLeft() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <line x1="19" y1="12" x2="5" y2="12" />
      <polyline points="12 19 5 12 12 5" />
    </svg>
  );
}

export default function IncidentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const [execution, setExecution] = useState<TriageExecution | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const id = params.id as string;
    fetchTriageExecution(id)
      .then(setExecution)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [params.id]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: "var(--sentinel-bg)" }}>
        <div className="space-y-4 w-full max-w-3xl px-6">
          <div className="skeleton h-8 w-64" />
          <div className="skeleton h-4 w-96" />
          <div className="skeleton h-48 w-full" />
        </div>
      </div>
    );
  }

  if (error || !execution) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: "var(--sentinel-bg)" }}>
        <div className="text-center">
          <p className="text-lg font-semibold mb-2" style={{ color: "var(--sentinel-error)" }}>
            Incident not found
          </p>
          <p className="text-sm mb-6" style={{ color: "var(--sentinel-text-muted)" }}>
            {error || "The requested triage execution does not exist."}
          </p>
          <button className="btn-primary" onClick={() => router.push("/incidents")}>
            Back to Incidents
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col" style={{ background: "var(--sentinel-bg)" }}>
      <header
        className="sticky top-0 z-50 flex items-center gap-4 px-6 py-4"
        style={{
          background: "rgba(10, 10, 15, 0.85)",
          backdropFilter: "blur(12px)",
          borderBottom: "1px solid var(--sentinel-border-subtle)",
        }}
      >
        <button className="btn-ghost" onClick={() => router.push("/incidents")}>
          <IconArrowLeft />
          Back
        </button>
        <div className="flex-1" />
        <span className={`badge ${STATUS_BADGE[execution.status] ?? ""}`}>{execution.status}</span>
      </header>

      <main className="flex-1 px-6 py-8 max-w-[1440px] w-full mx-auto">
        <div className="mb-8 animate-fade-in">
          <h1
            className="text-2xl font-bold mb-2 tracking-tight"
            style={{ color: "var(--sentinel-text-primary)", fontFamily: "var(--font-geist-mono)" }}
          >
            Incident {execution.id.slice(0, 8)}
          </h1>
          <p className="text-sm" style={{ color: "var(--sentinel-text-muted)" }}>
            trace:{" "}
            <a
              className="font-mono text-xs px-2 py-0.5 rounded"
              style={{ background: "var(--sentinel-surface)", color: "var(--sentinel-text-secondary)" }}
              href={`/traces/${execution.trace_id}`}
            >
              {execution.trace_id}
            </a>
          </p>
        </div>

        <div className="animate-slide-up grid grid-cols-1 xl:grid-cols-[1fr_320px] gap-6 items-start">
          <ControlRoom execution={execution} onUpdate={setExecution} />
          <IncidentStatsPanel />
        </div>
      </main>
    </div>
  );
}
