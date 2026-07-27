"use client";

import { useEffect, useRef, useState } from "react";
import {
  decideTriage,
  fetchTriageExecution,
  triageWebSocketUrl,
  type TriageExecution,
  type TriagePatchFile,
} from "@/lib/api";
import { useToast } from "@/components/toast";
import { AgentGraph, type GraphStep } from "@/components/AgentGraph";
import { HudPanel } from "@/components/HudPanel";

/* ================================================================
   Live State Graph
   ================================================================ */

type StepKey = "diagnostic" | "planner" | "compliance" | "approval" | "execution";
type StepState = "pending" | "active" | "done" | "failed";

const STEPS: { key: StepKey; label: string }[] = [
  { key: "diagnostic", label: "Diagnostic" },
  { key: "planner", label: "Planner" },
  { key: "compliance", label: "Compliance Check" },
  { key: "approval", label: "Approval Gate" },
  { key: "execution", label: "Execution" },
];

function stepState(step: StepKey, execution: TriageExecution): StepState {
  const order: StepKey[] = ["diagnostic", "planner", "compliance", "approval", "execution"];
  const nodeIndex: Record<string, number> = {
    diagnostic: 0,
    planner: 1,
    compliance: 2,
    execution: 4,
    done: 5,
  };
  const stepIndex = order.indexOf(step);

  if (execution.status === "failed") {
    const failedAt = nodeIndex[execution.current_node] ?? 0;
    if (stepIndex < failedAt) return "done";
    if (stepIndex === failedAt) return "failed";
    return "pending";
  }

  // Approval gate is virtual — derive its state from status, not current_node.
  if (step === "approval") {
    if (execution.status === "paused_for_approval") return "active";
    if (execution.status === "rejected") return "failed";
    if (["approved", "completed"].includes(execution.status)) return "done";
    if (execution.current_node === "compliance") return "pending";
    return execution.diagnosis && execution.proposed_patch ? "pending" : "pending";
  }

  const currentIndex = nodeIndex[execution.current_node] ?? 0;
  if (step === "execution") {
    if (execution.status === "completed") return "done";
    if (execution.current_node === "execution") return "active";
    return "pending";
  }
  if (stepIndex < currentIndex) return "done";
  if (stepIndex === currentIndex) return execution.status === "running" ? "active" : "done";
  return "pending";
}

function StateGraph({ execution }: { execution: TriageExecution }) {
  const steps: GraphStep[] = STEPS.map((step) => ({
    key: step.key,
    label: step.label,
    state: stepState(step.key, execution),
  }));
  return <AgentGraph steps={steps} cacheHit={Boolean(execution.diagnosis?.cache_hit)} />;
}

/* ================================================================
   Diff Viewer
   ================================================================ */

function diffLineClass(line: string): string {
  if (line.startsWith("+++") || line.startsWith("---") || line.startsWith("@@")) {
    return "diff-line diff-line-hunk";
  }
  if (line.startsWith("+")) return "diff-line diff-line-add";
  if (line.startsWith("-")) return "diff-line diff-line-remove";
  return "diff-line diff-line-context";
}

function DiffFile({ file }: { file: TriagePatchFile }) {
  const lines = file.diff.split("\n");
  return (
    <div className="mb-4">
      <div
        className="text-xs font-mono px-3 py-1.5 rounded-t-lg"
        style={{
          background: "var(--sentinel-surface-elevated)",
          color: "var(--sentinel-text-secondary)",
          border: "1px solid var(--sentinel-border-subtle)",
          borderBottom: "none",
        }}
      >
        {file.path}
      </div>
      <div className="diff-viewer" style={{ borderTopLeftRadius: 0, borderTopRightRadius: 0 }}>
        {lines.map((line, i) => (
          <div key={i} className={diffLineClass(line)}>
            {line || " "}
          </div>
        ))}
      </div>
    </div>
  );
}

/* ================================================================
   Compliance Badge
   ================================================================ */

function riskBadgeClass(tier: string | null): string {
  if (tier === "high" || tier === "unacceptable") return "badge-error";
  if (tier === "medium" || tier === "limited") return "badge-warning";
  if (tier === "low" || tier === "minimal") return "badge-success";
  return "";
}

function ComplianceBadge({ execution }: { execution: TriageExecution }) {
  return (
    <HudPanel title="Compliance & Risk Gate">
      <div className="flex flex-wrap items-center gap-2 mb-3">
        {execution.patch_risk_tier && (
          <span className={`badge ${riskBadgeClass(execution.patch_risk_tier)}`}>
            patch risk: {execution.patch_risk_tier}
          </span>
        )}
        {execution.trace_risk_tier && (
          <span className={`badge ${riskBadgeClass(execution.trace_risk_tier)}`}>
            EU AI Act: {execution.trace_risk_tier}
          </span>
        )}
        {execution.pr_url && (
          <a
            href={execution.pr_url}
            target="_blank"
            rel="noreferrer"
            className="badge badge-success"
          >
            PR opened ↗
          </a>
        )}
      </div>
      {execution.compliance_reasons.length > 0 && (
        <ul className="text-xs space-y-1" style={{ color: "var(--sentinel-text-muted)" }}>
          {execution.compliance_reasons.map((reason, i) => (
            <li key={i}>· {reason}</li>
          ))}
        </ul>
      )}
    </HudPanel>
  );
}

