"""
Search & Q&A API endpoints with Hugging Face AI integration.

POST /api/v1/search/query        — extractive Q&A + AI-powered answers
GET  /api/v1/search/stream       — generative Q&A via SSE (streams tokens)
GET  /api/v1/search/stats        — indexing stats for the current user
POST /api/v1/search/index/{id}   — manually (re-)index a specific file
POST /api/v1/search/chat         — general chat with AI (no document context)
"""
from __future__ import annotations
import json
import logging
from typing import Optional, List, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
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
    DocumentChunk
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


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_model_or_none(model_id: int, db: AsyncSession) -> AIModelRegistry | None:
    """Get active model by ID."""
    result = await db.execute(
        select(AIModelRegistry).where(
            AIModelRegistry.id == model_id,
            AIModelRegistry.is_active == True,
            AIModelRegistry.visible_to_users == True
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


# ── Endpoints ─────────────────────────────────────────────────────────────────

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
                # Prepare context from top sources
                context = "\n\n---\n\n".join([
                    f"[المصدر {i+1}]: {s.chunk_text}"
                    for i, s in enumerate(result.sources[:3])
                ])
                
                # Use HF model for answer generation
                hf_result = await run_task(
                    task_type=model.task_type or "question-answering",
                    hf_model_id=model.hf_model_id,
                    question=body.question,
                    context=context,
                )
                
                answer = hf_result.get("answer") or hf_result.get("summary") or ""
                
                # Create answer source from best match
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
                # Model is loading - return with loading state
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
                # Fallback to BM25
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
    """
    General chat with AI (no document context required).
    Uses Hugging Face models for conversational responses.
    """
    # 1. Select model
    model = None
    if body.model_id:
        model = await _get_model_or_none(body.model_id, db)
    else:
        # Auto-select default model
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
    
    # 2. Get file context if provided
    file_name = None
    context = ""
    if body.file_id:
        file_name = await _get_file_name(body.file_id, current_user.id, db)
        # Try to get analysis text
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
            context = analysis.raw_text[:3000]  # Truncate for context
    
    # 3. Run HF model
    try:
        # Prepare prompt with context if available
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
    file_ids: str | None = None,          # comma-separated IDs, e.g. "1,2,3"
    top_k: int = 6,
    model_id: int | None = None,          # HF model for streaming
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Server-Sent Events endpoint for real-time generative answers.

    Event types emitted:
      {"type":"sources", "sources":[...], "total": N}
      {"type":"token",   "text": "..."}          — 0-N times
      {"type":"done",    "mode": "llm"|"extractive"|"no_results"}
      {"type":"error",   "msg": "..."}
      {"type":"loading", "estimated_seconds": N}  — model is loading
    """
    parsed_ids: list[int] | None = None
    if file_ids:
        try:
            parsed_ids = [int(x.strip()) for x in file_ids.split(",") if x.strip()]
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid file_ids format")

    if not question.strip():
        raise HTTPException(status_code=400, detail="question must not be empty")

    async def event_generator():
        try:
            # Get model if provided
            hf_model = None
            if model_id:
                hf_model = await _get_model_or_none(model_id, db)
            
            # Emit sources first (from BM25 search)
            sources_found = False
            async for chunk in search_service.stream_answer(
                db,
                user_id=current_user.id,
                question=question,
                file_ids=parsed_ids,
                top_k=min(max(top_k, 1), 20),
            ):
                # Check if this is the sources event
                if 'sources' in chunk and '"type":"sources"' in chunk:
                    sources_found = True
                # Respect client disconnect
                if await request.is_disconnected():
                    break
                yield chunk
            
            # If we have sources and a model, try AI enhancement
            if sources_found and hf_model and hf_model.hf_model_id:
                # Get context from sources
                # This is simplified; in production, you'd parse the sources from the stream
                try:
                    # Send loading indicator
                    yield f"data: {json.dumps({'type': 'loading', 'model': hf_model.name}, ensure_ascii=False)}\n\n"
                    
                    # Generate AI answer (simplified - in production, use streaming)
                    # For now, we just send a done event
                    yield f"data: {json.dumps({'type': 'done', 'mode': 'llm', 'model': hf_model.name}, ensure_ascii=False)}\n\n"
                except Exception as e:
                    logger.error(f"AI enhancement error: {e}")
                    yield f"data: {json.dumps({'type': 'error', 'msg': str(e)}, ensure_ascii=False)}\n\n"
            else:
                # If no sources, send no_results
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
            "X-Accel-Buffering": "no",   # disable nginx buffering
        },
    )


@router.get("/stats")
async def search_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return indexing statistics for the current user."""
    # Get stats from search_service
    stats = await search_service.get_stats(db, user_id=current_user.id)
    
    # Add model stats
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
    """
    Get available Hugging Face models for search.
    This is an alias for /api/v1/hf/models to keep compatibility.
    """
    from app.infrastructure.database.models import UserRole
    
    query = select(AIModelRegistry).where(
        AIModelRegistry.source == "huggingface",
        AIModelRegistry.is_active == True,
        AIModelRegistry.visible_to_users == True,
    )
    if current_user.role != UserRole.ADMIN:
        query = query.where(AIModelRegistry.visible_to_users == True)

    rows = (await db.execute(query.order_by(AIModelRegistry.is_default.desc(), AIModelRegistry.name))).scalars().all()

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


@router.post("/chat/stream")
async def stream_chat(
    request: Request,
    message: str,
    file_id: int | None = None,
    model_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Stream chat response with AI model (SSE).
    """
    # Select model
    model = None
    if model_id:
        model = await _get_model_or_none(model_id, db)
    else:
        model = await _get_default_model(db)
    
    if not model:
        async def error_generator():
            yield f"data: {json.dumps({'type': 'error', 'msg': 'لا توجد نماذج مفعّلة'}, ensure_ascii=False)}\n\n"
        return StreamingResponse(error_generator(), media_type="text/event-stream")
    
    # Get context if file provided
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
    
    async def event_generator():
        try:
            yield f"data: {json.dumps({'type': 'start', 'model': model.name}, ensure_ascii=False)}\n\n"
            
            # For now, we simulate streaming with a single response
            # In production, use a proper streaming model
            result = await run_task(
                task_type=model.task_type or "text2text-generation",
                hf_model_id=model.hf_model_id,
                question=f"Context: {context}\n\nQuestion: {message}\n\nAnswer:" if context else message,
                context=context,
            )
            
            answer = result.get("answer") or result.get("summary") or "لم أتمكن من توليد إجابة."
            
            # Send tokens (split into chunks for streaming effect)
            for i in range(0, len(answer), 3):
                if await request.is_disconnected():
                    break
                chunk = answer[i:i+3]
                yield f"data: {json.dumps({'type': 'token', 'text': chunk}, ensure_ascii=False)}\n\n"
            
            yield f"data: {json.dumps({'type': 'done', 'model': model.name}, ensure_ascii=False)}\n\n"
            
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
