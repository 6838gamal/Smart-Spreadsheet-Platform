"""
Model Loader — lazy loading and in-memory caching for AI models.
Models are loaded on first use and evicted after 30 min of inactivity.
"""
from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

# idle eviction: 30 minutes
_EVICT_AFTER_SECS = 30 * 60


class _CachedEntry:
    def __init__(self, model: Any):
        self.model = model
        self.last_used = time.monotonic()

    def touch(self):
        self.last_used = time.monotonic()

    def is_stale(self) -> bool:
        return (time.monotonic() - self.last_used) > _EVICT_AFTER_SECS


class ModelLoader:
    """
    Lazy-load models by key.  Each model type gets a loader function
    registered via `register_loader(model_type)`.

    Usage:
        loader = ModelLoader()

        @loader.register_loader("ocr")
        def _load_ocr():
            return MyOCRModel(...)

        model = loader.get("ocr")   # loaded on first call, cached after
    """

    def __init__(self):
        self._loaders: dict[str, Any] = {}
        self._cache: dict[str, _CachedEntry] = {}

    # ── Registration ──────────────────────────────────────────────────────────

    def register_loader(self, model_type: str):
        """Decorator to register a zero-argument factory for a model type."""
        def decorator(fn):
            self._loaders[model_type] = fn
            logger.debug("Registered loader for model_type=%s", model_type)
            return fn
        return decorator

    # ── Access ────────────────────────────────────────────────────────────────

    def get(self, model_type: str) -> Any | None:
        """Return the loaded model, loading it if necessary."""
        entry = self._cache.get(model_type)
        if entry is not None:
            entry.touch()
            return entry.model

        loader = self._loaders.get(model_type)
        if loader is None:
            logger.warning("No loader registered for model_type=%s", model_type)
            return None

        logger.info("Loading model: %s", model_type)
        t0 = time.monotonic()
        try:
            model = loader()
            self._cache[model_type] = _CachedEntry(model)
            logger.info("Model %s loaded in %.1fs", model_type, time.monotonic() - t0)
            return model
        except Exception as exc:
            logger.error("Failed to load model %s: %s", model_type, exc)
            return None

    def is_loaded(self, model_type: str) -> bool:
        return model_type in self._cache

    def evict(self, model_type: str):
        """Force-evict a model from cache."""
        self._cache.pop(model_type, None)
        logger.info("Evicted model: %s", model_type)

    def evict_stale(self):
        """Remove models that have been idle longer than the eviction window."""
        stale = [k for k, v in self._cache.items() if v.is_stale()]
        for k in stale:
            self.evict(k)
        if stale:
            logger.info("Evicted %d stale model(s): %s", len(stale), stale)

    def status(self) -> dict[str, dict]:
        """Return a status dict for all registered and loaded models."""
        result = {}
        for mt in self._loaders:
            entry = self._cache.get(mt)
            result[mt] = {
                "registered": True,
                "loaded": entry is not None,
                "idle_secs": int(time.monotonic() - entry.last_used) if entry else None,
            }
        return result


# Global singleton — loaders registered at import time in each service
model_loader = ModelLoader()