/* ================================================================
   Action Bar
   ================================================================ */

function ActionBar({
  execution,
  onUpdate,
}: {
  execution: TriageExecution;
  onUpdate: (e: TriageExecution) => void;
}) {
  const toast = useToast();
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState<"approve" | "reject" | null>(null);

  if (execution.status !== "paused_for_approval") return null;

  async function decide(action: "approve" | "reject") {
    setBusy(action);
    try {
      const updated = await decideTriage(execution.id, action, comment || undefined);
      onUpdate(updated);
      toast.push(
        action === "approve" ? "Approved — executing fix" : "Rejected",
        action === "approve" ? "success" : "error",
      );
    } catch (e) {
      toast.push(String(e), "error");
    } finally {
      setBusy(null);
    }
  }

  return (
    <HudPanel title="Human Approval Required" elevated>
      <textarea
        className="w-full bg-surface border border-default rounded px-3 py-2 text-sm text-fg mb-3"
        placeholder="Optional comment…"
        rows={2}
        value={comment}
        onChange={(e) => setComment(e.target.value)}
      />
      <div className="flex gap-3">
        <button
          type="button"
          className="btn-success"
          disabled={busy !== null}
          onClick={() => decide("approve")}
        >
          {busy === "approve" ? "Approving…" : "Approve & Execute Fix"}
        </button>
        <button
          type="button"
          className="btn-danger"
          disabled={busy !== null}
          onClick={() => decide("reject")}
        >
          {busy === "reject" ? "Rejecting…" : "Reject / Override"}
        </button>
      </div>
    </HudPanel>
  );
}

/* ================================================================
   Control Room
   ================================================================ */

export function ControlRoom({
  execution,
  onUpdate,
}: {
  execution: TriageExecution;
  onUpdate: (e: TriageExecution) => void;
}) {
  const [events, setEvents] = useState<Record<string, unknown>[]>([]);
  const executionRef = useRef(execution);

  useEffect(() => {
    executionRef.current = execution;
  }, [execution]);

  useEffect(() => {
    if (["completed", "rejected", "failed"].includes(execution.status)) return;

    const ws = new WebSocket(triageWebSocketUrl(execution.id));
    ws.onmessage = (msg) => {
      try {
        const event = JSON.parse(msg.data) as Record<string, unknown>;
        setEvents((prev) => [...prev.slice(-19), event]);
        // Node transitions mutate server state beyond what the event carries
        // (diagnosis/patch/risk) — refetch the canonical record.
        fetchTriageExecution(executionRef.current.id).then(onUpdate).catch(() => {});
      } catch {
        /* ignore malformed frames */
      }
    };
    return () => ws.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [execution.id, execution.status]);

  return (
    <div className="space-y-6">
      <HudPanel title="Agent Execution Graph" elevated className="overflow-x-auto">
        <StateGraph execution={execution} />
      </HudPanel>

      {execution.diagnosis && (
        <HudPanel title="Root Cause Diagnosis">
          <p className="text-sm mb-2" style={{ color: "var(--sentinel-text-secondary)" }}>
            {execution.diagnosis.root_cause}
          </p>
          {execution.diagnosis.confidence !== null && (
            <p className="text-xs" style={{ color: "var(--sentinel-text-muted)" }}>
              confidence: {(execution.diagnosis.confidence * 100).toFixed(0)}%
            </p>
          )}
          {execution.diagnosis.suspected_files.length > 0 && (
            <p className="text-xs mt-1" style={{ color: "var(--sentinel-text-muted)" }}>
              suspected files: {execution.diagnosis.suspected_files.join(", ")}
            </p>
          )}
        </HudPanel>
      )}

      {execution.proposed_patch && execution.proposed_patch.files.length > 0 && (
        <HudPanel title="Proposed Fix">
          <p className="text-sm mb-4" style={{ color: "var(--sentinel-text-secondary)" }}>
            {execution.proposed_patch.summary}
          </p>
          {execution.proposed_patch.files.map((f, i) => (
            <DiffFile key={i} file={f} />
          ))}
        </HudPanel>
      )}

      <ComplianceBadge execution={execution} />
      <ActionBar execution={execution} onUpdate={onUpdate} />

      {execution.error_message && (
        <div
          className="p-4 rounded-lg"
          style={{ background: "var(--sentinel-error-dim)", border: "1px solid rgba(248, 113, 113, 0.2)" }}
        >
          <p className="text-sm font-semibold mb-1" style={{ color: "var(--sentinel-error)" }}>
            Error
          </p>
          <p className="text-sm font-mono" style={{ color: "var(--sentinel-text-secondary)" }}>
            {execution.error_message}
          </p>
        </div>
      )}

      {events.length > 0 && (
        <HudPanel title="Live Activity Feed">
          <div className="json-viewer text-xs" style={{ maxHeight: 200 }}>
            {events.map((e, i) => (
              <div key={i}>
                <span style={{ color: "var(--shield-cyan-light)" }}>&gt;</span>{" "}
                {String(e.timestamp)} · node={String(e.node)} · status={String(e.status)}
                {e.latency_ms !== undefined ? ` · ${e.latency_ms}ms` : ""}
                {e.tokens_used !== undefined ? ` · ${e.tokens_used} tok` : ""}
              </div>
            ))}
          </div>
        </HudPanel>
      )}
    </div>
  );
}
