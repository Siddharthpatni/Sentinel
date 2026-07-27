"""Deterministic patch-risk scoring for the ComplianceGuardrailNode.

Explicit rules rather than another LLM call — same reasoning as the existing
declarative AuditClassifier/RoutingPolicy rules: a compliance gate needs to
be auditable and explainable, not another opaque model judgment.

This is a *different* axis than Trace.risk_tier (the EU-AI-Act use-case
tier assigned to the original LLM traffic). This score answers "how risky
is it to auto-apply this specific code change", independent of what kind of
AI use case produced the failing trace.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.agents.prompts import FileChange

ALLOWED_PATCH_RISK_TIERS = {"low", "medium", "high"}

# Substring match against a file's repo-relative path.
SENSITIVE_PATH_SUBSTRINGS = (
    "app/security/",
    "app/auth.py",
    "db/migrations/",
    ".env",
    "docker-compose.yml",
)

MAX_LOW_RISK_FILES = 3
MAX_LOW_RISK_CHANGED_LINES = 50


def assess_patch_risk(files: list[FileChange], patch_kind: str) -> tuple[str, list[str]]:
    """Return (tier, reasons) for a proposed patch. Pure and deterministic."""
    if not files:
        return "low", ["no files touched — informational diagnosis only"]

    sensitive_hits = [f.path for f in files if any(p in f.path for p in SENSITIVE_PATH_SUBSTRINGS)]
    if sensitive_hits:
        return "high", [f"touches security/auth/migration/infra-sensitive path: {', '.join(sensitive_hits)}"]

    reasons: list[str] = []
    if patch_kind == "sql_fix":
        reasons.append("patch_kind is sql_fix (direct data mutation)")
    if len(files) > MAX_LOW_RISK_FILES:
        reasons.append(f"touches {len(files)} files (>{MAX_LOW_RISK_FILES})")
    total_changed_lines = sum(_count_changed_lines(f.diff) for f in files)
    if total_changed_lines > MAX_LOW_RISK_CHANGED_LINES:
        reasons.append(f"changes {total_changed_lines} lines (>{MAX_LOW_RISK_CHANGED_LINES})")

    if reasons:
        return "medium", reasons
    return "low", ["small, non-sensitive change"]


def _count_changed_lines(diff: str) -> int:
    return sum(
        1
        for line in diff.splitlines()
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
    )
