"""
Search & Q&A API endpoints with Hugging Face AI integration.

Endpoints:
    POST   /api/v1/search/query              — extractive Q&A + AI-powered answers
    POST   /api/v1/search/chat               — general chat with AI (no document context)
    GET    /api/v1/search/stream             — generative Q&A via SSE (streams tokens)
    POST   /api/v1/search/chat/stream        — stream chat response (SSE)
    GET    /api/v1/search/stats              — indexing stats for the current user
    POST   /api/v1/search/index/{id}         — manually (re-)index a specific file
    GET    /api/v1/search/models             — list available HF models

File pipeline endpoints:
    GET    /api/v1/search/files/{id}/status  — pipeline status (pending/analyzing/indexing/ready/…)
    POST   /api/v1/search/files/{id}/analyze — trigger analyze + index (background)
    GET    /api/v1/search/pending            — list files not yet ready

✨ تحديث: 
    - إرجاع حقول التقدم التفصيلي (progress_current/total/percent/step/stage)
    - إصلاح منطق تحديد الحالة: "failed" لها أولوية على "completed"
    - إضافة حقل current_step و stage لدعم عرض الخطوة الحالية في الواجهة
"""
from __future__ import annotations
import json
import logging
from typing import Optional, List, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.infrastructure.database.models import User, File
from app.infrastructure.database.models_intelligence import (
    DocumentAnalysis,
    AnalysisStatus,
    AIModelRegistry,
    DocumentChunk,
)
from app.services.search.search_service import search_service
from app.services.ai.huggingface_service import run_task, HFError, HFModelLoadingError

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    file_ids: list[int] | None = Field(default=None)
    top_k: int = Field(default=5, ge=1, le=20)
    model_id: int | None = Field(default=None, description="HF model ID for AI-powered answers")
    use_ai: bool = Field(default=True, description="Use AI model for answer generation")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    file_id: int | None = None
    model_id: int | None = None


class SourceSchema(BaseModel):
    file_id: int
    file_name: str
    doc_type: str | None
    chunk_text: str
    chunk_index: int
    score: float


class QueryResponse(BaseModel):
    question: str
    answer: str
    answer_source: SourceSchema | None
    sources: list[SourceSchema]
    total_chunks_searched: int
    backend: str
    has_results: bool
    mode: str = "extractive"
    model_name: str | None = None
    model_id: int | None = None
    loading: bool = False
    estimated_seconds: int | None = None
    error: str | None = None


class ChatResponse(BaseModel):
    ok: bool
    answer: str
    model_name: str | None = None
    model_id: int | None = None
    file_name: str | None = None
    loading: bool = False
    estimated_seconds: int | None = None
    error: str | None = None


class FileStatusResponse(BaseModel):
    file_id: int
    # pending | analyzing | indexing | analyzed_not_indexed | ready | failed
    status: str
    chunks: int
    analysis_id: int | None = None
    analysis_status: str | None = None
    has_text: bool = False
    doc_type: str | None = None
    language: str | None = None
    error: str | None = None

    # ── حقول تفصيلية إضافية ──
    text_length: int = 0
    pipeline_used: str | None = None
    processing_ms: int | None = None
    updated_at: str | None = None
    is_indexing: bool = False

    # ✨ حقول تتبع التقدم (جديدة)
    stage: str | None = None              # analysis | indexing | done | failed
    current_step: str | None = None       # preparing | chunking | embedding | storing | done | failed
    progress_current: int = 0             # عدد المقاطع المعالجة
    progress_total: int = 0               # إجمالي المقاطع المتوقع
    progress_percent: float = 0.0         # نسبة التقدم 0-100
    stage_started_at: str | None = None   # وقت بدء المرحلة الحالية
    last_heartbeat_at: str | None = None  # آخر نبضة من المهمة
    is_stalled: bool = False              # هل المهمة معلقة؟


class AnalyzeTriggerResponse(BaseModel):
    ok: bool
    message: str
    file_id: int


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_model_or_none(model_id: int, db: AsyncSession) -> AIModelRegistry | None:
    """Get active model by ID."""
    result = await db.execute(
        select(AIModelRegistry).where(
            AIModelRegistry.id == model_id,
            AIModelRegistry.is_active == True,
            AIModelRegistry.visible_to_users == True,
        )
    )
    return result.scalar_one_or_none()


