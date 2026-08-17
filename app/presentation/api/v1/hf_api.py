"""
Hugging Face AI API — Q&A, summarization, text extraction, and speech-to-text endpoints.
Available to all authenticated users; admin controls which models are visible.
"""
from __future__ import annotations

import logging
import os
import tempfile
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form
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


class ChatRequest(BaseModel):
    message: str
    file_id: int | None = None
    model_id: int | None = None          # override auto-selected model


class SpeechToTextRequest(BaseModel):
    model_id: int | None = None          # optional: specify ASR model


class AvailableModelsResponse(BaseModel):
    models: list[dict]
    default_model_id: int | None = None


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


async def _get_default_model_for_task(task_type: str, db: AsyncSession) -> AIModelRegistry | None:
    """Get the default active model for a given task type."""
    result = await db.execute(
        select(AIModelRegistry).where(
            AIModelRegistry.source == "huggingface",
            AIModelRegistry.task_type == task_type,
            AIModelRegistry.is_active == True,
            AIModelRegistry.visible_to_users == True,
        ).order_by(AIModelRegistry.is_default.desc()).limit(1)
    )
    return result.scalar_one_or_none()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/models", response_model=AvailableModelsResponse)
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

    models = [
        {
            "id":           m.id,
            "name":         m.name,
            "model_type":   m.model_type,
            "task_type":    m.task_type,
            "hf_model_id":  m.hf_model_id,
            "languages":    m.languages,
            "description":  m.description,
            "is_default":   m.is_default,
            "is_active":    m.is_active,
            "visible_to_users": m.visible_to_users,
        }
        for m in rows
    ]
    
    # Find default model
    default_model = next((m for m in rows if m.is_default), rows[0] if rows else None)
    
    return {
        "models": models,
        "default_model_id": default_model.id if default_model else None,
    }


