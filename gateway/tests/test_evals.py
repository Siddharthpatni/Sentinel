"""Unit tests for the eval YAML parser and assertion engine."""

from __future__ import annotations

import pytest

from app.evals.assertions import CallResult, run_assertion
from app.evals.parser import (
    ContainsAssertion,
    MaxLatencyAssertion,
    RegexAssertion,
    parse_suite_yaml,
)

SAMPLE_YAML = """
name: demo
target:
  endpoint: /v1/chat/completions
  model: gpt-4o-mini
cases:
  - name: greet
    input:
      messages:
        - role: user
          content: hi
    assertions:
      - type: contains
        path: $.choices[0].message.content
        value: hello
      - type: max_latency_ms
        value: 5000
"""


def test_parse_suite_yaml_happy():
    suite = parse_suite_yaml(SAMPLE_YAML)
    assert suite.name == "demo"
    assert suite.target.model == "gpt-4o-mini"
    assert len(suite.cases) == 1
    assert suite.cases[0].assertions[0].type == "contains"


def test_parse_invalid_assertion_type():
    bad = SAMPLE_YAML.replace("type: contains", "type: not_a_real_type")
    with pytest.raises(Exception):
        parse_suite_yaml(bad)


def _response(text: str) -> dict:
    return {"choices": [{"message": {"content": text}}]}


def test_contains_passes_case_insensitive():
    a = ContainsAssertion(type="contains", value="Hello", case_sensitive=False)
    r = run_assertion(a, CallResult(response=_response("well hello there"), latency_ms=10, cost_usd=0))
    assert r.passed


def test_not_contains_fails_when_found():
    a = ContainsAssertion(type="not_contains", value="error", case_sensitive=False)
    r = run_assertion(a, CallResult(response=_response("there was an Error"), latency_ms=10, cost_usd=0))
    assert not r.passed


def test_regex_match():
    a = RegexAssertion(type="regex", pattern=r"^order #\d+")
    r = run_assertion(a, CallResult(response=_response("order #123 confirmed"), latency_ms=1, cost_usd=0))
    assert r.passed


def test_max_latency_fails_when_exceeded():
    a = MaxLatencyAssertion(type="max_latency_ms", value=100)
    r = run_assertion(a, CallResult(response=_response("x"), latency_ms=500, cost_usd=0))
    assert not r.passed
