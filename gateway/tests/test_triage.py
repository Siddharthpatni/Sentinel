"""Tests for the triage risk model, prompt parsing, and the compliance/approval gate."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents.prompts import FileChange, parse_diagnosis_response, parse_remediation_response
from app.agents.risk import assess_patch_risk
from app.db.models import Base, Project, Trace, TriageExecution

# ---------------------------------------------------------------------------
# app/agents/risk.py
# ---------------------------------------------------------------------------


def test_assess_patch_risk_no_files_is_low():
    tier, _reasons = assess_patch_risk([], "none")
    assert tier == "low"


def test_assess_patch_risk_sensitive_path_is_high():
    files = [FileChange(path="app/auth.py", diff="+x")]
    tier, reasons = assess_patch_risk(files, "git_diff")
    assert tier == "high"
    assert any("sensitive" in r for r in reasons)


def test_assess_patch_risk_sql_fix_is_medium():
    files = [FileChange(path="app/routes/traces.py", diff="+x\n-y")]
    tier, reasons = assess_patch_risk(files, "sql_fix")
    assert tier == "medium"
    assert any("sql_fix" in r for r in reasons)


def test_assess_patch_risk_small_clean_change_is_low():
    files = [FileChange(path="app/routes/traces.py", diff="+one line")]
    tier, _reasons = assess_patch_risk(files, "git_diff")
    assert tier == "low"


def test_assess_patch_risk_many_files_is_medium():
    files = [FileChange(path=f"app/mod{i}.py", diff="+x") for i in range(5)]
    tier, _reasons = assess_patch_risk(files, "git_diff")
    assert tier == "medium"


def test_assess_patch_risk_large_diff_is_medium():
    big_diff = "\n".join(f"+line{i}" for i in range(60))
    files = [FileChange(path="app/routes/traces.py", diff=big_diff)]
    tier, _reasons = assess_patch_risk(files, "git_diff")
    assert tier == "medium"


# ---------------------------------------------------------------------------
# app/agents/prompts.py
# ---------------------------------------------------------------------------


def test_parse_diagnosis_bare_json():
    result = parse_diagnosis_response(
        '{"root_cause": "null template var", "confidence": 0.8, "suspected_files": ["a.py"]}'
    )
    assert result.root_cause == "null template var"
    assert result.confidence == 0.8
    assert result.suspected_files == ["a.py"]


def test_parse_diagnosis_wrapped_in_prose():
    raw = 'Here you go:\n{"root_cause": "bug", "confidence": 0.5, "suspected_files": []}\nDone.'
    result = parse_diagnosis_response(raw)
    assert result.root_cause == "bug"


def test_parse_diagnosis_garbage_returns_error_shape():
    result = parse_diagnosis_response("not json at all")
    assert "failed" in result.root_cause.lower()
    assert result.confidence is None
    assert result.suspected_files == []


def test_parse_diagnosis_confidence_out_of_range_dropped():
    result = parse_diagnosis_response('{"root_cause": "x", "confidence": 5}')
    assert result.confidence is None


def test_parse_remediation_bare_json():
    raw = (
        '{"summary": "fix null check", "patch_kind": "git_diff", '
        '"files": [{"path": "a.py", "diff": "+x"}]}'
    )
    result = parse_remediation_response(raw)
    assert result.summary == "fix null check"
    assert result.patch_kind == "git_diff"
    assert len(result.files) == 1
    assert result.files[0].path == "a.py"


def test_parse_remediation_invalid_patch_kind_defaults_to_none():
    raw = '{"summary": "x", "patch_kind": "yolo", "files": []}'
    result = parse_remediation_response(raw)
    assert result.patch_kind == "none"


def test_parse_remediation_garbage_returns_empty_files():
    result = parse_remediation_response("garbage")
    assert result.patch_kind == "none"
    assert result.files == []


# ---------------------------------------------------------------------------
# ComplianceGuardrailNode / HumanApprovalInterrupt branch (app/agents/triage.py)
# ---------------------------------------------------------------------------


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _seed_execution(session_factory, *, proposed_patch: dict) -> str:
    session = session_factory()
    project = Project(name=f"t-{uuid.uuid4()}", api_key=f"k-{uuid.uuid4()}")
    session.add(project)
    session.flush()
    trace = Trace(project_id=project.id, provider="openai", model="gpt-4o-mini", status_code=500)
    session.add(trace)
    session.flush()
    execution = TriageExecution(
        project_id=project.id,
        trace_id=trace.id,
        current_node="compliance",
        proposed_patch=proposed_patch,
    )
    session.add(execution)
    session.commit()
    execution_id = str(execution.id)
    session.close()
    return execution_id


def test_compliance_node_pauses_for_medium_risk(monkeypatch, session_factory):
    from app.agents import triage as triage_mod

    monkeypatch.setattr(triage_mod, "get_sync_session", session_factory)
    monkeypatch.setattr(triage_mod.run_execution_node, "delay", lambda *a, **k: None)

    execution_id = _seed_execution(
        session_factory,
        proposed_patch={
            "summary": "direct data fix",
            "patch_kind": "sql_fix",
            "files": [{"path": "a.py", "diff": "+x"}],
        },
    )

    triage_mod.run_compliance_node(execution_id)

    check = session_factory()
    updated = check.get(TriageExecution, uuid.UUID(execution_id))
    assert updated.patch_risk_tier == "medium"
    assert updated.status == "paused_for_approval"


def test_compliance_node_pauses_for_high_risk_sensitive_path(monkeypatch, session_factory):
    from app.agents import triage as triage_mod

    monkeypatch.setattr(triage_mod, "get_sync_session", session_factory)
    monkeypatch.setattr(triage_mod.run_execution_node, "delay", lambda *a, **k: None)

    execution_id = _seed_execution(
        session_factory,
        proposed_patch={
            "summary": "loosen auth check",
            "patch_kind": "git_diff",
            "files": [{"path": "app/auth.py", "diff": "+x"}],
        },
    )

    triage_mod.run_compliance_node(execution_id)

    check = session_factory()
    updated = check.get(TriageExecution, uuid.UUID(execution_id))
    assert updated.patch_risk_tier == "high"
    assert updated.status == "paused_for_approval"


def test_compliance_node_auto_continues_for_low_risk_no_files(monkeypatch, session_factory):
    from app.agents import triage as triage_mod

    monkeypatch.setattr(triage_mod, "get_sync_session", session_factory)
    called: dict[str, str] = {}
    monkeypatch.setattr(
        triage_mod.run_execution_node, "delay", lambda eid: called.setdefault("eid", eid)
    )

    execution_id = _seed_execution(
        session_factory,
        proposed_patch={"summary": "no code change needed", "patch_kind": "none", "files": []},
    )

    triage_mod.run_compliance_node(execution_id)

    check = session_factory()
    updated = check.get(TriageExecution, uuid.UUID(execution_id))
    assert updated.patch_risk_tier == "low"
    assert updated.status == "approved"
    assert updated.current_node == "execution"
    assert called["eid"] == execution_id