@router.get("/models/task/{task_type}")
async def list_models_by_task(
    task_type: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List HF models filtered by task type (question-answering, summarization, speech-to-text, etc.)"""
    from app.infrastructure.database.models import UserRole
    
    query = select(AIModelRegistry).where(
        AIModelRegistry.source == "huggingface",
        AIModelRegistry.task_type == task_type,
        AIModelRegistry.is_active == True,
    )
    if current_user.role != UserRole.ADMIN:
        query = query.where(AIModelRegistry.visible_to_users == True)

    rows = (await db.execute(query.order_by(AIModelRegistry.is_default.desc(), AIModelRegistry.name))).scalars().all()

    return {
        "task_type": task_type,
        "models": [
            {
                "id":           m.id,
                "name":         m.name,
                "hf_model_id":  m.hf_model_id,
                "is_default":   m.is_default,
                "description":  m.description,
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
            "model_id": model.id,
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
        return {"ok": True, "model_name": model.name, "model_id": model.id, **result}
    except HFModelLoadingError as exc:
        return {"ok": False, "loading": True, "estimated_seconds": exc.estimated_seconds, "error": str(exc)}
    except HFError as exc:
        return {"ok": False, "loading": False, "error": str(exc)}
    except Exception as exc:
        logger.error("HF summarize error: %s", exc)
        return {"ok": False, "loading": False, "error": "حدث خطأ غير متوقع، يُرجى المحاولة مجدداً."}


@router.post("/chat")
async def chat(
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Smart chat endpoint — auto-routes to summarization or Q&A based on message intent.
    Falls back to a helpful message when no models are configured.
    """
    from app.infrastructure.database.models import UserRole

    # ── Detect intent ────────────────────────────────────────────────────────
    summarize_keywords = ["لخص", "ملخص", "خلاصة", "summarize", "summary", "tldr", "اختصار"]
    is_summarize = any(kw in body.message.lower() for kw in summarize_keywords)
    target_task = "summarization" if is_summarize else "question-answering"

    # ── Select model ─────────────────────────────────────────────────────────
    if body.model_id:
        model = await db.get(AIModelRegistry, body.model_id)
        if not model or not model.is_active:
            return {"ok": False, "error": "النموذج المحدد غير متاح"}
        if model.task_type not in ("question-answering", "text2text-generation", "summarization"):
            return {"ok": False, "error": f"هذا النموذج لا يدعم الدردشة (نوعه: {model.task_type})"}
    else:
        # Auto-select based on intent
        model = await _get_default_model_for_task(target_task, db)
        if not model:
            # Try fallback to any chat-capable model
            fallback_tasks = ["question-answering", "text2text-generation", "summarization"]
            for task in fallback_tasks:
                model = await _get_default_model_for_task(task, db)
                if model:
                    break

        if not model:
            return {
                "ok": False,
                "error": "لا توجد نماذج HF مفعّلة للدردشة. يُرجى تفعيل نموذج من لوحة الإدارة.",
            }

    if not model.hf_model_id:
        return {"ok": False, "error": "معرّف Hugging Face مفقود لهذا النموذج"}

    # ── Resolve file context ──────────────────────────────────────────────────
    context = ""
    file_name = None
    if body.file_id:
        file_result = await db.execute(
            select(File).where(File.id == body.file_id, File.owner_id == current_user.id)
        )
        file = file_result.scalar_one_or_none()
        if file:
            file_name = file.original_name
            context = await _extract_file_text(body.file_id, current_user.id, db)

    # ── Run inference ─────────────────────────────────────────────────────────
    try:
        result = await run_task(
            task_type=model.task_type,
            hf_model_id=model.hf_model_id,
            question=body.message,
            context=context,
            text=context if is_summarize else None,
        )
        
        # Extract answer based on task type
        if model.task_type == "summarization":
            answer = result.get("summary") or result.get("answer") or ""
        else:
            answer = result.get("answer") or result.get("summary") or ""
        
        return {
            "ok": True,
            "answer": answer,
            "model_name": model.name,
            "model_id": model.id,
            "task_type": model.task_type,
            "file_name": file_name,
            "has_context": bool(context),
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
        logger.error("HF chat error: %s", exc)
        return {"ok": False, "loading": False, "error": "حدث خطأ غير متوقع، يُرجى المحاولة مجدداً."}


@router.post("/speech-to-text")
async def speech_to_text(
    audio: UploadFile = File(...),
    model_id: int | None = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Convert audio file to text using a Hugging Face ASR model.
    Automatically selects a speech-to-text model if not specified.
    """
    # 1. Select ASR model
    if model_id:
        model = await db.get(AIModelRegistry, model_id)
        if not model or not model.is_active:
            return {"ok": False, "error": "النموذج غير موجود أو غير مفعّل"}
        if model.task_type != "speech-to-text":
            return {"ok": False, "error": f"هذا النموذج لا يدعم تحويل الصوت (نوعه: {model.task_type})"}
    else:
        # Auto-select: find first active ASR model
        model = await _get_default_model_for_task("speech-to-text", db)
        if not model:
            return {
                "ok": False,
                "error": "لا توجد نماذج تحويل صوت إلى نص مفعّلة. يرجى تفعيل نموذج مثل openai/whisper-large-v3"
            }
    
    if not model.hf_model_id:
        return {"ok": False, "error": "معرّف Hugging Face مفقود لهذا النموذج"}
    
    # 2. Validate audio file
    if not audio.filename:
        return {"ok": False, "error": "لم يتم تحميل ملف صوتي"}
    
    # Check file extension
    allowed_extensions = ['.webm', '.wav', '.mp3', '.m4a', '.flac', '.ogg', '.aac']
    file_ext = os.path.splitext(audio.filename)[1].lower()
    if file_ext not in allowed_extensions:
        return {"ok": False, "error": f"صيغة الملف غير مدعومة. الصيغ المدعومة: {', '.join(allowed_extensions)}"}
    
    # 3. Save audio to temp file
    tmp_path = None
    try:
        # Read audio content
        content = await audio.read()
        if len(content) == 0:
            return {"ok": False, "error": "الملف الصوتي فارغ"}
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
            tmp_file.write(content)
            tmp_path = tmp_file.name
        
        # 4. Run ASR using the service
        result = await run_task(
            task_type="speech-to-text",
            hf_model_id=model.hf_model_id,
            audio_path=tmp_path,
        )
        
        # 5. Extract text from result
        text = result.get("text", "")
        chunks = result.get("chunks", [])
        
        # If no text, try alternative response format
        if not text and isinstance(result, str):
            text = result
        
        return {
            "ok": True,
            "text": text,
            "model_name": model.name,
            "model_id": model.id,
            "hf_model_id": model.hf_model_id,
            "chunks": chunks,
            "filename": audio.filename,
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
    except Exception as e:
        logger.error(f"Speech-to-text error: {e}")
        return {"ok": False, "error": f"حدث خطأ أثناء تحويل الصوت: {str(e)}"}
    finally:
        # Cleanup temp file
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception as e:
                logger.warning(f"Could not delete temp file {tmp_path}: {e}")


@router.post("/speech-to-text-bytes")
async def speech_to_text_bytes(
    audio_bytes: bytes,
    model_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Convert audio bytes to text (alternative endpoint for binary data).
    """
    # 1. Select ASR model
    if model_id:
        model = await db.get(AIModelRegistry, model_id)
        if not model or not model.is_active:
            return {"ok": False, "error": "النموذج غير موجود أو غير مفعّل"}
        if model.task_type != "speech-to-text":
            return {"ok": False, "error": f"هذا النموذج لا يدعم تحويل الصوت (نوعه: {model.task_type})"}
    else:
        model = await _get_default_model_for_task("speech-to-text", db)
        if not model:
            return {
                "ok": False,
                "error": "لا توجد نماذج تحويل صوت إلى نص مفعّلة"
            }
    
    if not model.hf_model_id:
        return {"ok": False, "error": "معرّف Hugging Face مفقود لهذا النموذج"}
    
    # 2. Save audio to temp file
    tmp_path = None
    try:
        if len(audio_bytes) == 0:
            return {"ok": False, "error": "البيانات الصوتية فارغة"}
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp_file:
            tmp_file.write(audio_bytes)
            tmp_path = tmp_file.name
        
        # 3. Run ASR
        result = await run_task(
            task_type="speech-to-text",
            hf_model_id=model.hf_model_id,
            audio_path=tmp_path,
        )
        
        text = result.get("text", "")
        if not text and isinstance(result, str):
            text = result
        
        return {
            "ok": True,
            "text": text,
            "model_name": model.name,
            "model_id": model.id,
        }
    except Exception as e:
        logger.error(f"Speech-to-text bytes error: {e}")
        return {"ok": False, "error": str(e)}
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


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
        "full_text": text if len(text) <= 5000 else None,  # Only return full text if small enough
    }


@router.get("/models/stats")
async def get_models_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get statistics about available HF models."""
    from app.infrastructure.database.models import UserRole
    
    query = select(AIModelRegistry).where(
        AIModelRegistry.source == "huggingface",
        AIModelRegistry.is_active == True,
    )
    if current_user.role != UserRole.ADMIN:
        query = query.where(AIModelRegistry.visible_to_users == True)
    
    rows = (await db.execute(query)).scalars().all()
    
    stats = {
        "total": len(rows),
        "by_task": {},
        "by_type": {},
        "has_summarization": False,
        "has_qa": False,
        "has_asr": False,
        "has_text2text": False,
    }
    
    for model in rows:
        task = model.task_type or "unknown"
        stats["by_task"][task] = stats["by_task"].get(task, 0) + 1
        
        model_type = model.model_type or "unknown"
        stats["by_type"][model_type] = stats["by_type"].get(model_type, 0) + 1
        
        if task == "summarization":
            stats["has_summarization"] = True
        elif task == "question-answering":
            stats["has_qa"] = True
        elif task == "speech-to-text":
            stats["has_asr"] = True
        elif task == "text2text-generation":
            stats["has_text2text"] = True
    
    return {"stats": stats}