async def _get_file_name(file_id: int, user_id: int, db: AsyncSession) -> str | None:
    """Get file name by ID."""
    result = await db.execute(
        select(File.original_name).where(File.id == file_id, File.owner_id == user_id)
    )
    return result.scalar_one_or_none()


async def _get_default_model(db: AsyncSession) -> AIModelRegistry | None:
    """Get the default active model."""
    result = await db.execute(
        select(AIModelRegistry).where(
            AIModelRegistry.source == "huggingface",
            AIModelRegistry.is_active == True,
            AIModelRegistry.visible_to_users == True,
        ).order_by(AIModelRegistry.is_default.desc()).limit(1)
    )
    return result.scalar_one_or_none()


def _safe_enum_value(enum_obj) -> str | None:
    """Convert enum or any value to a lowercase string safely."""
    if enum_obj is None:
        return None
    val = getattr(enum_obj, "value", None)
    if val is not None:
        return str(val).lower()
    return str(enum_obj).lower()


def _iso_or_none(dt) -> str | None:
    """Convert datetime to ISO string safely."""
    if dt is None:
        return None
    try:
        return dt.isoformat()
    except Exception:
        return None


# ── Q&A Endpoints ─────────────────────────────────────────────────────────────

@router.post("/query", response_model=QueryResponse)
async def query_documents(
    body: QueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Sync Q&A with optional AI-powered answers.

    - If model_id is provided and use_ai=True: uses HF model for answer generation
    - Otherwise: uses BM25 extractive Q&A
    """
    # 1. Perform BM25 search first
    result = await search_service.query(
        db,
        user_id=current_user.id,
        question=body.question,
        file_ids=body.file_ids,
        top_k=body.top_k * 2,  # Get more for context
    )

    # 2. If no results, return early
    if not result.has_results or not result.sources:
        return QueryResponse(
            question=body.question,
            answer="لم أجد معلومات ذات صلة بسؤالك في المستندات.",
            answer_source=None,
            sources=[],
            total_chunks_searched=result.total_chunks_searched,
            backend=result.backend,
            has_results=False,
            mode="extractive",
        )

    # 3. If AI is enabled and model_id provided
    if body.use_ai and body.model_id:
        model = await _get_model_or_none(body.model_id, db)

        if model and model.hf_model_id:
            try:
                context = "\n\n---\n\n".join([
                    f"[المصدر {i+1}]: {s.chunk_text}"
                    for i, s in enumerate(result.sources[:3])
                ])

                hf_result = await run_task(
                    task_type=model.task_type or "question-answering",
                    hf_model_id=model.hf_model_id,
                    question=body.question,
                    context=context,
                )

                answer = hf_result.get("answer") or hf_result.get("summary") or ""

                best_source = result.sources[0] if result.sources else None
                answer_source = SourceSchema(
                    file_id=best_source.file_id,
                    file_name=best_source.file_name,
                    doc_type=best_source.doc_type,
                    chunk_text=best_source.chunk_text,
                    chunk_index=best_source.chunk_index,
                    score=best_source.score,
                ) if best_source else None

                return QueryResponse(
                    question=body.question,
                    answer=answer,
                    answer_source=answer_source,
                    sources=[SourceSchema(**vars(s)) for s in result.sources[:body.top_k]],
                    total_chunks_searched=result.total_chunks_searched,
                    backend="hf_ai",
                    has_results=bool(answer),
                    mode="ai_generated",
                    model_name=model.name,
                    model_id=model.id,
                )

            except HFModelLoadingError as exc:
                return QueryResponse(
                    question=body.question,
                    answer="",
                    answer_source=None,
                    sources=[SourceSchema(**vars(s)) for s in result.sources[:body.top_k]],
                    total_chunks_searched=result.total_chunks_searched,
                    backend="hf_ai",
                    has_results=True,
                    mode="loading",
                    model_name=model.name,
                    model_id=model.id,
                    loading=True,
                    estimated_seconds=exc.estimated_seconds,
                    error=str(exc),
                )

            except HFError as exc:
                logger.error(f"HF error in query: {exc}")
                return QueryResponse(
                    question=body.question,
                    answer=result.answer or "⚠️ خطأ في الذكاء الاصطناعي. عرض نتائج البحث.",
                    answer_source=SourceSchema(**vars(result.answer_source)) if result.answer_source else None,
                    sources=[SourceSchema(**vars(s)) for s in result.sources[:body.top_k]],
                    total_chunks_searched=result.total_chunks_searched,
                    backend=result.backend,
                    has_results=result.has_results,
                    mode="extractive_fallback",
                    error=str(exc),
                )

    # 4. Fallback: return BM25 results only
    return QueryResponse(
        question=body.question,
        answer=result.answer,
        answer_source=SourceSchema(**vars(result.answer_source)) if result.answer_source else None,
        sources=[SourceSchema(**vars(s)) for s in result.sources[:body.top_k]],
        total_chunks_searched=result.total_chunks_searched,
        backend=result.backend,
        has_results=result.has_results,
        mode=result.mode,
    )


@router.post("/chat", response_model=ChatResponse)
async def chat_with_ai(
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """General chat with AI (no document context required)."""
    model = None
    if body.model_id:
        model = await _get_model_or_none(body.model_id, db)
    else:
        model = await _get_default_model(db)

    if not model:
        return ChatResponse(
            ok=False,
            answer="لا توجد نماذج ذكاء اصطناعي مفعّلة. يرجى تفعيل نموذج من لوحة الإدارة.",
            error="No active models found",
        )

    if not model.hf_model_id:
        return ChatResponse(
            ok=False,
            answer="معرّف النموذج مفقود.",
            error="Model has no HF ID",
            model_name=model.name,
            model_id=model.id,
        )

    file_name = None
    context = ""
    if body.file_id:
        file_name = await _get_file_name(body.file_id, current_user.id, db)
        analysis_result = await db.execute(
            select(DocumentAnalysis)
            .where(
                DocumentAnalysis.file_id == body.file_id,
                DocumentAnalysis.status == AnalysisStatus.COMPLETED,
            )
            .order_by(DocumentAnalysis.id.desc())
            .limit(1)
        )
        analysis = analysis_result.scalar_one_or_none()
        if analysis and analysis.raw_text:
            context = analysis.raw_text[:3000]

    try:
        if context:
            prompt = f"Context: {context}\n\nQuestion: {body.message}\n\nAnswer:"
        else:
            prompt = body.message

        result = await run_task(
            task_type=model.task_type or "text2text-generation",
            hf_model_id=model.hf_model_id,
            question=prompt,
            context=context,
        )

        answer = result.get("answer") or result.get("summary") or ""

        return ChatResponse(
            ok=True,
            answer=answer,
            model_name=model.name,
            model_id=model.id,
            file_name=file_name,
        )

    except HFModelLoadingError as exc:
        return ChatResponse(
            ok=False,
            answer="جاري تحميل النموذج... سيصبح جاهزاً خلال بضع ثوان.",
            model_name=model.name,
            model_id=model.id,
            loading=True,
            estimated_seconds=exc.estimated_seconds,
            error=str(exc),
        )

    except HFError as exc:
        logger.error(f"HF chat error: {exc}")
        return ChatResponse(
            ok=False,
            answer=f"⚠️ حدث خطأ: {str(exc)}",
            model_name=model.name,
            model_id=model.id,
            error=str(exc),
        )

    except Exception as exc:
        logger.error(f"Chat error: {exc}")
        return ChatResponse(
            ok=False,
            answer="حدث خطأ غير متوقع. حاول مرة أخرى.",
            error=str(exc),
        )


@router.get("/stream")
async def stream_answer(
    request: Request,
    question: str,
    file_ids: str | None = None,
    top_k: int = 6,
    model_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Server-Sent Events endpoint for real-time generative answers."""
    parsed_ids: list[int] | None = None
    if file_ids:
        try:
            parsed_ids = [int(x.strip()) for x in file_ids.split(",") if x.strip()]
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid file_ids format")

    if not question.strip():
        raise HTTPException(status_code=400, detail="question must not be empty")

    # ✨ جلب النموذج قبل إنشاء الـ generator (تفادي استخدام db مغلق)
    hf_model = None
    if model_id:
        hf_model = await _get_model_or_none(model_id, db)

    async def event_generator():
        try:
            sources_found = False
            async for chunk in search_service.stream_answer(
                db,
                user_id=current_user.id,
                question=question,
                file_ids=parsed_ids,
                top_k=min(max(top_k, 1), 20),
            ):
                if 'sources' in chunk and '"type":"sources"' in chunk:
                    sources_found = True
                if await request.is_disconnected():
                    break
                yield chunk

            if sources_found and hf_model and hf_model.hf_model_id:
                try:
                    yield f"data: {json.dumps({'type': 'loading', 'model': hf_model.name}, ensure_ascii=False)}\n\n"
                    yield f"data: {json.dumps({'type': 'done', 'mode': 'llm', 'model': hf_model.name}, ensure_ascii=False)}\n\n"
                except Exception as e:
                    logger.error(f"AI enhancement error: {e}")
                    yield f"data: {json.dumps({'type': 'error', 'msg': str(e)}, ensure_ascii=False)}\n\n"
            else:
                if not sources_found:
                    yield f"data: {json.dumps({'type': 'done', 'mode': 'no_results'}, ensure_ascii=False)}\n\n"
                else:
                    yield f"data: {json.dumps({'type': 'done', 'mode': 'extractive'}, ensure_ascii=False)}\n\n"

        except HFModelLoadingError as exc:
            yield f"data: {json.dumps({'type': 'loading', 'estimated_seconds': exc.estimated_seconds, 'msg': str(exc)}, ensure_ascii=False)}\n\n"
        except Exception as exc:
            logger.error("SSE stream error: %s", exc)
            yield f"data: {json.dumps({'type': 'error', 'msg': str(exc)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/chat/stream")
