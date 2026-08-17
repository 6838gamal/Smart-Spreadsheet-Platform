"""
Hugging Face Inference API service.
Uses the HF Inference API (no local model downloads) — set HUGGINGFACE_TOKEN in secrets.
Supports: question-answering, summarization, text2text-generation, feature-extraction, speech-to-text.
"""
from __future__ import annotations

import logging
import os
import base64
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

HF_API_BASE = "https://api-inference.huggingface.co/models"
_TIMEOUT = 120  # زيادة المهلة للصوتيات الكبيرة


def _headers() -> dict[str, str]:
    h = {"Content-Type": "application/json"}
    if settings.HUGGINGFACE_TOKEN:
        h["Authorization"] = f"Bearer {settings.HUGGINGFACE_TOKEN}"
    return h


def _headers_multipart() -> dict[str, str]:
    """Headers for multipart/form-data requests (audio files)."""
    h = {}
    if settings.HUGGINGFACE_TOKEN:
        h["Authorization"] = f"Bearer {settings.HUGGINGFACE_TOKEN}"
    return h


async def _post(model_id: str, payload: dict, timeout: int = _TIMEOUT) -> Any:
    """POST to HF Inference API and return parsed JSON."""
    if not settings.EXTERNAL_APIS_ENABLED:
        raise HFError("ميزات الذكاء الاصطناعي معطّلة مؤقتاً. يُرجى المحاولة لاحقاً.")
    url = f"{HF_API_BASE}/{model_id}"
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, json=payload, headers=_headers())
        if resp.status_code == 503:
            # Model is loading — return a friendly error
            try:
                data = resp.json()
                wait = data.get("estimated_time", 20)
            except Exception:
                wait = 20
            raise HFModelLoadingError(
                f"النموذج يتم تحميله حالياً، يُرجى المحاولة بعد ~{int(wait)} ثانية.",
                estimated_seconds=int(wait),
            )
        if resp.status_code != 200:
            raise HFError(f"HF API error {resp.status_code}: {resp.text[:300]}")
        return resp.json()


async def _post_audio(model_id: str, audio_bytes: bytes, timeout: int = _TIMEOUT) -> Any:
    """
    POST audio data to HF Inference API for speech-to-text.
    Uses raw binary data with multipart/form-data or base64.
    """
    if not settings.EXTERNAL_APIS_ENABLED:
        raise HFError("ميزات الذكاء الاصطناعي معطّلة مؤقتاً. يُرجى المحاولة لاحقاً.")
    
    url = f"{HF_API_BASE}/{model_id}"
    
    # Some ASR models expect base64 encoded audio
    # Try both approaches: base64 in JSON and raw binary
    
    # Approach 1: Base64 in JSON (most reliable)
    audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        # Try with base64 first
        payload = {"inputs": audio_base64}
        resp = await client.post(url, json=payload, headers=_headers())
        
        if resp.status_code == 503:
            try:
                data = resp.json()
                wait = data.get("estimated_time", 20)
            except Exception:
                wait = 20
            raise HFModelLoadingError(
                f"النموذج يتم تحميله حالياً، يُرجى المحاولة بعد ~{int(wait)} ثانية.",
                estimated_seconds=int(wait),
            )
        
        if resp.status_code == 400 and "audio file" in resp.text.lower():
            # Try approach 2: Raw binary with multipart/form-data
            headers = _headers_multipart()
            headers["Content-Type"] = "audio/webm"  # or audio/wav
            resp2 = await client.post(url, content=audio_bytes, headers=headers)
            if resp2.status_code != 200:
                raise HFError(f"HF API error {resp2.status_code}: {resp2.text[:300]}")
            return resp2.json()
        
        if resp.status_code != 200:
            raise HFError(f"HF API error {resp.status_code}: {resp.text[:300]}")
        
        return resp.json()


# ── Custom exceptions ──────────────────────────────────────────────────────────

class HFError(Exception):
    """General HF API error."""

