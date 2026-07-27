"use client";

/* ================================================================
   AgentGraph — hexagonal node-DAG view of a triage execution.

   Presentational only: ControlRoom.tsx owns node-state derivation
   (stepState) and passes it in, matching the split already used for
   ComplianceBadge/ActionBar in that file.
   ================================================================ */

export type NodeState = "pending" | "active" | "done" | "failed";

export interface GraphStep {
  key: string;
  label: string;
  state: NodeState;
}

function IconCheck() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="m5 12 5 5 9-9" />
    </svg>
  );
}

function IconX() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 6 6 18M6 6l12 12" />
    </svg>
  );
}

function IconBolt() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M13 2 4 14h6l-1 8 9-12h-6l1-8Z" />
    </svg>
  );
}

function IconDot() {
  return (
    <svg width="10" height="10" viewBox="0 0 10 10" fill="currentColor">
      <circle cx="5" cy="5" r="5" />
    </svg>
  );
}

function NodeIcon({ state }: { state: NodeState | "skipped" }) {
  if (state === "done") return <IconCheck />;
  if (state === "failed") return <IconX />;
  if (state === "active") return <IconDot />;
  return <IconDot />;
}

function HexNode({ step, skipped }: { step: GraphStep; skipped?: boolean }) {
  const cls = skipped ? "skipped" : step.state;
  return (
    <div className="agent-node-wrap">
      <div className={`agent-node is-${cls}`}>
        <div className="agent-node-inner">
          <NodeIcon state={skipped ? "pending" : step.state} />
        </div>
      </div>
      <span className="agent-node-label">
        {step.label}
        {step.state === "active" && !skipped && (
          <>
            <br />
            <span style={{ color: "var(--shield-cyan-light)" }}>RUNNING…</span>
          </>
        )}
        {skipped && (
          <>
            <br />
            <span style={{ color: "var(--sentinel-text-faint)" }}>SKIPPED</span>
          </>
        )}
      </span>
    </div>
  );
}

function Edge({ state }: { state: "pending" | "active" | "done" }) {
  return <div className={`agent-edge is-${state}`} />;
}

/** Edge state derived from the two nodes it connects. */
function edgeState(from: NodeState, to: NodeState): "pending" | "active" | "done" {
  if (from === "done" || from === "failed") {
    if (to === "pending") return "pending";
    return to === "active" ? "active" : "done";
  }
  return "pending";
}

export function AgentGraph({ steps, cacheHit }: { steps: GraphStep[]; cacheHit: boolean }) {
  const trigger: GraphStep = { key: "trigger", label: "Trace\nIngested", state: "done" };
  const all = [trigger, ...steps];

  return (
    <div className="hud-grid-bg rounded-xl p-5">
      {cacheHit && (
        <div className="mb-4">
          <span className="agent-bypass-chip">
            <IconBolt /> Cache hit — diagnostic + planner skipped
          </span>
        </div>
      )}
      <div className="agent-graph">
        {all.map((step, i) => {
          const isSkippedNode = cacheHit && (step.key === "diagnostic" || step.key === "planner");
          const prev = all[i - 1];
          return (
            <div key={step.key} className="flex items-start">
              {i > 0 && prev && (
                <Edge
                  state={
                    isSkippedNode || (cacheHit && step.key === "compliance")
                      ? cacheHit
                        ? "done"
                        : "pending"
                      : edgeState(prev.state, step.state)
                  }
                />
              )}
              <HexNode step={step} skipped={isSkippedNode} />
            </div>
          );
        })}
      </div>
    </div>
  );
}
