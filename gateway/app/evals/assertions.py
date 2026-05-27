"""Built-in assertion executors for the eval harness."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from jsonpath_ng.ext import parse as jsonpath_parse

from app.evals.parser import (
    ContainsAssertion,
    EqualsAssertion,
    JsonSchemaAssertion,
    LlmJudgeAssertion,
    MaxCostAssertion,
    MaxLatencyAssertion,
    RegexAssertion,
)


@dataclass
class AssertionResult:
    type: str
    passed: bool
    detail: str


@dataclass
class CallResult:
    response: dict
    latency_ms: int
    cost_usd: float


def _extract(response: dict, path: str) -> Any:
    expr = jsonpath_parse(path)
    matches = [m.value for m in expr.find(response)]
    if not matches:
        return None
    return matches[0]


def run_assertion(assertion: Any, call: CallResult) -> AssertionResult:
    """Dispatch on assertion type. Never raises — failures become AssertionResult."""
    try:
        if isinstance(assertion, ContainsAssertion):
            return _run_contains(assertion, call)
        if isinstance(assertion, EqualsAssertion):
            return _run_equals(assertion, call)
        if isinstance(assertion, RegexAssertion):
            return _run_regex(assertion, call)
        if isinstance(assertion, MaxLatencyAssertion):
            ok = call.latency_ms <= assertion.value
            return AssertionResult(
                type=assertion.type,
                passed=ok,
                detail=f"latency_ms={call.latency_ms} max={assertion.value}",
            )
        if isinstance(assertion, MaxCostAssertion):
            ok = call.cost_usd <= assertion.value
            return AssertionResult(
                type=assertion.type,
                passed=ok,
                detail=f"cost_usd={call.cost_usd:.6f} max={assertion.value}",
            )
        if isinstance(assertion, JsonSchemaAssertion):
            return _run_json_schema(assertion, call)
        if isinstance(assertion, LlmJudgeAssertion):
            return AssertionResult(
                type=assertion.type,
                passed=False,
                detail="llm_judge not wired (requires Phase 2 Step 11 eval runner)",
            )
    except Exception as exc:  # noqa: BLE001
        return AssertionResult(type=getattr(assertion, "type", "?"), passed=False, detail=str(exc))

    return AssertionResult(type="unknown", passed=False, detail="unknown assertion type")


def _run_contains(a: ContainsAssertion, call: CallResult) -> AssertionResult:
    value = _extract(call.response, a.path)
    text = "" if value is None else str(value)
    needle = a.value
    if not a.case_sensitive:
        text = text.lower()
        needle = needle.lower()
    found = needle in text
    passed = found if a.type == "contains" else not found
    return AssertionResult(type=a.type, passed=passed, detail=f"path={a.path} found={found}")


def _run_equals(a: EqualsAssertion, call: CallResult) -> AssertionResult:
    value = _extract(call.response, a.path)
    eq = value == a.value
    passed = eq if a.type == "equals" else not eq
    return AssertionResult(type=a.type, passed=passed, detail=f"actual={value!r}")


def _run_regex(a: RegexAssertion, call: CallResult) -> AssertionResult:
    value = _extract(call.response, a.path)
    text = "" if value is None else str(value)
    passed = re.search(a.pattern, text) is not None
    return AssertionResult(type=a.type, passed=passed, detail=f"pattern={a.pattern}")


def _run_json_schema(a: JsonSchemaAssertion, call: CallResult) -> AssertionResult:
    try:
        from jsonschema import validate
    except ImportError:
        return AssertionResult(
            type=a.type, passed=False, detail="jsonschema package not installed"
        )
    try:
        validate(call.response, a.schema_)
        return AssertionResult(type=a.type, passed=True, detail="schema matched")
    except Exception as exc:  # noqa: BLE001
        return AssertionResult(type=a.type, passed=False, detail=str(exc))
