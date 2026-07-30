"""Model Manager API — list, activate, and inspect AI models."""
from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.infrastructure.database.models import User
from app.infrastructure.database.models_intelligence import AIModelRegistry
from app.infrastructure.ai.model_registry import model_registry, BUILTIN_MODELS

logger = logging.getLogger(__name__)
router = APIRouter()


async def _seed_db_models(db: AsyncSession):
    """Ensure built-in models are present in the DB."""
    for m in BUILTIN_MODELS:
        existing = (await db.execute(
            select(AIModelRegistry).where(
                AIModelRegistry.name == m["name"],
                AIModelRegistry.model_type == m["model_type"],
            )
        )).scalar_one_or_none()
        if not existing:
            db.add(AIModelRegistry(
                name=m["name"],
                model_type=m["model_type"],
                version=m["version"],
                source=m.get("source", "builtin"),
                is_active=m.get("is_active", False),
                is_default=m.get("is_default", False),
                languages=m.get("languages", []),
                description=m.get("description", ""),
            ))
    await db.commit()


@router.get("")
async def list_models(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all registered AI models."""
    await _seed_db_models(db)
    rows = (await db.execute(
        select(AIModelRegistry).order_by(AIModelRegistry.model_type, AIModelRegistry.created_at)
    )).scalars().all()

    return {
        "models": [
            {
                "id":          m.id,
                "name":        m.name,
                "model_type":  m.model_type,
                "version":     m.version,
                "source":      m.source,
                "is_active":   m.is_active,
                "is_default":  m.is_default,
                "languages":   m.languages,
                "description": m.description,
                "metrics":     m.metrics,
                "size_mb":     m.size_mb,
                "loaded_at":   m.loaded_at.isoformat() if m.loaded_at else None,
                "created_at":  m.created_at.isoformat() if m.created_at else None,
            }
            for m in rows
        ]
    }


@router.post("/{model_id}/activate")
async def activate_model(
    model_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Activate a model for its type (deactivates previous active)."""
    m = await db.get(AIModelRegistry, model_id)
    if not m:
        raise HTTPException(404, "Model not found")

    # Deactivate others of same type
    all_same_type = (await db.execute(
        select(AIModelRegistry).where(
            AIModelRegistry.model_type == m.model_type,
            AIModelRegistry.is_active == True,
        )
    )).scalars().all()
    for other in all_same_type:
        other.is_active = False

    m.is_active = True
    await db.commit()

    # Update in-memory registry
    model_registry.activate(m.model_type, {
        "name": m.name, "model_type": m.model_type,
        "version": m.version, "is_active": True,
    })
    return {"message": f"Model '{m.name}' activated for type '{m.model_type}'"}


@router.post("/{model_id}/set-default")
async def set_default_model(
    model_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Set a model as the default for its type."""
    m = await db.get(AIModelRegistry, model_id)
    if not m:
        raise HTTPException(404, "Model not found")

    # Unset previous default
    prev = (await db.execute(
        select(AIModelRegistry).where(
            AIModelRegistry.model_type == m.model_type,
            AIModelRegistry.is_default == True,
        )
    )).scalars().all()
    for p in prev:
        p.is_default = False

    m.is_default = True
    await db.commit()
    return {"message": f"Model '{m.name}' set as default for type '{m.model_type}'"}


@router.get("/status")
async def model_loader_status(
    current_user: User = Depends(get_current_user),
):
    """Return in-memory model loader cache status."""
    try:
        from app.infrastructure.ai.model_loader import model_loader
        return {"status": model_loader.status()}
    except Exception as exc:
        return {"status": {}, "error": str(exc)}
