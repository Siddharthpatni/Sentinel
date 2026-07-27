"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useToast } from "@/components/toast";
import { HudPanel } from "@/components/HudPanel";

/* ================================================================
   Icons — hand-rolled Feather-style SVGs, matching the convention in
   app/traces/[id]/page.tsx (IconArrowLeft) rather than lucide-react.
   ================================================================ */

function IconShield() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2 4 5v6c0 5.5 3.4 9.7 8 11 4.6-1.3 8-5.5 8-11V5l-8-3Z" />
      <path d="m9 12 2 2 4-4" />
    </svg>
  );
}

function IconSearch() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="7" />
      <path d="m21 21-4.3-4.3" />
    </svg>
  );
}

function IconBell() {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  );
}

function IconX({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}

function IconCheckCircle() {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <path d="m9 12 2 2 4-4" />
    </svg>
  );
}

function IconXCircle() {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <line x1="15" y1="9" x2="9" y2="15" />
      <line x1="9" y1="9" x2="15" y2="15" />
    </svg>
  );
}

function IconSpinner() {
  return (
    <svg className="animate-spin" width="15" height="15" viewBox="0 0 24 24" fill="none">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
      <path className="opacity-90" d="M22 12a10 10 0 0 0-10-10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

/* ================================================================
   Mock data
   ================================================================ */

type DiffLineType = "context" | "removed" | "added";
interface UnifiedLine {
  type: DiffLineType;
  text: string;
}
interface SplitRow {
  left: { type: "context" | "removed"; text: string } | null;
  right: { type: "context" | "added"; text: string } | null;
}

const UNIFIED_DIFF: UnifiedLine[] = [
  { type: "context", text: "import psycopg2" },
  { type: "added", text: "import time" },
  { type: "removed", text: "def get_db_connection():" },
  { type: "added", text: "def get_db_connection(max_retries: int = 3):" },
  { type: "removed", text: "    conn = psycopg2.connect(DATABASE_URL)" },
  { type: "added", text: "    delay = 0.5" },
  { type: "added", text: "    for attempt in range(max_retries):" },
  { type: "added", text: "        try:" },
  { type: "added", text: "            return psycopg2.connect(DATABASE_URL)" },
  { type: "added", text: "        except OperationalError:" },
  { type: "added", text: "            if attempt == max_retries - 1:" },
  { type: "added", text: "                raise" },
  { type: "added", text: "            time.sleep(delay)" },
  { type: "added", text: "            delay *= 2" },
  { type: "removed", text: "    return conn" },
];

const SPLIT_DIFF: SplitRow[] = [
  { left: { type: "context", text: "import psycopg2" }, right: { type: "context", text: "import psycopg2" } },
  { left: null, right: { type: "added", text: "import time" } },
  { left: { type: "context", text: "" }, right: { type: "context", text: "" } },
  { left: { type: "removed", text: "def get_db_connection():" }, right: { type: "added", text: "def get_db_connection(max_retries: int = 3):" } },
  { left: { type: "removed", text: "    conn = psycopg2.connect(DATABASE_URL)" }, right: { type: "added", text: "    delay = 0.5" } },
  { left: { type: "removed", text: "    return conn" }, right: { type: "added", text: "    for attempt in range(max_retries):" } },
  { left: null, right: { type: "added", text: "        try:" } },
  { left: null, right: { type: "added", text: "            return psycopg2.connect(DATABASE_URL)" } },
  { left: null, right: { type: "added", text: "        except OperationalError:" } },
  { left: null, right: { type: "added", text: "            if attempt == max_retries - 1:" } },
  { left: null, right: { type: "added", text: "                raise" } },
  { left: null, right: { type: "added", text: "            time.sleep(delay)" } },
  { left: null, right: { type: "added", text: "            delay *= 2" } },
];

type StepStatus = "completed" | "running" | "approved" | "escalated";
interface Step {
  label: string;
  status: StepStatus;
}

const INITIAL_STEPS: Step[] = [
  { label: "Incident Detected", status: "completed" },
  { label: "Log Analysis", status: "completed" },
  { label: "Codebase RAG Query", status: "completed" },
  { label: "Fix Generation", status: "completed" },
  { label: "Security Scan", status: "completed" },
  { label: "Human Approval", status: "running" },
];

const SIDEBAR_LINKS = [
  { label: "Dashboard", href: "/" },
  { label: "Agent Activity", href: null },
  { label: "Incidents", href: null, badge: "1" },
  { label: "Settings", href: "/settings/keys" },
];

/* ================================================================
   Sidebar
   ================================================================ */

function Sidebar() {
  const router = useRouter();
  return (
    <aside
      className="hidden md:flex w-56 shrink-0 flex-col gap-1 px-3 py-5"
      style={{
        background: "var(--sentinel-surface)",
        borderRight: "1px solid color-mix(in srgb, var(--shield-cyan) 20%, var(--sentinel-border-subtle))",
      }}
    >
      <div className="flex items-center gap-2 px-2 mb-6">
        <span style={{ color: "var(--shield-cyan-light)", filter: "drop-shadow(0 0 4px var(--shield-cyan-glow))" }}>
          <IconShield />
        </span>
        <span
          className="font-semibold tracking-tight text-sm"
          style={{ color: "var(--sentinel-text-primary)", fontFamily: "var(--font-geist-mono)", letterSpacing: "0.02em" }}
        >
          SENTINEL // OPS
        </span>
      </div>
      {SIDEBAR_LINKS.map((link) => {
        const active = link.label === "Incidents";
        return (
          <button
            key={link.label}
            type="button"
            onClick={() => link.href && router.push(link.href)}
            className="flex items-center justify-between rounded-md px-3 py-2 text-sm text-left transition-colors"
            style={{
              background: active ? "var(--shield-cyan-dim)" : "transparent",
              color: active ? "var(--shield-cyan-light)" : "var(--sentinel-text-secondary)",
              fontWeight: active ? 600 : 500,
              cursor: link.href ? "pointer" : "default",
            }}
            onMouseEnter={(e) => {
              if (!active) e.currentTarget.style.background = "var(--sentinel-surface-hover)";
            }}
            onMouseLeave={(e) => {
              if (!active) e.currentTarget.style.background = "transparent";
            }}
          >
            {link.label}
            {link.badge && (
              <span className="badge badge-error" style={{ padding: "1px 7px", fontSize: "0.65rem" }}>
                {link.badge}
              </span>
            )}
          </button>
        );
      })}
    </aside>
  );
}

/* ================================================================
   Top Bar
   ================================================================ */

function TopBar() {
  return (
    <header
      className="flex items-center gap-4 px-6 py-3.5"
      style={{ borderBottom: "1px solid var(--sentinel-border-subtle)", background: "var(--sentinel-bg)" }}
    >
      <div className="relative flex-1 max-w-sm">
        <span className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--sentinel-text-faint)" }}>
          <IconSearch />
        </span>
        <input
          type="text"
          placeholder="Search incidents, traces, agents…"
          className="w-full rounded-md pl-9 pr-3 py-1.5 text-sm outline-none"
          style={{
            background: "var(--sentinel-surface)",
            border: "1px solid var(--sentinel-border)",
            color: "var(--sentinel-text-primary)",
          }}
        />
      </div>
      <div className="flex-1" />
      <button
        type="button"
        className="relative p-2 rounded-md"
        style={{ color: "var(--sentinel-text-secondary)" }}
      >
        <IconBell />
        <span
          className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full"
          style={{ background: "var(--sentinel-error)" }}
        />
      </button>
      <div className="flex items-center gap-2 pl-2" style={{ borderLeft: "1px solid var(--sentinel-border-subtle)" }}>
        <span
          className="flex items-center justify-center w-7 h-7 rounded-full text-xs font-semibold"
          style={{ background: "var(--shield-cyan)", color: "white" }}
        >
          JS
        </span>
        <span className="text-sm hidden sm:inline" style={{ color: "var(--sentinel-text-secondary)" }}>
          John Smith
        </span>
      </div>
    </header>
  );
}

/* ================================================================
   Diff Viewer
   ================================================================ */

function diffLineStyle(type: DiffLineType): React.CSSProperties {
  if (type === "added") return { background: "var(--sentinel-success-dim)", color: "var(--sentinel-success)" };
  if (type === "removed") return { background: "var(--sentinel-error-dim)", color: "var(--sentinel-error)" };
  return { color: "var(--sentinel-text-muted)" };
}

function DiffViewer() {
  const [mode, setMode] = useState<"split" | "unified">("split");

  return (
    <HudPanel padded={false} className="overflow-hidden">
      <div className="flex items-center justify-between px-2 py-2" style={{ borderBottom: "1px solid var(--sentinel-border-subtle)" }}>
        <span className="hud-label px-2">
          {mode === "split" ? "Base Version  ·  Proposed Fix" : "Unified Diff"}
        </span>
        <div className="flex gap-1">
          {(["split", "unified"] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMode(m)}
              className="text-xs px-2.5 py-1 rounded"
              style={{
                background: mode === m ? "var(--shield-cyan-dim)" : "transparent",
                color: mode === m ? "var(--shield-cyan-light)" : "var(--sentinel-text-muted)",
                fontWeight: 600,
              }}
            >
              {m === "split" ? "Split View" : "Unified View"}
            </button>
          ))}
        </div>
      </div>

      <div
        className="overflow-auto font-mono text-xs leading-relaxed"
        style={{ maxHeight: 420, fontFamily: "var(--font-geist-mono), monospace" }}
      >
        {mode === "split" ? (
          <div className="grid grid-cols-2">
            <div style={{ borderRight: "1px solid var(--sentinel-border-subtle)" }}>
              {SPLIT_DIFF.map((row, i) => (
                <div key={i} className="flex px-3 py-0.5 whitespace-pre" style={row.left ? diffLineStyle(row.left.type) : {}}>
                  <span className="w-6 shrink-0 text-right pr-3 select-none" style={{ color: "var(--sentinel-text-faint)" }}>
                    {row.left ? i + 1 : ""}
                  </span>
                  <span className="shrink-0 w-3 select-none">{row.left?.type === "removed" ? "-" : ""}</span>
                  {row.left?.text}
                </div>
              ))}
            </div>
            <div>
              {SPLIT_DIFF.map((row, i) => (
                <div key={i} className="flex px-3 py-0.5 whitespace-pre" style={row.right ? diffLineStyle(row.right.type) : {}}>
                  <span className="w-6 shrink-0 text-right pr-3 select-none" style={{ color: "var(--sentinel-text-faint)" }}>
                    {row.right ? i + 1 : ""}
                  </span>
                  <span className="shrink-0 w-3 select-none">{row.right?.type === "added" ? "+" : ""}</span>
                  {row.right?.text}
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div>
            {UNIFIED_DIFF.map((line, i) => (
              <div key={i} className="flex px-3 py-0.5 whitespace-pre" style={diffLineStyle(line.type)}>
                <span className="w-6 shrink-0 text-right pr-3 select-none" style={{ color: "var(--sentinel-text-faint)" }}>
                  {i + 1}
                </span>
                <span className="shrink-0 w-3 select-none">{line.type === "added" ? "+" : line.type === "removed" ? "-" : ""}</span>
                {line.text}
              </div>
            ))}
          </div>
        )}
      </div>
    </HudPanel>
  );
}

/* ================================================================
   Agent Workflow Status Stepper
   ================================================================ */

function StepBadge({ status }: { status: StepStatus }) {
  if (status === "completed") {
    return (
      <span className="badge badge-success" style={{ gap: 4 }}>
        <IconCheckCircle /> Completed
      </span>
    );
  }
  if (status === "approved") {
    return (
      <span className="badge badge-success" style={{ gap: 4 }}>
        <IconCheckCircle /> Approved
      </span>
    );
  }
  if (status === "escalated") {
    return (
      <span className="badge badge-error" style={{ gap: 4 }}>
        <IconXCircle /> Escalated to On-Call
      </span>
    );
  }
  return (
    <span
      className="badge"
      style={{
        gap: 4,
        background: "var(--shield-cyan-dim)",
        color: "var(--shield-cyan-light)",
        animation: "pulse-glow 1.8s ease-in-out infinite",
      }}
    >
      <IconSpinner /> Waiting for input
    </span>
  );
}

function WorkflowStepper({ steps }: { steps: Step[] }) {
  return (
    <HudPanel title="Agent Workflow Status">
      <ol className="space-y-3">
        {steps.map((step, i) => (
          <li key={step.label} className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <span
                className="flex items-center justify-center w-5 h-5 rounded-full text-[10px] font-bold shrink-0"
                style={{
                  background:
                    step.status === "completed" || step.status === "approved"
                      ? "var(--sentinel-success)"
                      : step.status === "escalated"
                        ? "var(--sentinel-error)"
                        : "var(--sentinel-surface-elevated)",
                  color: step.status === "running" ? "var(--sentinel-text-muted)" : "white",
                  border: step.status === "running" ? "1px solid var(--sentinel-border)" : "none",
                }}
              >
                {i + 1}
              </span>
              <span className="text-sm" style={{ color: "var(--sentinel-text-secondary)" }}>
                {step.label}
              </span>
            </div>
            <StepBadge status={step.status} />
          </li>
        ))}
      </ol>
    </HudPanel>
  );
}

/* ================================================================
   Agent Insights Metrics
   ================================================================ */

function MetricsCard() {
  return (
    <HudPanel title="Agent Insights">
      <div className="grid grid-cols-1 gap-3">
        <div className="stat-card">
          <span className="stat-label">Tokens used</span>
          <span className="stat-value text-lg">1,300</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Processing time</span>
          <span className="stat-value text-lg">3.0s</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Security risk score</span>
          <span className="badge badge-success mt-1">Low (Passed)</span>
        </div>
      </div>
    </HudPanel>
  );
}

/* ================================================================
   Page
   ================================================================ */

export default function IncidentPanelPage() {
  const router = useRouter();
  const toast = useToast();
  const [steps, setSteps] = useState<Step[]>(INITIAL_STEPS);
  const [deciding, setDeciding] = useState<"approve" | "reject" | null>(null);
  const [showRejectForm, setShowRejectForm] = useState(false);
  const [rejectComment, setRejectComment] = useState("");

  const humanStep = steps[steps.length - 1];
  const decided = humanStep.status === "approved" || humanStep.status === "escalated";

  function setHumanStatus(status: StepStatus) {
    setSteps((prev) => prev.map((s, i) => (i === prev.length - 1 ? { ...s, status } : s)));
  }

  function approve() {
    setDeciding("approve");
    setTimeout(() => {
      setHumanStatus("approved");
      setDeciding(null);
      toast.push("Fix successfully dispatched to deployment pipeline.", "success");
    }, 900);
  }

  function confirmReject() {
    setDeciding("reject");
    setTimeout(() => {
      setHumanStatus("escalated");
      setDeciding(null);
      setShowRejectForm(false);
      toast.push("Fix rejected — escalated to human on-call.", "error");
    }, 700);
  }

  return (
    <div className="flex h-screen" style={{ background: "var(--sentinel-bg)" }}>
      <Sidebar />
      <div className="flex flex-1 flex-col min-w-0">
        <TopBar />

        <main className="hud-grid-bg flex-1 overflow-auto p-6">
          <div className="hud-frame glass-panel-elevated p-0 max-w-[1400px] mx-auto overflow-hidden">
            <span className="hud-corner hud-corner-tl" />
            <span className="hud-corner hud-corner-tr" />
            <span className="hud-corner hud-corner-bl" />
            <span className="hud-corner hud-corner-br" />
            {/* Header */}
            <div
              className="flex items-start justify-between gap-4 px-6 py-4"
              style={{ borderBottom: "1px solid color-mix(in srgb, var(--shield-cyan) 20%, var(--sentinel-border-subtle))" }}
            >
              <div>
                <div className="hud-title mb-1.5">Live Diff Viewer</div>
                <h1 className="text-lg font-bold tracking-tight" style={{ color: "var(--sentinel-text-primary)" }}>
                  Incident Control Panel
                </h1>
                <p className="text-sm mt-1" style={{ color: "var(--sentinel-text-secondary)" }}>
                  Root Cause: Database connection retry logic bug. Generated fix adds robust
                  error handling and exponential backoff.
                </p>
              </div>
              <button
                type="button"
                onClick={() => router.push("/")}
                className="btn-ghost p-2"
                aria-label="Close incident panel"
              >
                <IconX />
              </button>
            </div>

            {/* Body */}
            <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-5 p-5">
              <div className="space-y-4">
                <DiffViewer />

                {/* Action bar */}
                <div className="glass-panel p-4">
                  {decided ? (
                    <div className="flex items-center gap-2 text-sm font-medium" style={{ color: humanStep.status === "approved" ? "var(--sentinel-success)" : "var(--sentinel-error)" }}>
                      {humanStep.status === "approved" ? <IconCheckCircle /> : <IconXCircle />}
                      {humanStep.status === "approved"
                        ? "Approved — fix dispatched to deployment pipeline."
                        : "Escalated to human on-call."}
                    </div>
                  ) : showRejectForm ? (
                    <div className="space-y-3">
                      <textarea
                        className="w-full rounded px-3 py-2 text-sm"
                        style={{ background: "var(--sentinel-surface)", border: "1px solid var(--sentinel-border)", color: "var(--sentinel-text-primary)" }}
                        rows={3}
                        placeholder="Why is this fix being rejected? (optional)"
                        value={rejectComment}
                        onChange={(e) => setRejectComment(e.target.value)}
                      />
                      <div className="flex gap-3">
                        <button type="button" className="btn-danger" disabled={deciding !== null} onClick={confirmReject}>
                          {deciding === "reject" ? <IconSpinner /> : <IconXCircle />}
                          {deciding === "reject" ? "Escalating…" : "Confirm Escalation"}
                        </button>
                        <button type="button" className="btn-ghost" onClick={() => setShowRejectForm(false)} disabled={deciding !== null}>
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex flex-wrap gap-3">
                      <button
                        type="button"
                        className="btn-success"
                        disabled={deciding !== null}
                        onClick={approve}
                        style={{ boxShadow: deciding === null ? "0 0 24px var(--sentinel-success-dim)" : undefined }}
                      >
                        {deciding === "approve" ? <IconSpinner /> : <IconCheckCircle />}
                        {deciding === "approve" ? "Deploying…" : "Approve & Deploy Fix"}
                      </button>
                      <button
                        type="button"
                        className="btn-danger"
                        disabled={deciding !== null}
                        onClick={() => setShowRejectForm(true)}
                      >
                        <IconXCircle />
                        Reject Fix & Escalation
                      </button>
                    </div>
                  )}
                </div>
              </div>

              <div className="space-y-4">
                <WorkflowStepper steps={steps} />
                <MetricsCard />
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
