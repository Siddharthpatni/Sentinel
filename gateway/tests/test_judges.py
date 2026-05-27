"""Unit tests for the judge module."""

from __future__ import annotations

import pytest
from jinja2.exceptions import SecurityError

from app.verification.judges import (
    parse_judge_response,
    render_judge_prompt,
)


def test_render_judge_prompt_basic():
    out = render_judge_prompt(
        "Q: {{ request.q }} A: {{ response.a }}",
        {"q": "hi"},
        {"a": "hello"},
    )
    assert out == "Q: hi A: hello"


def test_render_judge_prompt_sandbox_blocks_dunder():
    with pytest.raises(SecurityError):
        render_judge_prompt(
            "{{ request.__class__.__mro__ }}",
            {"q": "x"},
            {},
        )


def test_parse_bare_json_object():
    v = parse_judge_response('{"verdict": "agree", "confidence": 0.9, "reasoning": "ok"}')
    assert v.verdict == "agree"
    assert v.confidence == 0.9
    assert v.reasoning == "ok"


def test_parse_wrapped_in_prose():
    raw = 'Here is my verdict:\n{"verdict": "disagree", "confidence": 0.4}\nDone.'
    v = parse_judge_response(raw)
    assert v.verdict == "disagree"
    assert v.confidence == 0.4


def test_parse_invalid_verdict_returns_error():
    v = parse_judge_response('{"verdict": "maybe"}')
    assert v.verdict == "error"


def test_parse_garbage_returns_error_with_raw():
    v = parse_judge_response("totally not json")
    assert v.verdict == "error"
    assert v.reasoning == "totally not json"


def test_parse_confidence_out_of_range_dropped():
    v = parse_judge_response('{"verdict": "agree", "confidence": 7}')
    assert v.verdict == "agree"
    assert v.confidence is None
