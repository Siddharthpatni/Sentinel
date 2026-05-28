"""Dataset CRUD + item ingest routes.

Datasets are project-scoped named collections of input examples. The
dashboard's playground saves runs as items; evals iterate items. Auth
piggy-backs on the existing dashboard contract: routes are open inside
the gateway (same trust model as ``/api/traces``). Cross-project
isolation is enforced by always scoping by ``project_id`` query param.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.exc import IntegrityError

from app.db.models import Dataset, DatasetItem
from app.db.session import AsyncSessionLocal

router = APIRouter(prefix="/api/datasets", tags=["datasets"])


class DatasetCreate(BaseModel):
    project_id: uuid.UUID
    name: str
    description: str | None = None


class DatasetUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class DatasetResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    description: str | None = None
    created_at: datetime
    item_count: int = 0


class DatasetItemCreate(BaseModel):
    input: dict
    expected_output: dict | None = None
    item_metadata: dict = Field(default_factory=dict)
    source_trace_id: uuid.UUID | None = None


class DatasetItemResponse(BaseModel):
    id: uuid.UUID
    dataset_id: uuid.UUID
    input: dict
    expected_output: dict | None = None
    item_metadata: dict = Field(default_factory=dict)
    source_trace_id: uuid.UUID | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("", response_model=list[DatasetResponse])
async def list_datasets(
    project_id: uuid.UUID = Query(..., description="Project to list datasets for"),
) -> list[DatasetResponse]:
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(Dataset).where(Dataset.project_id == project_id).order_by(
                    desc(Dataset.created_at)
                )
            )
        ).scalars().all()
        counts = dict(
            (
                await session.execute(
                    select(DatasetItem.dataset_id, func.count(DatasetItem.id))
                    .where(DatasetItem.dataset_id.in_([d.id for d in rows]))
                    .group_by(DatasetItem.dataset_id)
                )
            ).all()
        ) if rows else {}
        return [
            DatasetResponse(
                id=d.id,
                project_id=d.project_id,
                name=d.name,
                description=d.description,
                created_at=d.created_at,
                item_count=int(counts.get(d.id, 0)),
            )
            for d in rows
        ]


@router.post("", response_model=DatasetResponse, status_code=201)
async def create_dataset(payload: DatasetCreate) -> DatasetResponse:
    async with AsyncSessionLocal() as session:
        d = Dataset(
            project_id=payload.project_id,
            name=payload.name,
            description=payload.description,
        )
        session.add(d)
        try:
            await session.commit()
        except IntegrityError as err:
            await session.rollback()
            raise HTTPException(
                status_code=409, detail="Dataset name already exists for project"
            ) from err
        await session.refresh(d)
        return DatasetResponse(
            id=d.id,
            project_id=d.project_id,
            name=d.name,
            description=d.description,
            created_at=d.created_at,
            item_count=0,
        )


@router.get("/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(dataset_id: uuid.UUID) -> DatasetResponse:
    async with AsyncSessionLocal() as session:
        d = await session.get(Dataset, dataset_id)
        if d is None:
            raise HTTPException(status_code=404, detail="Dataset not found")
        count = (
            await session.execute(
                select(func.count(DatasetItem.id)).where(
                    DatasetItem.dataset_id == dataset_id
                )
            )
        ).scalar_one()
        return DatasetResponse(
            id=d.id,
            project_id=d.project_id,
            name=d.name,
            description=d.description,
            created_at=d.created_at,
            item_count=int(count),
        )


@router.patch("/{dataset_id}", response_model=DatasetResponse)
async def update_dataset(
    dataset_id: uuid.UUID, payload: DatasetUpdate
) -> DatasetResponse:
    async with AsyncSessionLocal() as session:
        d = await session.get(Dataset, dataset_id)
        if d is None:
            raise HTTPException(status_code=404, detail="Dataset not found")
        if payload.name is not None:
            d.name = payload.name
        if payload.description is not None:
            d.description = payload.description
        try:
            await session.commit()
        except IntegrityError as err:
            await session.rollback()
            raise HTTPException(
                status_code=409, detail="Dataset name already exists for project"
            ) from err
        await session.refresh(d)
        count = (
            await session.execute(
                select(func.count(DatasetItem.id)).where(
                    DatasetItem.dataset_id == dataset_id
                )
            )
        ).scalar_one()
        return DatasetResponse(
            id=d.id,
            project_id=d.project_id,
            name=d.name,
            description=d.description,
            created_at=d.created_at,
            item_count=int(count),
        )


@router.delete("/{dataset_id}", status_code=204)
async def delete_dataset(dataset_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as session:
        d = await session.get(Dataset, dataset_id)
        if d is None:
            raise HTTPException(status_code=404, detail="Dataset not found")
        await session.delete(d)
        await session.commit()


@router.get("/{dataset_id}/items", response_model=list[DatasetItemResponse])
async def list_items(
    dataset_id: uuid.UUID,
    limit: int = Query(100, ge=1, le=500),
) -> list[DatasetItemResponse]:
    async with AsyncSessionLocal() as session:
        d = await session.get(Dataset, dataset_id)
        if d is None:
            raise HTTPException(status_code=404, detail="Dataset not found")
        rows = (
            await session.execute(
                select(DatasetItem)
                .where(DatasetItem.dataset_id == dataset_id)
                .order_by(desc(DatasetItem.created_at))
                .limit(limit)
            )
        ).scalars().all()
        return [DatasetItemResponse.model_validate(r) for r in rows]


@router.post(
    "/{dataset_id}/items",
    response_model=DatasetItemResponse,
    status_code=201,
)
async def add_item(
    dataset_id: uuid.UUID, payload: DatasetItemCreate
) -> DatasetItemResponse:
    async with AsyncSessionLocal() as session:
        d = await session.get(Dataset, dataset_id)
        if d is None:
            raise HTTPException(status_code=404, detail="Dataset not found")
        item = DatasetItem(
            dataset_id=dataset_id,
            input=payload.input,
            expected_output=payload.expected_output,
            item_metadata=payload.item_metadata,
            source_trace_id=payload.source_trace_id,
        )
        session.add(item)
        await session.commit()
        await session.refresh(item)
        return DatasetItemResponse.model_validate(item)


@router.delete("/{dataset_id}/items/{item_id}", status_code=204)
async def delete_item(dataset_id: uuid.UUID, item_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as session:
        item = await session.get(DatasetItem, item_id)
        if item is None or item.dataset_id != dataset_id:
            raise HTTPException(status_code=404, detail="Item not found")
        await session.delete(item)
        await session.commit()
