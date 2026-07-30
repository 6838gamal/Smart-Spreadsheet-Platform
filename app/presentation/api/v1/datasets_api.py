"""Dataset Manager API — CRUD for training datasets and samples."""
from __future__ import annotations

import logging
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.infrastructure.database.models import User
from app.infrastructure.database.models_intelligence import Dataset, DatasetSample, UserFeedback

logger = logging.getLogger(__name__)
router = APIRouter()


class CreateDatasetRequest(BaseModel):
    name: str
    description: str | None = None
    dataset_type: str  # ocr | classification | ner | layout | table
    version: str | None = "1.0"
    split_train: float = 0.8
    split_val: float = 0.1
    split_test: float = 0.1


class AddFromFeedbackRequest(BaseModel):
    feedback_ids: list[int]


@router.get("")
async def list_datasets(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (await db.execute(
        select(Dataset).where(Dataset.created_by == current_user.id)
        .order_by(Dataset.created_at.desc())
    )).scalars().all()

    result = []
    for d in rows:
        sample_count = (await db.execute(
            select(func.count(DatasetSample.id)).where(DatasetSample.dataset_id == d.id)
        )).scalar_one() or 0
        result.append({
            "id": d.id, "name": d.name, "description": d.description,
            "dataset_type": d.dataset_type, "version": d.version,
            "status": d.status, "sample_count": sample_count,
            "split_train": d.split_train, "split_val": d.split_val, "split_test": d.split_test,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        })
    return {"datasets": result}


@router.post("")
async def create_dataset(
    body: CreateDatasetRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    d = Dataset(
        name=body.name, description=body.description,
        dataset_type=body.dataset_type, version=body.version,
        split_train=body.split_train, split_val=body.split_val,
        split_test=body.split_test, created_by=current_user.id,
        status="building",
    )
    db.add(d)
    await db.commit()
    await db.refresh(d)
    return {"id": d.id, "name": d.name, "status": d.status}


@router.get("/{dataset_id}")
async def get_dataset(
    dataset_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    d = await db.get(Dataset, dataset_id)
    if not d or d.created_by != current_user.id:
        raise HTTPException(404, "Dataset not found")

    samples = (await db.execute(
        select(DatasetSample).where(DatasetSample.dataset_id == dataset_id)
        .order_by(DatasetSample.created_at.desc()).limit(50)
    )).scalars().all()

    return {
        "id": d.id, "name": d.name, "description": d.description,
        "dataset_type": d.dataset_type, "version": d.version,
        "status": d.status, "sample_count": len(samples),
        "split_train": d.split_train, "split_val": d.split_val, "split_test": d.split_test,
        "samples": [
            {
                "id": s.id, "split": s.split,
                "input_path": s.input_path, "doc_type": s.doc_type,
                "language": s.language, "training_status": s.training_status,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in samples
        ],
    }


@router.delete("/{dataset_id}")
async def delete_dataset(
    dataset_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    d = await db.get(Dataset, dataset_id)
    if not d or d.created_by != current_user.id:
        raise HTTPException(404, "Dataset not found")
    await db.delete(d)
    await db.commit()
    return {"message": "Dataset deleted"}


@router.post("/{dataset_id}/samples/add_from_feedback")
async def add_samples_from_feedback(
    dataset_id: int,
    body: AddFromFeedbackRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    d = await db.get(Dataset, dataset_id)
    if not d or d.created_by != current_user.id:
        raise HTTPException(404, "Dataset not found")

    added = 0
    for fid in body.feedback_ids:
        fb = await db.get(UserFeedback, fid)
        if not fb or fb.user_id != current_user.id:
            continue
        sample = DatasetSample(
            dataset_id=dataset_id,
            feedback_id=fid,
            analysis_id=fb.analysis_id,
            file_id=fb.file_id,
            input_path=f"feedback/{fid}",
            labels={"correction": fb.corrected_value, "original": fb.original_value, "field": fb.field_name},
            doc_type=fb.doc_type, language=fb.language,
            split="train",
        )
        db.add(sample)
        fb.used_in_training = True
        added += 1

    await db.commit()
    return {"message": f"Added {added} samples from feedback", "added": added}
