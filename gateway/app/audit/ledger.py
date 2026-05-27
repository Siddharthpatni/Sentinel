"""Append-only audit ledger with a SHA-256 hash chain.

Each entry stores:
  - ``sequence``    monotonically increasing per project.
  - ``prev_hash``   the previous entry's ``entry_hash`` (NULL for the first).
  - ``entry_hash``  SHA-256 over a deterministic JSON serialisation of the
                    entry's content plus ``prev_hash``.

Tampering with any entry breaks the chain forward — every subsequent
``entry_hash`` becomes invalid because the input changed. External auditors
re-run :func:`compute_entry_hash` over an export and compare.

The ledger is intentionally minimal: no signing keys, no per-tenant
secrets. Tamper-*evidence* is what most teams actually need; tamper-*proof*
would require external timestamping which is out of scope here.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.models import AuditLogEntry, Trace

logger = logging.getLogger(__name__)


def _canonical(obj: Any) -> str:
    """Deterministic JSON: sorted keys, no whitespace, UTF-8."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def compute_entry_hash(
    *,
    sequence: int,
    project_id: uuid.UUID | str,
    trace_id: uuid.UUID | str,
    risk_tier: str | None,
    payload: dict,
    prev_hash: str | None,
) -> str:
    """Pure function — auditors can call this on an export to re-derive hashes."""
    material = _canonical({
        "sequence": sequence,
        "project_id": str(project_id),
        "trace_id": str(trace_id),
        "risk_tier": risk_tier,
        "payload": payload,
        "prev_hash": prev_hash,
    })
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _payload_from_trace(trace: Trace) -> dict:
    """Snapshot the fields that matter for AI Act compliance."""
    return {
        "provider": trace.provider,
        "model": trace.model,
        "latency_ms": trace.latency_ms,
        "prompt_tokens": trace.prompt_tokens,
        "completion_tokens": trace.completion_tokens,
        "cost_usd": float(trace.cost_usd),
        "status_code": trace.status_code,
        "request_body": trace.request_body,
        "response_body": trace.response_body,
        "error_message": trace.error_message,
        "trace_created_at": trace.created_at.isoformat() if trace.created_at else None,
    }


def append_for_trace(session: Session, trace: Trace) -> AuditLogEntry:
    """Append one audit entry for ``trace``. Caller commits."""
    last = (
        session.execute(
            select(AuditLogEntry)
            .where(AuditLogEntry.project_id == trace.project_id)
            .order_by(desc(AuditLogEntry.sequence))
            .limit(1)
        )
        .scalars()
        .first()
    )
    sequence = (last.sequence + 1) if last else 1
    prev_hash = last.entry_hash if last else None

    payload = _payload_from_trace(trace)
    entry_hash = compute_entry_hash(
        sequence=sequence,
        project_id=trace.project_id,
        trace_id=trace.id,
        risk_tier=trace.risk_tier,
        payload=payload,
        prev_hash=prev_hash,
    )

    entry = AuditLogEntry(
        id=uuid.uuid4(),
        sequence=sequence,
        created_at=datetime.now(UTC),
        project_id=trace.project_id,
        trace_id=trace.id,
        risk_tier=trace.risk_tier,
        payload=payload,
        prev_hash=prev_hash,
        entry_hash=entry_hash,
    )
    session.add(entry)
    return entry


def verify_chain(entries: list[AuditLogEntry]) -> tuple[bool, str | None]:
    """Validate a contiguous slice of the ledger ordered by sequence.

    Returns ``(ok, error_detail)``. Used by ``GET /api/audit/verify``.
    """
    expected_prev: str | None = None
    expected_sequence: int | None = None
    for e in entries:
        if expected_sequence is None:
            expected_sequence = e.sequence
            expected_prev = e.prev_hash
        else:
            if e.sequence != expected_sequence:
                return False, f"sequence gap at id={e.id}: got {e.sequence}, expected {expected_sequence}"
            if e.prev_hash != expected_prev:
                return False, f"prev_hash mismatch at sequence {e.sequence}"
        recomputed = compute_entry_hash(
            sequence=e.sequence,
            project_id=e.project_id,
            trace_id=e.trace_id,
            risk_tier=e.risk_tier,
            payload=e.payload,
            prev_hash=e.prev_hash,
        )
        if recomputed != e.entry_hash:
            return False, f"entry_hash mismatch at sequence {e.sequence}"
        expected_prev = e.entry_hash
        expected_sequence = e.sequence + 1
    return True, None
