"""
In-memory model registry backed by the ai_model_registry DB table.
Tracks which model is active for each model_type.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


# Built-in model definitions (seeded on startup)
BUILTIN_MODELS = [
    {
        "name": "Tesseract OCR",
        "model_type": "ocr",
        "task_type": "text-extraction",
        "version": "5.x",
        "source": "builtin",
        "is_active": True,
        "is_default": True,
        "visible_to_users": False,
        "languages": ["ar", "en"],
        "description": "Tesseract OCR via pytesseract — fast, good for clean documents",
    },
    {
        "name": "Rule-based Classifier",
        "model_type": "classification",
        "task_type": "text-classification",
        "version": "1.0",
        "source": "builtin",
        "is_active": True,
        "is_default": True,
        "visible_to_users": False,
        "languages": ["ar", "en"],
        "description": "Keyword + heuristic document classifier — zero dependencies",
    },
    {
        "name": "pdfplumber Layout",
        "model_type": "layout",
        "task_type": "text-extraction",
        "version": "1.0",
        "source": "builtin",
        "is_active": True,
        "is_default": True,
        "visible_to_users": False,
        "languages": ["ar", "en"],
        "description": "Layout detection using pdfplumber bounding boxes",
    },
    {
        "name": "img2table Table Extractor",
        "model_type": "table",
        "task_type": "text-extraction",
        "version": "2.x",
        "source": "builtin",
        "is_active": True,
        "is_default": True,
        "visible_to_users": False,
        "languages": ["ar", "en"],
        "description": "Table detection and extraction via img2table",
    },
    {
        "name": "Regex NER",
        "model_type": "ner",
        "task_type": "token-classification",
        "version": "1.0",
        "source": "builtin",
        "is_active": True,
        "is_default": True,
        "visible_to_users": False,
        "languages": ["ar", "en"],
        "description": "Pattern-based named entity recognition — no ML required",
    },
    # ── Hugging Face Models ──────────────────────────────────────────────────
    {
        "name": "XLM-RoBERTa Q&A (متعدد اللغات)",
        "model_type": "qa",
        "task_type": "question-answering",
        "version": "1.0",
        "source": "huggingface",
        "hf_model_id": "deepset/xlm-roberta-base-squad2",
        "is_active": True,
        "is_default": True,
        "visible_to_users": True,
        "languages": ["ar", "en", "fr", "de", "es"],
        "description": "نموذج سؤال وجواب متعدد اللغات يدعم العربية والإنجليزية — مناسب للمستندات",
    },
    {
        "name": "AraBERT Q&A (عربي)",
        "model_type": "qa",
        "task_type": "question-answering",
        "version": "2.0",
        "source": "huggingface",
        "hf_model_id": "aubmindlab/bert-base-arabertv2",
        "is_active": True,
        "is_default": False,
        "visible_to_users": True,
        "languages": ["ar"],
        "description": "نموذج BERT مُدرَّب على النصوص العربية — دقة عالية للمحتوى العربي",
    },
    {
        "name": "BART Summarization (إنجليزي)",
        "model_type": "summarization",
        "task_type": "summarization",
        "version": "1.0",
        "source": "huggingface",
        "hf_model_id": "facebook/bart-large-cnn",
        "is_active": True,
        "is_default": True,
        "visible_to_users": True,
        "languages": ["en"],
        "description": "تلخيص النصوص الإنجليزية — مُدرَّب على مقالات الأخبار والوثائق",
    },
    {
        "name": "mBART Summarization (متعدد اللغات)",
        "model_type": "summarization",
        "task_type": "summarization",
        "version": "1.0",
        "source": "huggingface",
        "hf_model_id": "csebuetnlp/mT5_multilingual_XLSum",
        "is_active": True,
        "is_default": False,
        "visible_to_users": True,
        "languages": ["ar", "en", "fr"],
        "description": "تلخيص متعدد اللغات يدعم العربية — مُدرَّب على مجموعة XL-Sum",
    },
    {
        "name": "Flan-T5 Q&A (إنجليزي)",
        "model_type": "qa",
        "task_type": "text2text-generation",
        "version": "1.0",
        "source": "huggingface",
        "hf_model_id": "google/flan-t5-base",
        "is_active": True,
        "is_default": False,
        "visible_to_users": True,
        "languages": ["en"],
        "description": "نموذج Flan-T5 للإجابة على الأسئلة بصيغة نص-إلى-نص — متعدد المهام",
    },
    {
        "name": "Multilingual-E5 Embeddings",
        "model_type": "embedding",
        "task_type": "feature-extraction",
        "version": "1.0",
        "source": "huggingface",
        "hf_model_id": "intfloat/multilingual-e5-small",
        "is_active": True,
        "is_default": True,
        "visible_to_users": False,
        "languages": ["ar", "en", "fr", "de", "es", "zh"],
        "description": "نموذج تضمين متعدد اللغات للبحث الدلالي — خفيف وسريع",
    },
]


class ModelRegistry:
    """Lightweight in-memory registry with DB persistence."""

    def __init__(self):
        # model_type → dict of model info
        self._active: dict[str, dict] = {}

    def register_builtin(self, model_info: dict):
        mt = model_info["model_type"]
        if model_info.get("is_active"):
            self._active[mt] = model_info
        logger.debug("Registered model: %s (%s)", model_info["name"], mt)

    def get_active(self, model_type: str) -> dict | None:
        return self._active.get(model_type)

    def get_all(self) -> list[dict]:
        return list(self._active.values())

    def activate(self, model_type: str, model_info: dict):
        self._active[model_type] = model_info
        logger.info("Activated model: %s for type: %s", model_info.get("name"), model_type)

    def seed_builtins(self):
        for m in BUILTIN_MODELS:
            self.register_builtin(m)
        logger.info("Seeded %d built-in models", len(BUILTIN_MODELS))


# Global singleton
model_registry = ModelRegistry()