class HFModelLoadingError(HFError):
    """Model is warming up on HF servers."""
    def __init__(self, message: str, estimated_seconds: int = 20):
        super().__init__(message)
        self.estimated_seconds = estimated_seconds


# ── Task handlers ──────────────────────────────────────────────────────────────

async def question_answering(
    model_id: str,
    question: str,
    context: str,
) -> dict:
    """
    Run extractive Q&A.
    Returns {"answer": str, "score": float, "start": int, "end": int}
    """
    if not context.strip():
        raise HFError("لا يوجد محتوى نصي في الملف لاستخدامه كسياق للإجابة.")

    # Truncate context to avoid exceeding model limits (~512 tokens ≈ 2000 chars)
    truncated = context[:3000]

    result = await _post(model_id, {"inputs": {"question": question, "context": truncated}})

    if isinstance(result, list):
        result = result[0]
    if isinstance(result, dict) and "answer" in result:
        return {
            "answer": result.get("answer", ""),
            "score": round(result.get("score", 0.0), 4),
        }
    raise HFError(f"استجابة غير متوقعة من النموذج: {str(result)[:200]}")


async def text2text_qa(
    model_id: str,
    question: str,
    context: str,
) -> dict:
    """
    Run text2text generation for Q&A (Flan-T5 style).
    Returns {"answer": str}
    """
    truncated_ctx = context[:1500]
    prompt = f"Answer the question based on the context.\nContext: {truncated_ctx}\nQuestion: {question}\nAnswer:"

    result = await _post(model_id, {
        "inputs": prompt,
        "parameters": {"max_new_tokens": 200, "temperature": 0.3},
    })

    if isinstance(result, list) and result:
        text = result[0].get("generated_text", "")
        # Strip the prompt echo if present
        if "Answer:" in text:
            text = text.split("Answer:")[-1].strip()
        return {"answer": text}
    raise HFError(f"استجابة غير متوقعة من النموذج: {str(result)[:200]}")


async def summarize(
    model_id: str,
    text: str,
    max_length: int = 300,
    min_length: int = 50,
) -> dict:
    """
    Summarize text.
    Returns {"summary": str}
    """
    if not text.strip():
        raise HFError("لا يوجد نص لتلخيصه.")

    truncated = text[:3000]
    result = await _post(model_id, {
        "inputs": truncated,
        "parameters": {
            "max_length": max_length,
            "min_length": min_length,
            "do_sample": False,
        },
    })

    if isinstance(result, list) and result:
        summary = result[0].get("summary_text", result[0].get("generated_text", ""))
        return {"summary": summary}
    raise HFError(f"استجابة غير متوقعة من النموذج: {str(result)[:200]}")


async def extract_text_features(
    model_id: str,
    text: str,
) -> dict:
    """
    Get text embeddings/features.
    Returns {"embeddings": list[float]}
    """
    result = await _post(model_id, {"inputs": text[:512]})
    # Flatten if nested list
    if isinstance(result, list):
        if result and isinstance(result[0], list):
            flat = result[0]
            if flat and isinstance(flat[0], list):
                flat = flat[0]
            return {"embeddings": flat}
        return {"embeddings": result}
    raise HFError(f"استجابة غير متوقعة من النموذج: {str(result)[:200]}")


