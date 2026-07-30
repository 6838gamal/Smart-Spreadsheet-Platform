"""
Hugging Face Inference API service.
Uses the HF Inference API (no local model downloads) — set HUGGINGFACE_TOKEN in secrets.
Supports: question-answering, summarization, text2text-generation, feature-extraction.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

HF_API_BASE = "https://api-inference.huggingface.co/models"
_TIMEOUT = 60  # seconds


def _headers() -> dict[str, str]:
    h = {"Content-Type": "application/json"}
    if settings.HUGGINGFACE_TOKEN:
        h["Authorization"] = f"Bearer {settings.HUGGINGFACE_TOKEN}"
    return h


async def _post(model_id: str, payload: dict) -> Any:
    """POST to HF Inference API and return parsed JSON."""
    url = f"{HF_API_BASE}/{model_id}"
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(url, json=payload, headers=_headers())
        if resp.status_code == 503:
            # Model is loading — return a friendly error
            data = resp.json()
            wait = data.get("estimated_time", 20)
            raise HFModelLoadingError(
                f"النموذج يتم تحميله حالياً، يُرجى المحاولة بعد ~{int(wait)} ثانية.",
                estimated_seconds=int(wait),
            )
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


# ── Unified dispatch ───────────────────────────────────────────────────────────

async def run_task(
    *,
    task_type: str,
    hf_model_id: str,
    question: str | None = None,
    context: str | None = None,
    text: str | None = None,
) -> dict:
    """
    Unified dispatcher. Raises HFError on failure.
    Returns a dict with an "answer" or "summary" key depending on the task.
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

    else:
        raise HFError(f"نوع المهمة غير مدعوم: {task_type}")
