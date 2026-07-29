"""Base Pipeline interface — all document pipelines inherit from this."""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PipelineContext:
    """Shared state flowing through all pipeline steps."""
    file_id: int
    file_path: str
    file_format: str
    analysis_id: int | None = None
    raw_text: str = ""
    language: str = "en"
    page_count: int = 0
    has_tables: bool = False
    has_images: bool = False
    layout_elements: list[dict] = field(default_factory=list)
    tables: list[Any] = field(default_factory=list)
    entities: list[dict] = field(default_factory=list)
    suggestions: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    step_timings: dict[str, int] = field(default_factory=dict)  # step → ms
    extra: dict[str, Any] = field(default_factory=dict)


class BasePipeline(ABC):
    name: str = "base"

    def run(self, ctx: PipelineContext) -> PipelineContext:
        steps = self.get_steps()
        for step_name, step_fn in steps:
            t0 = time.monotonic()
            try:
                step_fn(ctx)
            except Exception as exc:
                logger.warning("[%s] Step %s failed: %s", self.name, step_name, exc)
                ctx.errors.append(f"{step_name}: {exc}")
            ctx.step_timings[step_name] = int((time.monotonic() - t0) * 1000)
        return ctx

    @abstractmethod
    def get_steps(self) -> list[tuple[str, Any]]:
        """Return ordered list of (step_name, callable(ctx) → None)."""
        ...
