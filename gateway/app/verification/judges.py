"""Judge prompt rendering and structured-output parsing."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from jinja2.sandbox import SandboxedEnvironment

VALID_VERDICTS = {"agree", "disagree", "uncertain"}

_env = SandboxedEnvironment(autoescape=False)


def render_judge_prompt(template: str, request: dict, response: dict) -> str:
    """Render a judge prompt template inside a sandboxed Jinja2 env.

    The sandbox blocks attribute access on Python internals so a malicious
    template cannot escape into the host process.
    """
    return _env.from_string(template).render(request=request, response=response)


@dataclass
class JudgeVerdict:
    verdict: str
    confidence: float | None
    reasoning: str | None
    raw: str


def parse_judge_response(raw_text: str) -> JudgeVerdict:
    """Parse the judge model's response into a structured verdict.

    Accepts either a bare JSON object or a JSON object wrapped in prose / code
    fences. On any failure, returns ``verdict="error"`` with the raw text in
    ``reasoning`` — never raises.
    """
    payload = _extract_json_object(raw_text)
    if payload is None:
        return JudgeVerdict(verdict="error", confidence=None, reasoning=raw_text, raw=raw_text)

    verdict = str(payload.get("verdict", "")).lower().strip()
    if verdict not in VALID_VERDICTS:
        return JudgeVerdict(verdict="error", confidence=None, reasoning=raw_text, raw=raw_text)

    confidence = _coerce_confidence(payload.get("confidence"))
    reasoning = payload.get("reasoning")
    if reasoning is not None:
        reasoning = str(reasoning)

    return JudgeVerdict(
        verdict=verdict,
        confidence=confidence,
        reasoning=reasoning,
        raw=raw_text,
    )


def _extract_json_object(text: str) -> dict[str, Any] | None:
    text = text.strip()
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match is None:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _coerce_confidence(value: Any) -> float | None:
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if not 0.0 <= f <= 1.0:
        return None
    return f
