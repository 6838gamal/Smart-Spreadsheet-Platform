"""
Layout Detection Service.
Uses pdfplumber bounding boxes for PDFs and basic heuristics for images.
Interface ready to plug in LayoutParser / YOLO-based detector.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class LayoutElement:
    element_type: str       # paragraph | header | table | image | ...
    page_number: int
    x1: float = 0.0
    y1: float = 0.0
    x2: float = 0.0
    y2: float = 0.0
    confidence: float = 1.0
    content: str = ""
    meta: dict = field(default_factory=dict)


@dataclass
class LayoutResult:
    elements: list[LayoutElement]
    page_count: int
    has_tables: bool
    has_images: bool


class LayoutDetector:
    """Detect layout regions in documents using pdfplumber."""

    def detect(self, file_path: str | Path) -> LayoutResult:
        path = Path(file_path)
        ext = path.suffix.lower()

        if ext == ".pdf":
            return self._detect_pdf(path)
        elif ext in {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"}:
            return self._detect_image(path)
        else:
            return LayoutResult(elements=[], page_count=1, has_tables=False, has_images=False)

    def _detect_pdf(self, path: Path) -> LayoutResult:
        elements: list[LayoutElement] = []
        has_tables = False
        has_images = False
        page_count = 0

        try:
            import pdfplumber
            with pdfplumber.open(str(path)) as pdf:
                page_count = len(pdf.pages)
                for page_num, page in enumerate(pdf.pages, 1):
                    w = page.width or 1
                    h = page.height or 1

                    # ── Tables ──────────────────────────────────────────────
                    for table in (page.find_tables() or []):
                        bbox = table.bbox  # (x0, top, x1, bottom)
                        elements.append(LayoutElement(
                            element_type="table",
                            page_number=page_num,
                            x1=bbox[0] / w, y1=bbox[1] / h,
                            x2=bbox[2] / w, y2=bbox[3] / h,
                            confidence=0.9,
                            meta={"rows": len(table.rows), "cols": len(table.rows[0]) if table.rows else 0},
                        ))
                        has_tables = True

                    # ── Images ──────────────────────────────────────────────
                    for img in (page.images or []):
                        elements.append(LayoutElement(
                            element_type="image",
                            page_number=page_num,
                            x1=img.get("x0", 0) / w,
                            y1=img.get("top", 0) / h,
                            x2=img.get("x1", 0) / w,
                            y2=img.get("bottom", 0) / h,
                            confidence=1.0,
                        ))
                        has_images = True

                    # ── Text blocks ─────────────────────────────────────────
                    words = page.extract_words(x_tolerance=5, y_tolerance=5) or []
                    blocks = self._group_words_into_blocks(words, page_num, w, h)
                    elements.extend(blocks)

        except Exception as e:
            logger.warning("Layout detection failed for %s: %s", path, e)

        return LayoutResult(
            elements=elements,
            page_count=page_count,
            has_tables=has_tables,
            has_images=has_images,
        )

    def _detect_image(self, path: Path) -> LayoutResult:
        """Basic image layout: treat the whole image as one paragraph."""
        elements = [
            LayoutElement(
                element_type="paragraph",
                page_number=1,
                x1=0.0, y1=0.0, x2=1.0, y2=1.0,
                confidence=0.5,
                meta={"source": "image"},
            )
        ]
        return LayoutResult(elements=elements, page_count=1, has_tables=False, has_images=True)

    @staticmethod
    def _group_words_into_blocks(
        words: list[dict], page_num: int, page_w: float, page_h: float
    ) -> list[LayoutElement]:
        """Group nearby words into paragraph/header blocks."""
        if not words:
            return []

        elements: list[LayoutElement] = []
        # Sort by y-position then x-position
        sorted_words = sorted(words, key=lambda w: (w.get("top", 0), w.get("x0", 0)))

        # Simple row-grouping: words within 10px vertically = same line
        lines: list[list[dict]] = []
        current_line: list[dict] = []
        prev_y = None

        for word in sorted_words:
            y = word.get("top", 0)
            if prev_y is None or abs(y - prev_y) < 10:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(current_line)
                current_line = [word]
            prev_y = y
        if current_line:
            lines.append(current_line)

        # Group consecutive lines into blocks (gap > 15px = new block)
        blocks: list[list[list[dict]]] = []
        current_block: list[list[dict]] = []
        prev_bottom = None

        for line in lines:
            top = min(w.get("top", 0) for w in line)
            if prev_bottom is None or top - prev_bottom < 15:
                current_block.append(line)
            else:
                if current_block:
                    blocks.append(current_block)
                current_block = [line]
            prev_bottom = max(w.get("bottom", top + 12) for w in line)
        if current_block:
            blocks.append(current_block)

        for block in blocks:
            all_words = [w for line in block for w in line]
            if not all_words:
                continue
            x0 = min(w.get("x0", 0) for w in all_words)
            top = min(w.get("top", 0) for w in all_words)
            x1 = max(w.get("x1", 0) for w in all_words)
            bottom = max(w.get("bottom", 0) for w in all_words)
            text = " ".join(w.get("text", "") for w in all_words)

            # Heuristic: short text + big font → header
            avg_height = (bottom - top) / max(len(block), 1)
            etype = "header" if (len(text) < 80 and avg_height > 14) else "paragraph"

            elements.append(LayoutElement(
                element_type=etype,
                page_number=page_num,
                x1=x0 / page_w, y1=top / page_h,
                x2=x1 / page_w, y2=bottom / page_h,
                confidence=0.75,
                content=text[:500],
            ))

        return elements
