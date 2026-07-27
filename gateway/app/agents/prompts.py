"""Prompt rendering and structured-output parsing for the triage LLM nodes.

Mirrors app/verification/judges.py's shape (render + parse-never-raises),
but the templates here are static (code-defined, not per-project Jinja) so
there's no sandboxed templating involved — just plain string building.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

VALID_PATCH_KINDS = {"git_diff", "sql_fix", "config_update", "none"}


@dataclass
class DiagnosisResult:
    root_cause: str
    confidence: float | None
    suspected_files: list[str]
    raw: str


@dataclass
class FileChange:
    path: str
    diff: str


@dataclass
class RemediationResult:
    summary: str
    patch_kind: str
    files: list[FileChange] = field(default_factory=list)
    raw: str = ""


def render_diagnostic_prompt(
    *,
    provider: str,
    model: str,
    error_message: str | None,
    request_body: dict[str, Any] | None,
    response_body: dict[str, Any] | None,
    chunks: list[dict[str, Any]],
) -> str:
    """Build the root-cause diagnosis prompt from a failing trace + retrieved code."""
    context = "\n\n".join(
        f"--- {c['file_path']}:{c['start_line']}-{c['end_line']} ---\n{c['content']}"
        for c in chunks
    ) or "(no relevant code retrieved)"

    return f"""You are Sentinel's incident-triage diagnostic agent. A proxied LLM API
call failed or was flagged high-risk. Diagnose the root cause using the
retrieved source code below.

Provider/model: {provider}/{model}
Error message: {error_message or "(none)"}
Request body: {json.dumps(request_body, default=str)[:4000]}
Response body: {json.dumps(response_body, default=str)[:4000]}

Retrieved source code:
{context}

Respond with a single JSON object, no prose outside it:
{{"root_cause": "<one paragraph explaining what went wrong and why>",
  "confidence": <0.0-1.0>,
  "suspected_files": ["<repo-relative path>", ...]}}"""


def parse_diagnosis_response(raw_text: str) -> DiagnosisResult:
    """Parse the diagnostic LLM's response. Never raises — returns an error-shaped result."""
    payload = _extract_json_object(raw_text)
    if payload is None:
        return DiagnosisResult(
            root_cause="Diagnosis failed: model did not return valid JSON.",
            confidence=None,
            suspected_files=[],
            raw=raw_text,
        )
    root_cause = str(payload.get("root_cause", "")).strip() or "(no root cause returned)"
    suspected = payload.get("suspected_files")
    suspected_files = [str(p) for p in suspected] if isinstance(suspected, list) else []
    confidence = _coerce_unit_float(payload.get("confidence"))
    return DiagnosisResult(
        root_cause=root_cause,
        confidence=confidence,
        suspected_files=suspected_files,
        raw=raw_text,
    )


def render_remediation_prompt(diagnosis: dict[str, Any]) -> str:
    """Build the remediation-planning prompt from a persisted DiagnosisResult-shaped dict."""
    chunks = diagnosis.get("retrieved_chunks", [])
    context = "\n\n".join(
        f"--- {c['file_path']}:{c['start_line']}-{c['end_line']} ---\n{c['content']}"
        for c in chunks
    ) or "(no source code available)"

    return f"""You are Sentinel's incident-triage remediation-planning agent. Given the
diagnosis below, propose a concrete, minimal fix.

Root cause: {diagnosis.get("root_cause", "")}
Suspected files: {", ".join(diagnosis.get("suspected_files", [])) or "(none)"}

Source code for context:
{context}

If a code change is warranted, express it as a unified diff per file (standard
`--- a/path`/`+++ b/path` + `@@` hunk format, valid against the source shown
above). If no code change is needed (e.g. purely a config or infra fix, or
the diagnosis is informational only), return an empty "files" list.

Respond with a single JSON object, no prose outside it:
{{"summary": "<one sentence describing the fix>",
  "patch_kind": "git_diff" | "sql_fix" | "config_update" | "none",
  "files": [{{"path": "<repo-relative path>", "diff": "<unified diff text>"}}, ...]}}"""


def parse_remediation_response(raw_text: str) -> RemediationResult:
    """Parse the remediation LLM's response. Never raises — returns an empty-patch result on failure."""
    payload = _extract_json_object(raw_text)
    if payload is None:
        return RemediationResult(
            summary="Remediation planning failed: model did not return valid JSON.",
            patch_kind="none",
            files=[],
            raw=raw_text,
        )
    summary = str(payload.get("summary", "")).strip() or "(no summary returned)"
    patch_kind = str(payload.get("patch_kind", "none")).strip().lower()
    if patch_kind not in VALID_PATCH_KINDS:
        patch_kind = "none"
    raw_files = payload.get("files")
    files: list[FileChange] = []
    if isinstance(raw_files, list):
        for entry in raw_files:
            if isinstance(entry, dict) and entry.get("path") and entry.get("diff"):
                files.append(FileChange(path=str(entry["path"]), diff=str(entry["diff"])))
    return RemediationResult(summary=summary, patch_kind=patch_kind, files=files, raw=raw_text)


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


def _coerce_unit_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if not 0.0 <= f <= 1.0:
        return None
    return f
