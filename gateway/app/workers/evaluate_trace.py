"""Verification orchestrator — Celery task chained after persist_trace.

Reads matching enabled rules for the trace's project, applies JSONPath
matching + sample-rate dice roll, calls the judge model through Sentinel's
own gateway (so the judge call is itself traced), parses the structured
verdict, and writes a `verifications` row.

Important constraints from the Phase 2 spec:
- Judging is async and non-blocking — the original caller never waits.
- Never verify a verification: judge calls carry ``X-Sentinel-Judge: 1`` and
  the orchestrator skips traces that already carry that marker. The marker
  is recorded on the request_body under ``_sentinel.is_judge`` so the
  worker (which sees only the serialized payload) can detect it.
- Failure to verify is never an error to the primary caller. We log it and
  store a ``verdict="error"`` row.
"""

from __future__ import annotations

import logging
import random
import uuid
from datetime import UTC, datetime

import httpx
from jsonpath_ng.ext import parse as jsonpath_parse

from app.config import settings
from app.db.models import Trace, Verification, VerificationRule
from app.db.session import get_sync_session
from app.verification.judges import parse_judge_response, render_judge_prompt
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

JUDGE_HEADER = "X-Sentinel-Judge"
GATEWAY_INTERNAL_URL = "http://gateway:8000/v1/chat/completions"


def _matches(rule: VerificationRule, request_body: dict) -> bool:
    try:
        expr = jsonpath_parse(rule.match_jsonpath)
    except Exception:  # noqa: BLE001
        logger.warning("Invalid JSONPath on rule %s: %r", rule.id, rule.match_jsonpath)
        return False
    return bool(expr.find(request_body))


def _sampled(rule: VerificationRule) -> bool:
    rate = float(rule.sample_rate or 0.0)
    if rate <= 0.0:
        return False
    if rate >= 1.0:
        return True
    return random.random() < rate


@celery_app.task(bind=True, max_retries=2, default_retry_delay=10)  # type: ignore[misc]
def evaluate_trace(self, trace_id: str) -> dict:  # type: ignore[no-untyped-def]
    """Evaluate enabled verification rules against a freshly persisted trace.

    Returns a small summary dict for testability.
    """
    session = get_sync_session()
    summary = {"trace_id": trace_id, "evaluated": 0, "verdicts": []}
    try:
        trace = session.get(Trace, uuid.UUID(trace_id))
        if trace is None:
            logger.warning("evaluate_trace: trace %s missing", trace_id)
            return summary

        request_body = trace.request_body or {}
        if isinstance(request_body, dict) and request_body.get("_sentinel", {}).get("is_judge"):
            logger.debug("evaluate_trace: skipping judge trace %s", trace_id)
            return summary

        rules = (
            session.query(VerificationRule)
            .filter(
                VerificationRule.project_id == trace.project_id,
                VerificationRule.enabled.is_(True),
            )
            .all()
        )
        for rule in rules:
            if not _matches(rule, request_body):
                continue
            if not _sampled(rule):
                continue
            verdict = _run_one_rule(session, trace, rule)
            summary["evaluated"] += 1
            summary["verdicts"].append(verdict)
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        logger.exception("evaluate_trace failed for %s: %s", trace_id, exc)
    finally:
        session.close()
    return summary


def _run_one_rule(session, trace: Trace, rule: VerificationRule) -> str:
    """Render judge prompt, call gateway, parse verdict, write row."""
    request_body = trace.request_body or {}
    response_body = trace.response_body or {}

    try:
        prompt = render_judge_prompt(
            rule.judge_prompt_template, request_body, response_body
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Judge prompt render failed for rule %s: %s", rule.id, exc)
        _write_verification(session, trace, rule, verdict="error", reasoning=str(exc))
        return "error"

    judge_request = {
        "model": rule.judge_model,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
        "_sentinel": {"is_judge": True},
    }
    headers = {
        "Authorization": f"Bearer {settings.default_project_api_key}",
        "Content-Type": "application/json",
        JUDGE_HEADER: "1",
    }

    try:
        resp = httpx.post(
            GATEWAY_INTERNAL_URL, json=judge_request, headers=headers, timeout=60.0
        )
        body = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Judge HTTP call failed: %s", exc)
        _write_verification(session, trace, rule, verdict="error", reasoning=str(exc))
        return "error"

    content = ""
    try:
        content = body["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        content = str(body)

    verdict = parse_judge_response(content)
    _write_verification(
        session,
        trace,
        rule,
        verdict=verdict.verdict,
        confidence=verdict.confidence,
        reasoning=verdict.reasoning,
    )
    return verdict.verdict


def _write_verification(
    session,
    trace: Trace,
    rule: VerificationRule,
    *,
    verdict: str,
    confidence: float | None = None,
    reasoning: str | None = None,
) -> None:
    row = Verification(
        id=uuid.uuid4(),
        created_at=datetime.now(UTC),
        trace_id=trace.id,
        judge_trace_id=None,
        judge_model=rule.judge_model,
        verdict=verdict,
        confidence=confidence,
        reasoning=reasoning,
        rule_id=rule.id,
    )
    session.add(row)
