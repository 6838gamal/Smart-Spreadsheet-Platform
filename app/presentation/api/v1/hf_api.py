"""
Hugging Face AI API — Q&A, summarization, and text extraction endpoints.
Available to all authenticated users; admin controls which models are visible.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.infrastructure.database.models import User, File
from app.infrastructure.database.models_intelligence import AIModelRegistry, DocumentAnalysis
from app.services.ai.huggingface_service import run_task, HFError, HFModelLoadingError

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class AskRequest(BaseModel):
    question: str
    model_id: int                    # AIModelRegistry.id
    file_id: int | None = None       # optional file context
    analysis_id: int | None = None   # optional: use already-extracted raw_text


class SummarizeRequest(BaseModel):
    model_id: int
    file_id: int | None = None
    analysis_id: int | None = None
    text: str | None = None          # direct text input (no file needed)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_model_or_404(model_id: int, db: AsyncSession) -> AIModelRegistry:
    m = await db.get(AIModelRegistry, model_id)
    if not m:
        raise HTTPException(404, "النموذج غير موجود")
    if not m.is_active:
        raise HTTPException(400, "هذا النموذج غير مفعّل حالياً")
    return m


async def _extract_file_text(file_id: int, user_id: int, db: AsyncSession) -> str:
    """
    Extract text from a file for use as HF context.
    Priority: existing analysis raw_text → rich_extractor → empty string.
    """
    # 1. Try existing analysis first (fast path)
    analysis_result = await db.execute(
        select(DocumentAnalysis)
        .where(DocumentAnalysis.file_id == file_id)
        .order_by(DocumentAnalysis.created_at.desc())
        .limit(1)
    )
    analysis = analysis_result.scalar_one_or_none()
    if analysis and analysis.raw_text:
        return analysis.raw_text[:8000]

    # 2. Get file path
    file_result = await db.execute(
        select(File).where(File.id == file_id, File.owner_id == user_id)
    )
    file = file_result.scalar_one_or_none()
    if not file:
        raise HTTPException(404, "الملف غير موجود")

    # 3. Use rich_extractor for on-the-fly extraction
    try:
        from app.application.converter.rich_extractor import RichExtractor
        extractor = RichExtractor()
        result = extractor.extract(file.path)
        text = result.get("text") or result.get("raw_text") or ""
        return text[:8000]
    except Exception as exc:
        logger.warning("Text extraction failed for file %s: %s", file_id, exc)
        return ""


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/models")
async def list_hf_models(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all HF models visible to users (admin can see all)."""
    from app.infrastructure.database.models import UserRole
    query = select(AIModelRegistry).where(
        AIModelRegistry.source == "huggingface",
        AIModelRegistry.is_active == True,
    )
    if current_user.role != UserRole.ADMIN:
        query = query.where(AIModelRegistry.visible_to_users == True)

    rows = (await db.execute(query.order_by(AIModelRegistry.model_type, AIModelRegistry.name))).scalars().all()

    return {
        "models": [
            {
                "id":           m.id,
                "name":         m.name,
                "model_type":   m.model_type,
                "task_type":    m.task_type,
                "hf_model_id":  m.hf_model_id,
                "languages":    m.languages,
                "description":  m.description,
                "is_default":   m.is_default,
            }
            for m in rows
        ]
    }


@router.post("/ask")
async def ask_question(
    body: AskRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Answer a question about a file (or any free text context) using a HF model.
    Supports task_type: question-answering, text2text-generation.
    """
    model = await _get_model_or_404(body.model_id, db)

    if model.task_type not in ("question-answering", "text2text-generation"):
        raise HTTPException(400, f"هذا النموذج لا يدعم الإجابة على الأسئلة (نوعه: {model.task_type})")

    if not model.hf_model_id:
        raise HTTPException(400, "معرّف Hugging Face مفقود لهذا النموذج")

    # Get context text
    context = ""
    if body.analysis_id:
        analysis = await db.get(DocumentAnalysis, body.analysis_id)
        if analysis and analysis.raw_text:
            context = analysis.raw_text[:8000]
    elif body.file_id:
        context = await _extract_file_text(body.file_id, current_user.id, db)

    try:
        result = await run_task(
            task_type=model.task_type,
            hf_model_id=model.hf_model_id,
            question=body.question,
            context=context,
        )
        return {
            "ok": True,
            "model_name": model.name,
            "hf_model_id": model.hf_model_id,
            **result,
        }
    except HFModelLoadingError as exc:
        return {
            "ok": False,
            "loading": True,
            "estimated_seconds": exc.estimated_seconds,
            "error": str(exc),
        }
    except HFError as exc:
        return {"ok": False, "loading": False, "error": str(exc)}
    except Exception as exc:
        logger.error("HF ask error: %s", exc)
        return {"ok": False, "loading": False, "error": "حدث خطأ غير متوقع، يُرجى المحاولة مجدداً."}


@router.post("/summarize")
async def summarize_file(
    body: SummarizeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Summarize a file's content using a HF summarization model."""
    model = await _get_model_or_404(body.model_id, db)

    if model.task_type != "summarization":
        raise HTTPException(400, f"هذا النموذج لا يدعم التلخيص (نوعه: {model.task_type})")

    if not model.hf_model_id:
        raise HTTPException(400, "معرّف Hugging Face مفقود لهذا النموذج")

    # Resolve text
    text = body.text or ""
    if not text and body.analysis_id:
        analysis = await db.get(DocumentAnalysis, body.analysis_id)
        if analysis and analysis.raw_text:
            text = analysis.raw_text
    if not text and body.file_id:
        text = await _extract_file_text(body.file_id, current_user.id, db)

    try:
        result = await run_task(
            task_type="summarization",
            hf_model_id=model.hf_model_id,
            text=text,
        )
        return {"ok": True, "model_name": model.name, **result}
    except HFModelLoadingError as exc:
        return {"ok": False, "loading": True, "estimated_seconds": exc.estimated_seconds, "error": str(exc)}
    except HFError as exc:
        return {"ok": False, "loading": False, "error": str(exc)}
    except Exception as exc:
        logger.error("HF summarize error: %s", exc)
        return {"ok": False, "loading": False, "error": "حدث خطأ غير متوقع، يُرجى المحاولة مجدداً."}


@router.get("/extract/{file_id}")
async def extract_file_text(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Extract and return the raw text content of a file (for preview / context inspection)."""
    text = await _extract_file_text(file_id, current_user.id, db)
    return {
        "file_id": file_id,
        "text_length": len(text),
        "preview": text[:500] + ("…" if len(text) > 500 else ""),
        "has_text": bool(text.strip()),
    }
