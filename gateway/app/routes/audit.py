"""Audit routes — classifier CRUD, NDJSON export, ledger verification.

Endpoints:
  - POST   /api/audit/classifiers           create a tier-classifier
  - GET    /api/audit/classifiers           list classifiers (filter by project)
  - PATCH  /api/audit/classifiers/{id}      update (enable, edit pattern)
  - DELETE /api/audit/classifiers/{id}      delete
  - GET    /api/audit/export                stream NDJSON ledger export
  - GET    /api/audit/verify                recompute hashes, report tampering
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.audit.classifiers import ALLOWED_TIERS
from app.audit.ledger import verify_chain
from app.db.models import AuditClassifier, AuditLogEntry, Project
from app.db.session import AsyncSessionLocal

router = APIRouter(prefix="/api/audit", tags=["audit"])


class ClassifierCreate(BaseModel):
    project_id: uuid.UUID
    name: str = Field(min_length=1, max_length=255)
    match_jsonpath: str = Field(min_length=1)
    risk_tier: str
    enabled: bool = True


class ClassifierUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    match_jsonpath: str | None = Field(default=None, min_length=1)
    risk_tier: str | None = None
    enabled: bool | None = None


class ClassifierResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    match_jsonpath: str
    risk_tier: str
    enabled: bool

    model_config = {"from_attributes": True}


class ClassifierListResponse(BaseModel):
    classifiers: list[ClassifierResponse]
    total: int


class VerifyResponse(BaseModel):
    ok: bool
    checked: int
    error: str | None = None


def _check_tier(tier: str) -> None:
    if tier not in ALLOWED_TIERS:
        raise HTTPException(
            status_code=400,
            detail=f"risk_tier must be one of {sorted(ALLOWED_TIERS)}",
        )


@router.post("/classifiers", response_model=ClassifierResponse, status_code=201)
async def create_classifier(payload: ClassifierCreate) -> ClassifierResponse:
    _check_tier(payload.risk_tier)
    async with AsyncSessionLocal() as session:
        if await session.get(Project, payload.project_id) is None:
            raise HTTPException(status_code=404, detail="Project not found")
        row = AuditClassifier(
            project_id=payload.project_id,
            name=payload.name,
            match_jsonpath=payload.match_jsonpath,
            risk_tier=payload.risk_tier,
            enabled=payload.enabled,
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return ClassifierResponse.model_validate(row)


@router.get("/classifiers", response_model=ClassifierListResponse)
async def list_classifiers(
    project_id: uuid.UUID | None = Query(None),
) -> ClassifierListResponse:
    async with AsyncSessionLocal() as session:
        stmt = select(AuditClassifier).order_by(AuditClassifier.name)
        if project_id is not None:
            stmt = stmt.where(AuditClassifier.project_id == project_id)
        rows = (await session.execute(stmt)).scalars().all()
        return ClassifierListResponse(
            classifiers=[ClassifierResponse.model_validate(r) for r in rows],
            total=len(rows),
        )


@router.patch("/classifiers/{classifier_id}", response_model=ClassifierResponse)
async def update_classifier(
    classifier_id: uuid.UUID, payload: ClassifierUpdate
) -> ClassifierResponse:
    if payload.risk_tier is not None:
        _check_tier(payload.risk_tier)
    async with AsyncSessionLocal() as session:
        row = await session.get(AuditClassifier, classifier_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Classifier not found")
        for field in ("name", "match_jsonpath", "risk_tier", "enabled"):
            v = getattr(payload, field)
            if v is not None:
                setattr(row, field, v)
        await session.commit()
        await session.refresh(row)
        return ClassifierResponse.model_validate(row)


@router.delete("/classifiers/{classifier_id}", status_code=204)
async def delete_classifier(classifier_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as session:
        row = await session.get(AuditClassifier, classifier_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Classifier not found")
        await session.delete(row)
        await session.commit()


def _entry_to_dict(e: AuditLogEntry) -> dict:
    return {
        "id": str(e.id),
        "sequence": e.sequence,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "project_id": str(e.project_id),
        "trace_id": str(e.trace_id),
        "risk_tier": e.risk_tier,
        "payload": e.payload,
        "prev_hash": e.prev_hash,
        "entry_hash": e.entry_hash,
    }


@router.get("/export")
async def export_audit_log(
    project_id: uuid.UUID,
    since: datetime | None = Query(None),
    until: datetime | None = Query(None),
    risk_tier: str | None = Query(None),
):  # type: ignore[no-untyped-def]
    """Stream the audit log as NDJSON, ordered by sequence ascending.

    External auditors recompute each ``entry_hash`` with
    :func:`app.audit.ledger.compute_entry_hash` and confirm the chain.
    """
    if risk_tier is not None:
        _check_tier(risk_tier)

    async def gen():  # type: ignore[no-untyped-def]
        async with AsyncSessionLocal() as session:
            stmt = (
                select(AuditLogEntry)
                .where(AuditLogEntry.project_id == project_id)
                .order_by(AuditLogEntry.sequence)
            )
            if since is not None:
                stmt = stmt.where(AuditLogEntry.created_at >= since)
            if until is not None:
                stmt = stmt.where(AuditLogEntry.created_at <= until)
            if risk_tier is not None:
                stmt = stmt.where(AuditLogEntry.risk_tier == risk_tier)
            result = await session.stream(stmt)
            async for (row,) in result:
                yield json.dumps(_entry_to_dict(row), default=str) + "\n"

    return StreamingResponse(
        gen(),
        media_type="application/x-ndjson",
        headers={
            "Content-Disposition": f'attachment; filename="audit-{project_id}.ndjson"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/verify", response_model=VerifyResponse)
async def verify_audit_log(project_id: uuid.UUID) -> VerifyResponse:
    """Recompute the hash chain in-place and report the first inconsistency."""
    async with AsyncSessionLocal() as session:
        stmt = (
            select(AuditLogEntry)
            .where(AuditLogEntry.project_id == project_id)
            .order_by(AuditLogEntry.sequence)
        )
        entries = (await session.execute(stmt)).scalars().all()
        ok, err = verify_chain(list(entries))
        return VerifyResponse(ok=ok, checked=len(entries), error=err)
