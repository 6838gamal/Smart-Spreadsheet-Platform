"""
Contract Pipeline — optimised for عقد / Contract documents.
Steps: OCR → Layout → NER[contract schema] → Suggestions
"""
from __future__ import annotations
from app.services.pipeline.base_pipeline import BasePipeline, PipelineContext
from app.services.ocr.ocr_service import OCRService
from app.services.layout.layout_detector import LayoutDetector
from app.services.ner.ner_service import NERService
from app.services.suggestions.suggestion_engine import SuggestionEngine


class ContractPipeline(BasePipeline):
    name = "contract"

    def __init__(self):
        self._ocr     = OCRService()
        self._layout  = LayoutDetector()
        self._ner     = NERService()
        self._suggest = SuggestionEngine()

    def get_steps(self):
        return [
            ("ocr",         self._step_ocr),
            ("layout",      self._step_layout),
            ("ner",         self._step_ner),
            ("suggestions", self._step_suggestions),
        ]

    def _step_ocr(self, ctx: PipelineContext):
        ext = ctx.file_format.lower().lstrip(".")
        if ext == "pdf":
            ctx.raw_text = self._ocr.extract_from_pdf(ctx.file_path)
        elif ext in {"png", "jpg", "jpeg", "bmp", "tiff", "webp"}:
            ctx.raw_text = self._ocr.extract_from_image(ctx.file_path)
        elif ext == "docx":
            try:
                import docx as _docx
                doc = _docx.Document(ctx.file_path)
                ctx.raw_text = "\n".join(p.text for p in doc.paragraphs)
            except Exception:
                pass
        ctx.language = self._ocr.detect_language(ctx.raw_text)

    def _step_layout(self, ctx: PipelineContext):
        result = self._layout.detect(ctx.file_path)
        ctx.page_count = result.page_count
        ctx.has_images = result.has_images
        ctx.layout_elements = [
            {
                "element_type": e.element_type,
                "page_number":  e.page_number,
                "x1": e.x1, "y1": e.y1, "x2": e.x2, "y2": e.y2,
                "confidence": e.confidence,
                "content":    e.content,
                "meta":       e.meta,
            }
            for e in result.elements
        ]

    def _step_ner(self, ctx: PipelineContext):
        entities = self._ner.extract(ctx.raw_text, "contract")
        ctx.entities = [
            {
                "entity_type":      e.entity_type,
                "value":            e.value,
                "normalized_value": e.normalized_value,
                "confidence":       e.confidence,
                "context":          e.context,
                "page_number":      e.page_number,
            }
            for e in entities
        ]

    def _step_suggestions(self, ctx: PipelineContext):
        suggs = self._suggest.generate(
            doc_type="contract",
            has_tables=ctx.has_tables,
            has_images=ctx.has_images,
            raw_text=ctx.raw_text,
            entities=ctx.entities,
            file_id=ctx.file_id,
            file_format=ctx.file_format,
        )
        ctx.suggestions = [
            {
                "suggestion_type": s.suggestion_type,
                "title":           s.title,
                "title_ar":        s.title_ar,
                "description":     s.description,
                "priority":        s.priority,
                "action_params":   s.action_params,
                "icon":            s.icon,
            }
            for s in suggs
        ]