async def speech_to_text(
    model_id: str,
    audio_path: str | None = None,
    audio_bytes: bytes | None = None,
) -> dict:
    """
    Convert audio to text using a Hugging Face ASR model (e.g., Whisper).
    Returns {"text": str, "chunks": list} or just {"text": str}
    """
    if not audio_path and not audio_bytes:
        raise HFError("يجب توفير ملف صوتي أو بيانات صوتية.")
    
    # Read audio bytes if path provided
    if audio_path and not audio_bytes:
        try:
            with open(audio_path, "rb") as f:
                audio_bytes = f.read()
        except Exception as e:
            raise HFError(f"فشل قراءة الملف الصوتي: {str(e)}")
    
    if not audio_bytes or len(audio_bytes) == 0:
        raise HFError("البيانات الصوتية فارغة أو غير صالحة.")
    
    # Check file size (max 25MB for HF API)
    if len(audio_bytes) > 25 * 1024 * 1024:
        raise HFError("حجم الملف الصوتي كبير جداً (الحد الأقصى 25 ميجابايت)")
    
    try:
        result = await _post_audio(model_id, audio_bytes)
        
        # Parse different response formats
        if isinstance(result, dict):
            # Format: {"text": "..."} or {"chunks": [...], "text": "..."}
            text = result.get("text", "")
            chunks = result.get("chunks", [])
            if text:
                return {"text": text, "chunks": chunks}
            # Try alternative format
            if "transcription" in result:
                return {"text": result["transcription"]}
        
        elif isinstance(result, list) and result:
            # Format: [{"text": "..."}] or ["..."]
            if isinstance(result[0], dict):
                text = result[0].get("text", "")
                if text:
                    return {"text": text}
            elif isinstance(result[0], str):
                return {"text": result[0]}
        
        elif isinstance(result, str):
            return {"text": result}
        
        # Fallback: return raw result
        return {"text": str(result)}
        
    except HFModelLoadingError:
        raise
    except Exception as e:
        logger.error(f"Speech-to-text error: {e}")
        raise HFError(f"فشل تحويل الصوت إلى نص: {str(e)}")


# ── Unified dispatch ───────────────────────────────────────────────────────────

async def run_task(
    *,
    task_type: str,
    hf_model_id: str,
    question: str | None = None,
    context: str | None = None,
    text: str | None = None,
    audio_path: str | None = None,
    audio_bytes: bytes | None = None,
) -> dict:
    """
    Unified dispatcher. Raises HFError on failure.
    Returns a dict with an "answer", "summary", or "text" key depending on the task.
    """
    ctx = context or text or ""

    if task_type == "question-answering":
        if not question:
            raise HFError("يجب تقديم سؤال لهذا النموذج.")
        return await question_answering(hf_model_id, question, ctx)

    elif task_type == "text2text-generation":
        if not question:
            raise HFError("يجب تقديم سؤال لهذا النموذج.")
        return await text2text_qa(hf_model_id, question, ctx)

    elif task_type == "summarization":
        return await summarize(hf_model_id, ctx)

    elif task_type == "feature-extraction":
        return await extract_text_features(hf_model_id, ctx)

    elif task_type in ("speech-to-text", "automatic-speech-recognition", "asr"):
        return await speech_to_text(hf_model_id, audio_path=audio_path, audio_bytes=audio_bytes)

    else:
        raise HFError(f"نوع المهمة غير مدعوم: {task_type}")


# ── Model info helpers ─────────────────────────────────────────────────────────

async def get_model_info(model_id: str) -> dict:
    """
    Get model information from Hugging Face API.
    Returns model details including tags, pipeline_tag, etc.
    """
    if not settings.EXTERNAL_APIS_ENABLED:
        raise HFError("ميزات الذكاء الاصطناعي معطّلة مؤقتاً.")
    
    url = f"https://huggingface.co/api/models/{model_id}"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url)
        if resp.status_code != 200:
            raise HFError(f"فشل الحصول على معلومات النموذج: {resp.status_code}")
        return resp.json()


async def list_available_models(
    filter_task: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """
    List available Hugging Face models (public).
    Can filter by task type (e.g., "automatic-speech-recognition", "text-generation").
    """
    if not settings.EXTERNAL_APIS_ENABLED:
        raise HFError("ميزات الذكاء الاصطناعي معطّلة مؤقتاً.")
    
    params = {"limit": limit, "sort": "downloads", "direction": -1}
    if filter_task:
        params["pipeline_tag"] = filter_task
    
    url = "https://huggingface.co/api/models"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, params=params)
        if resp.status_code != 200:
            raise HFError(f"فشل الحصول على قائمة النماذج: {resp.status_code}")
        return resp.json()
