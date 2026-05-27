"""Eval runner — executes a parsed suite end-to-end through the gateway.

For each case:
  1. POST the case input to the gateway (so the call is itself traced).
  2. Time the call and parse the response.
  3. Run each assertion against the response/latency/cost.
  4. Persist an EvalCase row tying assertions to the trace_id (when discoverable).

The runner is intentionally synchronous (uses httpx.Client) because it is
invoked from a Celery worker. It never raises out — any per-case failure is
recorded as ``passed=False`` with an assertion_log entry describing the error.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import asdict
from datetime import UTC, datetime

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Eval, EvalCase, EvalRun, Trace
from app.evals.assertions import AssertionResult, CallResult, run_assertion
from app.evals.parser import EvalSuiteSpec, parse_suite_yaml
from app.tracing.cost import compute_cost

logger = logging.getLogger(__name__)

GATEWAY_INTERNAL_URL = "http://gateway:8000"


def _build_request(suite: EvalSuiteSpec, case_input: dict) -> dict:
    """Merge the suite's target model into the case input."""
    body = dict(case_input)
    body.setdefault("model", suite.target.model)
    return body


def _call_gateway(
    endpoint: str,
    body: dict,
    api_key: str,
    timeout: float = 60.0,
) -> tuple[dict, int, int]:
    """POST to the gateway. Returns (response_json, latency_ms, status_code)."""
    url = f"{GATEWAY_INTERNAL_URL}{endpoint}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    start = time.monotonic()
    resp = httpx.post(url, json=body, headers=headers, timeout=timeout)
    latency_ms = int((time.monotonic() - start) * 1000)
    try:
        data = resp.json()
    except Exception:  # noqa: BLE001
        data = {"_raw": resp.text}
    return data, latency_ms, resp.status_code


def _compute_call_cost(response: dict) -> float:
    """Approximate the cost from the response usage block."""
    try:
        usage = response.get("usage") or {}
        model = response.get("model", "")
        prompt = int(usage.get("prompt_tokens", 0) or 0)
        completion = int(usage.get("completion_tokens", 0) or 0)
        return float(compute_cost(model, prompt, completion).total_cost_usd)
    except Exception:  # noqa: BLE001
        return 0.0


def _find_trace_id(session: Session, response: dict, project_id: uuid.UUID) -> uuid.UUID | None:
    """Best-effort: find the most recent trace whose response_body matches the call's id."""
    try:
        rid = response.get("id")
        if not rid:
            return None
        from sqlalchemy import select

        stmt = (
            select(Trace.id)
            .where(Trace.project_id == project_id)
            .order_by(Trace.created_at.desc())
            .limit(20)
        )
        for (trace_id,) in session.execute(stmt).all():
            row = session.get(Trace, trace_id)
            if row and isinstance(row.response_body, dict) and row.response_body.get("id") == rid:
                return trace_id
    except Exception as exc:  # noqa: BLE001
        logger.debug("trace id lookup failed: %s", exc)
    return None


def run_suite(
    session: Session,
    eval_row: Eval,
    *,
    triggered_by: str = "manual",
    git_sha: str | None = None,
    api_key: str | None = None,
) -> EvalRun:
    """Parse the suite, execute every case, persist EvalRun + EvalCase rows.

    Returns the committed :class:`EvalRun`. Never raises — runtime errors are
    encoded as failed cases.
    """
    suite = parse_suite_yaml(eval_row.yaml_source)
    api_key = api_key or settings.default_project_api_key

    run = EvalRun(
        id=uuid.uuid4(),
        eval_id=eval_row.id,
        started_at=datetime.now(UTC),
        total=len(suite.cases),
        passed=0,
        failed=0,
        triggered_by=triggered_by,
        git_sha=git_sha,
    )
    session.add(run)
    session.flush()

    for case in suite.cases:
        body = _build_request(suite, case.input)
        try:
            response, latency_ms, status_code = _call_gateway(
                suite.target.endpoint, body, api_key
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("eval case %s: gateway call failed: %s", case.name, exc)
            session.add(EvalCase(
                id=uuid.uuid4(),
                run_id=run.id,
                case_name=case.name,
                input=body,
                expected=None,
                actual=None,
                passed=False,
                assertion_log=[{"type": "transport", "passed": False, "detail": str(exc)}],
                trace_id=None,
            ))
            run.failed += 1
            continue

        cost_usd = _compute_call_cost(response)
        call = CallResult(response=response, latency_ms=latency_ms, cost_usd=cost_usd)

        results: list[AssertionResult] = []
        all_passed = status_code < 400
        if not all_passed:
            results.append(
                AssertionResult(
                    type="http_status",
                    passed=False,
                    detail=f"upstream returned {status_code}",
                )
            )
        for assertion in case.assertions:
            res = run_assertion(assertion, call)
            results.append(res)
            if not res.passed:
                all_passed = False

        trace_id = _find_trace_id(session, response, eval_row.project_id)
        session.add(EvalCase(
            id=uuid.uuid4(),
            run_id=run.id,
            case_name=case.name,
            input=body,
            expected=None,
            actual=response,
            passed=all_passed,
            assertion_log=[asdict(r) for r in results],
            trace_id=trace_id,
        ))
        if all_passed:
            run.passed += 1
        else:
            run.failed += 1

    run.finished_at = datetime.now(UTC)
    session.commit()
    session.refresh(run)
    return run
