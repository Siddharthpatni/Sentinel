"""Autonomous incident-triage state machine.

Each node is a Celery task, chained the same way persist_trace_task chains
into evaluate_trace (app/workers/persist_trace.py): a node writes its
output to the TriageExecution row, commits, publishes a WebSocket-bound
event over Redis pub/sub, and enqueues the next node.

Graph:
    DiagnosticNode -> RemediationPlannerNode -> ComplianceGuardrailNode
        -> [HumanApprovalInterrupt: pause] -> ExecutionNode

HumanApprovalInterrupt isn't a separate task — it's the branch at the end
of run_compliance_node. Unless the patch is trivially safe (low risk, no
files touched), the chain stops with status="paused_for_approval" and
waits for POST /api/v1/triage/{id}/approve to enqueue run_execution_node.

LLM calls for the diagnostic/planner nodes self-call Sentinel's own gateway
(GATEWAY_INTERNAL_URL), tagged `_sentinel.is_agent` / `X-Sentinel-Agent`, the
same trick app/workers/evaluate_trace.py uses for judge calls — the call is
itself traced, but excluded from triggering triage-on-triage recursion.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx
import redis

from app.agents.cache_registry import get_cache_registry
from app.agents.github import github_configured, open_remediation_pr
from app.agents.prompts import (
    FileChange,
    parse_diagnosis_response,
    parse_remediation_response,
    render_diagnostic_prompt,
    render_remediation_prompt,
)
from app.agents.rag import retrieve_relevant_chunks
from app.agents.risk import assess_patch_risk
from app.audit.ledger import append_for_triage_decision
from app.config import settings
from app.db.models import Trace, TriageApproval, TriageExecution
from app.db.session import get_sync_session
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

AGENT_HEADER = "X-Sentinel-Agent"
GATEWAY_INTERNAL_URL = "http://gateway:8000/v1/chat/completions"
PATCH_ARTIFACT_ROOT = Path(__file__).resolve().parents[3] / ".sentinel" / "patches"


def _redis_client() -> redis.Redis[bytes]:
    return redis.Redis.from_url(settings.redis_url)


def _publish_event(execution_id: str, **fields: object) -> None:
    """Best-effort publish to the WS bridge channel — never raises."""
    event = {"execution_id": execution_id, "timestamp": datetime.now(UTC).isoformat(), **fields}
    try:
        _redis_client().publish(f"triage:{execution_id}", json.dumps(event, default=str))
    except Exception as exc:
        logger.warning("Failed to publish triage event for %s: %s", execution_id, exc)


def _call_agent_llm(prompt: str) -> tuple[str, int, int]:
    """Self-call the gateway's own chat endpoint.

    Returns (content, latency_ms, total_tokens) — the call is itself traced
    by the gateway, so token usage comes straight back on the response body
    like any other chat completion.
    """
    request_body = {
        "model": settings.triage_llm_model,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
        "_sentinel": {"is_agent": True},
    }
    headers = {
        "Authorization": f"Bearer {settings.default_project_api_key}",
        "Content-Type": "application/json",
        AGENT_HEADER: "1",
    }
    start = time.monotonic()
    resp = httpx.post(GATEWAY_INTERNAL_URL, json=request_body, headers=headers, timeout=90.0)
    latency_ms = int((time.monotonic() - start) * 1000)
    body = resp.json()
    try:
        content = body["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        content = json.dumps(body)
    total_tokens = int((body.get("usage") or {}).get("total_tokens", 0) or 0)
    return content, latency_ms, total_tokens


def _incident_signature(trace: Trace) -> str:
    """Stable text signature used as the cache registry's key/embedding input.

    Deliberately narrow (provider/model/status/error only, not the full
    request/response bodies) so recurring instances of the same underlying
    bug hash and embed the same way instead of fragmenting the cache
    per-request.
    """
    return f"{trace.provider}/{trace.model} status={trace.status_code} error={trace.error_message or ''}"


def start_triage(session, trace: Trace) -> TriageExecution:  # type: ignore[no-untyped-def]
    """Create a TriageExecution for `trace` and enqueue the first node. Caller commits.

    Checks the local cache registry first (app/agents/cache_registry.py) —
    on a hit, the stored diagnosis + patch are replayed directly onto the
    execution and it jumps straight to the compliance node, skipping both
    LLM calls. The compliance gate itself always re-runs: it's a cheap,
    deterministic rule check (app/agents/risk.py), not a model call.
    """
    execution = TriageExecution(project_id=trace.project_id, trace_id=trace.id)
    session.add(execution)
    session.flush()

    cached = None
    if settings.sentinel_cache_enabled:
        try:
            cached = get_cache_registry().lookup(_incident_signature(trace))
        except Exception:
            logger.exception("Cache lookup failed for execution %s", execution.id)

    if cached is not None:
        resolution, tokens_saved = cached
        execution.diagnosis = {**resolution["diagnosis"], "cache_hit": True}
        execution.proposed_patch = resolution["proposed_patch"]
        execution.current_node = "compliance"
        session.flush()
        _publish_event(str(execution.id), node="cache", status="hit", tokens_saved=tokens_saved)
        run_compliance_node.delay(str(execution.id))
    else:
        run_diagnostic_node.delay(str(execution.id))
    return execution


def _mark_failed(session, execution_id: str, message: str) -> None:  # type: ignore[no-untyped-def]
    execution = session.get(TriageExecution, uuid.UUID(execution_id))
    if execution is not None:
        execution.status = "failed"
        execution.error_message = message
        session.commit()


@celery_app.task  # type: ignore[misc]
def log_triage_decision(execution_id: str, approval_id: str) -> None:
    """Chain a human decision into the hash-chained audit ledger.

    Runs as its own sync-session task (rather than inline in the async
    /approve route) so the ledger's sequence/prev_hash bookkeeping only
    ever happens from the sync Celery/session world it already lives in
    (see app/audit/ledger.py, otherwise only ever called from
    persist_trace_task) — one implementation of the hash chain, not two.
    """
    session = get_sync_session()
    try:
        execution = session.get(TriageExecution, uuid.UUID(execution_id))
        approval = session.get(TriageApproval, uuid.UUID(approval_id))
        if execution is not None and approval is not None:
            append_for_triage_decision(session, execution, approval)
            session.commit()
    except Exception:
        session.rollback()
        logger.exception(
            "log_triage_decision failed for execution=%s approval=%s",
            execution_id,
            approval_id,
        )
    finally:
        session.close()


@celery_app.task  # type: ignore[misc]
def run_diagnostic_node(execution_id: str) -> None:
    session = get_sync_session()
    try:
        execution = session.get(TriageExecution, uuid.UUID(execution_id))
        if execution is None:
            return
        trace = session.get(Trace, execution.trace_id)
        if trace is None:
            _mark_failed(session, execution_id, "originating trace not found")
            return

        query_text = f"{trace.provider}/{trace.model} error: {trace.error_message or ''}"
        try:
            chunks = retrieve_relevant_chunks(session, query_text, k=8)
        except Exception as exc:
            logger.warning("RAG retrieval failed for %s: %s", execution_id, exc)
            chunks = []
        chunk_dicts = [
            {
                "file_path": c.file_path,
                "start_line": c.start_line,
                "end_line": c.end_line,
                "content": c.content,
            }
            for c in chunks
        ]

        prompt = render_diagnostic_prompt(
            provider=trace.provider,
            model=trace.model,
            error_message=trace.error_message,
            request_body=trace.request_body,
            response_body=trace.response_body,
            chunks=chunk_dicts,
        )
        content, latency_ms, tokens_used = _call_agent_llm(prompt)
        diagnosis = parse_diagnosis_response(content)

        execution.diagnosis = {
            "root_cause": diagnosis.root_cause,
            "confidence": diagnosis.confidence,
            "suspected_files": diagnosis.suspected_files,
            "retrieved_chunks": chunk_dicts,
        }
        execution.current_node = "planner"
        session.commit()
        _publish_event(
            execution_id,
            node="diagnostic",
            status="completed",
            latency_ms=latency_ms,
            tokens_used=tokens_used,
        )
        run_planner_node.delay(execution_id)
    except Exception as exc:
        session.rollback()
        logger.exception("run_diagnostic_node failed for %s", execution_id)
        _mark_failed(session, execution_id, str(exc))
        _publish_event(execution_id, node="diagnostic", status="failed", error=str(exc))
    finally:
        session.close()


@celery_app.task  # type: ignore[misc]
def run_planner_node(execution_id: str) -> None:
    session = get_sync_session()
    try:
        execution = session.get(TriageExecution, uuid.UUID(execution_id))
        if execution is None or execution.diagnosis is None:
            return

        prompt = render_remediation_prompt(execution.diagnosis)
        content, latency_ms, tokens_used = _call_agent_llm(prompt)
        remediation = parse_remediation_response(content)

        execution.proposed_patch = {
            "summary": remediation.summary,
            "patch_kind": remediation.patch_kind,
            "files": [{"path": f.path, "diff": f.diff} for f in remediation.files],
        }
        execution.current_node = "compliance"
        session.commit()
        _publish_event(
            execution_id,
            node="planner",
            status="completed",
            latency_ms=latency_ms,
            tokens_used=tokens_used,
        )
        run_compliance_node.delay(execution_id)
    except Exception as exc:
        session.rollback()
        logger.exception("run_planner_node failed for %s", execution_id)
        _mark_failed(session, execution_id, str(exc))
        _publish_event(execution_id, node="planner", status="failed", error=str(exc))
    finally:
        session.close()


@celery_app.task  # type: ignore[misc]
def run_compliance_node(execution_id: str) -> None:
    session = get_sync_session()
    try:
        execution = session.get(TriageExecution, uuid.UUID(execution_id))
        if execution is None or execution.proposed_patch is None:
            return

        files = [
            FileChange(path=f["path"], diff=f["diff"])
            for f in execution.proposed_patch.get("files", [])
        ]
        patch_kind = execution.proposed_patch.get("patch_kind", "none")
        tier, reasons = assess_patch_risk(files, patch_kind)

        execution.patch_risk_tier = tier
        execution.compliance_reasons = reasons
        session.commit()
        _publish_event(execution_id, node="compliance", status="completed", patch_risk_tier=tier)

        if settings.sentinel_cache_enabled and not (execution.diagnosis or {}).get("cache_hit"):
            trace = session.get(Trace, execution.trace_id)
            if trace is not None:
                try:
                    get_cache_registry().store(
                        _incident_signature(trace),
                        {"diagnosis": execution.diagnosis, "proposed_patch": execution.proposed_patch},
                    )
                except Exception:
                    logger.exception("Cache store failed for execution %s", execution_id)

        auto_continue = settings.triage_auto_approve_low_risk and tier == "low" and not files
        if auto_continue:
            execution.status = "approved"
            execution.current_node = "execution"
            session.commit()
            _publish_event(execution_id, node="approval", status="auto_approved")
            run_execution_node.delay(execution_id)
        else:
            execution.status = "paused_for_approval"
            session.commit()
            _publish_event(execution_id, node="approval", status="paused_for_approval")
    except Exception as exc:
        session.rollback()
        logger.exception("run_compliance_node failed for %s", execution_id)
        _mark_failed(session, execution_id, str(exc))
        _publish_event(execution_id, node="compliance", status="failed", error=str(exc))
    finally:
        session.close()


@celery_app.task  # type: ignore[misc]
def run_execution_node(execution_id: str) -> None:
    session = get_sync_session()
    try:
        execution = session.get(TriageExecution, uuid.UUID(execution_id))
        if execution is None or execution.proposed_patch is None:
            return

        files = [
            FileChange(path=f["path"], diff=f["diff"])
            for f in execution.proposed_patch.get("files", [])
        ]
        summary = execution.proposed_patch.get("summary", "")
        patch_kind = execution.proposed_patch.get("patch_kind", "none")

        if files and github_configured():
            execution.pr_url = open_remediation_pr(
                execution_id=execution_id, summary=summary, patch_kind=patch_kind, files=files
            )
        elif files:
            _write_patch_artifact(execution_id, files)

        execution.status = "completed"
        execution.current_node = "done"
        session.commit()
        _publish_event(execution_id, node="execution", status="completed", pr_url=execution.pr_url)
    except Exception as exc:
        session.rollback()
        logger.exception("run_execution_node failed for %s", execution_id)
        _mark_failed(session, execution_id, str(exc))
        _publish_event(execution_id, node="execution", status="failed", error=str(exc))
    finally:
        session.close()


def _write_patch_artifact(execution_id: str, files: list[FileChange]) -> None:
    out_dir = PATCH_ARTIFACT_ROOT / execution_id
    out_dir.mkdir(parents=True, exist_ok=True)
    for file in files:
        safe_name = file.path.replace("/", "__") + ".diff"
        (out_dir / safe_name).write_text(file.diff, encoding="utf-8")
