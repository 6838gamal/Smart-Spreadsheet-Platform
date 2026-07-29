"""
OCR Service — wraps pytesseract (built-in) with Arabic + English support.
Interface designed to swap in PaddleOCR or EasyOCR without touching callers.
"""
from __future__ import annotations

import io
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Language map: ISO 639-1 → Tesseract lang code
_LANG_MAP = {
    "ar": "ara",
    "en": "eng",
    "fr": "fra",
    "de": "deu",
}
_DEFAULT_LANG = "ara+eng"


def _tesseract_available() -> bool:
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


class OCRService:
    """Extract text from images and PDFs using Tesseract."""

    def __init__(self, lang: str = _DEFAULT_LANG):
        self.lang = lang
        self._available = _tesseract_available()
        if not self._available:
            logger.warning("Tesseract not available — OCR will return empty strings")

    # ── Public API ──────────────────────────────────────────────────────────

    def extract_from_image(self, image_path: str | Path) -> str:
        """Extract text from a single image file."""
        if not self._available:
            return ""
        try:
            import pytesseract
            from PIL import Image
            img = Image.open(str(image_path))
            text = pytesseract.image_to_string(img, lang=self.lang, config="--psm 3")
            return self._clean(text)
        except Exception as e:
            logger.warning("OCR failed for %s: %s", image_path, e)
            return ""

    def extract_from_bytes(self, image_bytes: bytes) -> str:
        """Extract text from raw image bytes."""
        if not self._available:
            return ""
        try:
            import pytesseract
            from PIL import Image
            img = Image.open(io.BytesIO(image_bytes))
            text = pytesseract.image_to_string(img, lang=self.lang, config="--psm 3")
            return self._clean(text)
        except Exception as e:
            logger.warning("OCR from bytes failed: %s", e)
            return ""

    def extract_from_pdf(self, pdf_path: str | Path) -> str:
        """Extract text from a PDF — tries native text first, falls back to OCR."""
        path = Path(pdf_path)
        if not path.exists():
            return ""
        try:
            import pdfplumber
            full_text: list[str] = []
            with pdfplumber.open(str(path)) as pdf:
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    if text.strip():
                        full_text.append(text)
                    elif self._available:
                        # Fallback: render page as image and OCR it
                        img = page.to_image(resolution=200).original
                        buf = io.BytesIO()
                        img.save(buf, format="PNG")
                        ocr_text = self.extract_from_bytes(buf.getvalue())
                        full_text.append(ocr_text)
            return "\n\n".join(full_text)
        except Exception as e:
            logger.warning("PDF OCR failed for %s: %s", pdf_path, e)
            return ""

    def extract_with_boxes(self, image_path: str | Path) -> list[dict[str, Any]]:
        """Return list of {text, confidence, x, y, w, h} dicts."""
        if not self._available:
            return []
        try:
            import pytesseract
            from PIL import Image
            img = Image.open(str(image_path))
            data = pytesseract.image_to_data(
                img, lang=self.lang, output_type=pytesseract.Output.DICT
            )
            results = []
            for i, text in enumerate(data["text"]):
                if text.strip() and int(data["conf"][i]) > 20:
                    results.append({
                        "text": text.strip(),
                        "confidence": int(data["conf"][i]) / 100,
                        "x": data["left"][i],
                        "y": data["top"][i],
                        "w": data["width"][i],
                        "h": data["height"][i],
                    })
            return results
        except Exception as e:
            logger.warning("OCR with boxes failed: %s", e)
            return []

    def detect_language(self, text: str) -> str:
        """Heuristic language detection: Arabic vs English."""
        if not text:
            return "en"
        arabic_chars = len(re.findall(r'[\u0600-\u06FF]', text))
        total_chars = len(re.findall(r'[a-zA-Z\u0600-\u06FF]', text))
        if total_chars == 0:
            return "en"
        return "ar" if arabic_chars / total_chars > 0.3 else "en"

    # ── Private ──────────────────────────────────────────────────────────────

    @staticmethod
    def _clean(text: str) -> str:
        """Remove junk from OCR output."""
        # Remove lines with only special chars
        lines = [ln for ln in text.splitlines() if ln.strip() and not re.match(r'^[\W_]+$', ln.strip())]
        return "\n".join(lines)
