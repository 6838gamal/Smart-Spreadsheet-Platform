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
        "version": "5.x",
        "source": "builtin",
        "is_active": True,
        "is_default": True,
        "languages": ["ar", "en"],
        "description": "Tesseract OCR via pytesseract — fast, good for clean documents",
    },
    {
        "name": "Rule-based Classifier",
        "model_type": "classification",
        "version": "1.0",
        "source": "builtin",
        "is_active": True,
        "is_default": True,
        "languages": ["ar", "en"],
        "description": "Keyword + heuristic document classifier — zero dependencies",
    },
    {
        "name": "pdfplumber Layout",
        "model_type": "layout",
        "version": "1.0",
        "source": "builtin",
        "is_active": True,
        "is_default": True,
        "languages": ["ar", "en"],
        "description": "Layout detection using pdfplumber bounding boxes",
    },
    {
        "name": "img2table Table Extractor",
        "model_type": "table",
        "version": "2.x",
        "source": "builtin",
        "is_active": True,
        "is_default": True,
        "languages": ["ar", "en"],
        "description": "Table detection and extraction via img2table",
    },
    {
        "name": "Regex NER",
        "model_type": "ner",
        "version": "1.0",
        "source": "builtin",
        "is_active": True,
        "is_default": True,
        "languages": ["ar", "en"],
        "description": "Pattern-based named entity recognition — no ML required",
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