async def stream_chat(
    request: Request,
    message: str,
    file_id: int | None = None,
    model_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stream chat response with AI model (SSE)."""
    model = None
    if model_id:
        model = await _get_model_or_none(model_id, db)
    else:
        model = await _get_default_model(db)

    if not model:
        async def error_generator():
            yield f"data: {json.dumps({'type': 'error', 'msg': 'لا توجد نماذج مفعّلة'}, ensure_ascii=False)}\n\n"
        return StreamingResponse(error_generator(), media_type="text/event-stream")

    context = ""
    file_name = None
    if file_id:
        file_name = await _get_file_name(file_id, current_user.id, db)
        analysis_result = await db.execute(
            select(DocumentAnalysis)
            .where(DocumentAnalysis.file_id == file_id)
            .order_by(DocumentAnalysis.id.desc())
            .limit(1)
        )
        analysis = analysis_result.scalar_one_or_none()
        if analysis and analysis.raw_text:
            context = analysis.raw_text[:3000]

    # ✨ حفظ مرجع النموذج قبل الـ generator
    _model_name = model.name
    _model_task_type = model.task_type or "text2text-generation"
    _model_hf_id = model.hf_model_id

    async def event_generator():
        try:
            yield f"data: {json.dumps({'type': 'start', 'model': _model_name}, ensure_ascii=False)}\n\n"

            result = await run_task(
                task_type=_model_task_type,
                hf_model_id=_model_hf_id,
                question=f"Context: {context}\n\nQuestion: {message}\n\nAnswer:" if context else message,
                context=context,
            )

            answer = result.get("answer") or result.get("summary") or "لم أتمكن من توليد إجابة."

            for i in range(0, len(answer), 3):
                if await request.is_disconnected():
                    break
                chunk = answer[i:i+3]
                yield f"data: {json.dumps({'type': 'token', 'text': chunk}, ensure_ascii=False)}\n\n"

            yield f"data: {json.dumps({'type': 'done', 'model': _model_name}, ensure_ascii=False)}\n\n"

        except HFModelLoadingError as exc:
            yield f"data: {json.dumps({'type': 'loading', 'estimated_seconds': exc.estimated_seconds}, ensure_ascii=False)}\n\n"
        except Exception as exc:
            logger.error(f"Stream chat error: {exc}")
            yield f"data: {json.dumps({'type': 'error', 'msg': str(exc)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Stats & Indexing ──────────────────────────────────────────────────────────

@router.get("/stats")
async def search_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return indexing statistics for the current user."""
    stats = await search_service.get_stats(db, user_id=current_user.id)

    model_count = await db.execute(
        select(func.count()).select_from(AIModelRegistry).where(
            AIModelRegistry.source == "huggingface",
            AIModelRegistry.is_active == True,
            AIModelRegistry.visible_to_users == True,
        )
    )

    return {
        **stats,
        "available_models": model_count.scalar() or 0,
    }


@router.post("/index/{file_id}")
async def index_file(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually trigger (re-)indexing of a file."""
    file = (await db.execute(
        select(File).where(File.id == file_id, File.owner_id == current_user.id)
    )).scalar_one_or_none()
    if not file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    analysis = (await db.execute(
        select(DocumentAnalysis)
        .where(
            DocumentAnalysis.file_id == file_id,
            DocumentAnalysis.status == AnalysisStatus.COMPLETED,
        )
        .order_by(DocumentAnalysis.id.desc())
    )).scalar_one_or_none()

    text = ""
    doc_type = None
    analysis_id = None

    if analysis and analysis.raw_text:
        text = analysis.raw_text
        doc_type = analysis.doc_type
        analysis_id = analysis.id
    else:
        from app.services.pipeline.pipeline_manager import _quick_text
        text = _quick_text(file.path, file.format)

    if not text.strip():
        return {"indexed": False, "reason": "No text found in this file. Run analysis first."}

    chunk_count = await search_service.index_document(
        db,
        file_id=file_id,
        analysis_id=analysis_id,
        user_id=current_user.id,
        text=text,
        doc_type=doc_type,
        language=analysis.language if analysis else None,
        filename=file.original_name,
    )

    return {
        "indexed": True,
        "file_id": file_id,
        "chunks": chunk_count,
        "source": "analysis" if analysis else "quick_extract",
    }


@router.get("/models")
async def get_available_models(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get available Hugging Face models for search."""
    from app.infrastructure.database.models import UserRole

    query = select(AIModelRegistry).where(
        AIModelRegistry.source == "huggingface",
        AIModelRegistry.is_active == True,
        AIModelRegistry.visible_to_users == True,
    )
    if current_user.role != UserRole.ADMIN:
        query = query.where(AIModelRegistry.visible_to_users == True)

    rows = (await db.execute(
        query.order_by(AIModelRegistry.is_default.desc(), AIModelRegistry.name)
    )).scalars().all()

    return {
        "models": [
            {
                "id": m.id,
                "name": m.name,
                "task_type": m.task_type,
                "hf_model_id": m.hf_model_id,
                "is_default": m.is_default,
                "description": m.description,
            }
            for m in rows
        ],
        "default_model_id": next((m.id for m in rows if m.is_default), rows[0].id if rows else None),
    }


# ── File Pipeline: Analyze + Index ────────────────────────────────────────────

@router.get("/files/{file_id}/status", response_model=FileStatusResponse)
async def file_pipeline_status(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return the current pipeline status of a file:
        pending               → لم يبدأ التحليل
        analyzing             → جاري التحليل الآن
        indexing              → التحليل انتهى، الفهرسة جارية
        analyzed_not_indexed  → التحليل انتهى لكن لا يوجد نص للفهرسة
        ready                 → جاهز للدردشة
        failed                → فشل التحليل

    ⚠️ Never returns 500 — falls back to safe defaults.
    """
    try:
        # 1. Verify ownership
        file = (await db.execute(
            select(File).where(File.id == file_id, File.owner_id == current_user.id)
        )).scalar_one_or_none()

        if not file:
            raise HTTPException(status_code=404, detail="File not found")

        # 2. Latest analysis (safe) + حقول التقدم
        analysis = None
        analysis_status_str = None
        has_text = False
        doc_type = None
        language = None
        analysis_error = None
        text_length = 0
        pipeline_used = None
        processing_ms = None
        updated_at_iso = None

        # ✨ حقول التقدم
        stage = None
        current_step = None
        progress_current = 0
        progress_total = 0
        progress_percent = 0.0
        stage_started_at_iso = None
        last_heartbeat_at_iso = None
        is_stalled = False

        try:
            analysis = (await db.execute(
                select(DocumentAnalysis)
                .where(DocumentAnalysis.file_id == file_id)
                .order_by(DocumentAnalysis.id.desc())
                .limit(1)
            )).scalar_one_or_none()

            if analysis:
                analysis_status_str = _safe_enum_value(analysis.status)
                has_text = bool(getattr(analysis, "raw_text", None))
                doc_type = getattr(analysis, "doc_type", None)
                language = getattr(analysis, "language", None)
                analysis_error = getattr(analysis, "error_message", None)
                text_length = len(analysis.raw_text) if analysis.raw_text else 0
                pipeline_used = getattr(analysis, "pipeline_used", None)
                processing_ms = getattr(analysis, "processing_ms", None)
                updated_at_iso = _iso_or_none(getattr(analysis, "updated_at", None))

                # ✨ حقول التقدم
                stage = getattr(analysis, "stage", None)
                current_step = getattr(analysis, "current_step", None)
                progress_current = getattr(analysis, "progress_current", 0) or 0
                progress_total = getattr(analysis, "progress_total", 0) or 0
                progress_percent = getattr(analysis, "progress_percent", 0.0) or 0.0
                stage_started_at_iso = _iso_or_none(getattr(analysis, "stage_started_at", None))
                last_heartbeat_at_iso = _iso_or_none(getattr(analysis, "last_heartbeat_at", None))

                # ✨ كشف المهمة المعلقة
                if hasattr(analysis, "is_stalled"):
                    try:
                        is_stalled = bool(analysis.is_stalled)
                    except Exception:
                        is_stalled = False
        except Exception as e:
            logger.warning(f"Could not load analysis for file {file_id}: {e}")

        # 3. Chunks count (safe)
        chunks = 0
        try:
            chunks = (await db.execute(
                select(func.count(DocumentChunk.id)).where(
                    DocumentChunk.file_id == file_id,
                    DocumentChunk.user_id == current_user.id,
                )
            )).scalar() or 0
        except Exception as e:
            logger.warning(f"Could not count chunks for file {file_id}: {e}")

        # ═══════════════════════════════════════════════════════════
        # 4. Determine status (with explicit "indexing" phase)
        # ═══════════════════════════════════════════════════════════
        #
        # Status priority (highest to lowest):
        #   1. chunks > 0                             → ready
        #   2. analysis FAILED                        → failed  ← ✨ رُفعت الأولوية
        #   3. analysis RUNNING/PROCESSING            → analyzing
        #   4. analysis COMPLETED + has_text + no chunks → indexing
        #   5. analysis COMPLETED + no text           → analyzed_not_indexed
        #   6. otherwise                              → pending
        #
        is_indexing = False

        if chunks > 0:
            status_str = "ready"

        elif analysis_status_str == "failed":
            # ✨ فشل له أولوية — يظهر للمستخدم بدل "indexing" الأبدي
            status_str = "failed"

        elif analysis_status_str in ("processing", "running"):
            status_str = "analyzing"

        elif analysis_status_str == "completed" and has_text:
            # ✨ Analysis done + text exists → indexing should be in progress
            status_str = "indexing"
            is_indexing = True

        elif analysis_status_str == "completed":
            # Analysis done but no extractable text
            status_str = "analyzed_not_indexed"

        else:
            status_str = "pending"

        # ✨ إذا كانت المهمة معلقة لكن status = indexing/analyzing → أبلغ عن ذلك
        if is_stalled and status_str in ("indexing", "analyzing"):
            logger.warning(
                f"⚠️ [status] File {file_id} appears stalled "
                f"(last heartbeat: {last_heartbeat_at_iso})"
            )
            # لا نُغيّر status، لكن نُمرّر is_stalled للمستخدم

        return FileStatusResponse(
            file_id=file_id,
            status=status_str,
            chunks=chunks,
            analysis_id=analysis.id if analysis else None,
            analysis_status=analysis_status_str,
            has_text=has_text,
            doc_type=doc_type,
            language=language,
            error=analysis_error,
            text_length=text_length,
            pipeline_used=pipeline_used,
            processing_ms=processing_ms,
            updated_at=updated_at_iso,
            is_indexing=is_indexing,
            # ✨ حقول التقدم
            stage=stage,
            current_step=current_step,
            progress_current=progress_current,
            progress_total=progress_total,
            progress_percent=progress_percent,
            stage_started_at=stage_started_at_iso,
            last_heartbeat_at=last_heartbeat_at_iso,
            is_stalled=is_stalled,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"❌ [status] Unexpected error for file {file_id}: {e}")
        return FileStatusResponse(
            file_id=file_id,
            status="pending",
            chunks=0,
            error=f"خطأ داخلي: {str(e)[:100]}",
        )


@router.post("/files/{file_id}/analyze", response_model=AnalyzeTriggerResponse)
async def trigger_file_analysis(
    file_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Manually trigger analysis + indexing for a file (background task).
    Safe to call multiple times.
    """
    file = (await db.execute(
        select(File).where(File.id == file_id, File.owner_id == current_user.id)
    )).scalar_one_or_none()

    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    try:
        from app.services.pipeline.analyze_and_index_task import analyze_and_index_background
    except ImportError as e:
        logger.error(f"❌ Failed to import background task: {e}")
        raise HTTPException(
            status_code=500,
            detail=(
                "خدمة التحليل غير متوفرة حالياً. "
                "تأكد من وجود app/services/pipeline/analyze_and_index_task.py"
            ),
        )

    background_tasks.add_task(
        analyze_and_index_background,
        file_id=file_id,
        user_id=current_user.id,
    )

    logger.info(
        f"📅 [API] Scheduled analyze+index for file {file_id} (user {current_user.id})"
    )

    return AnalyzeTriggerResponse(
        ok=True,
        message="بدأ التحليل في الخلفية. تابع الحالة عبر polling.",
        file_id=file_id,
    )


@router.get("/pending")
async def list_pending_files(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return files that are NOT yet ready for search
    (pending/analyzing/indexing/analyzed_not_indexed/failed).
    """
    all_files = (await db.execute(
        select(File).where(File.owner_id == current_user.id).order_by(File.created_at.desc())
    )).scalars().all()

    if not all_files:
        return {"pending": [], "total": 0}

    file_ids = [f.id for f in all_files]

    indexed_ids = set((await db.execute(
        select(DocumentChunk.file_id).where(
            DocumentChunk.user_id == current_user.id,
            DocumentChunk.file_id.in_(file_ids),
        ).distinct()
    )).scalars().all())

    analysis_rows = (await db.execute(
        select(DocumentAnalysis)
        .where(DocumentAnalysis.file_id.in_(file_ids))
        .order_by(DocumentAnalysis.id.desc())
    )).scalars().all()

    latest_analysis: dict[int, DocumentAnalysis] = {}
    for a in analysis_rows:
        if a.file_id not in latest_analysis:
            latest_analysis[a.file_id] = a

    pending = []
    for f in all_files:
        if f.id in indexed_ids:
            continue

        a = latest_analysis.get(f.id)
        a_status = _safe_enum_value(a.status) if a else None
        a_has_text = bool(getattr(a, "raw_text", None)) if a else False

        # ✨ Determine status with "indexing" phase + failed priority
        if a_status == "failed":
            status_str = "failed"
        elif a_status in ("processing", "running"):
            status_str = "analyzing"
        elif a_status == "completed" and a_has_text:
            status_str = "indexing"
        elif a_status == "completed":
            status_str = "analyzed_not_indexed"
        else:
            status_str = "pending"

        pending.append({
            "file_id": f.id,
            "original_name": f.original_name,
            "status": status_str,
            "format": f.format,
            "size_bytes": f.size_bytes,
        })

    return {
        "pending": pending,
        "total": len(pending),
    }
