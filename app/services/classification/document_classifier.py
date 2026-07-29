"""
Document Classification Service.
Uses a keyword + heuristic engine (zero-dependency, fast).
Interface ready to plug in ModernBERT / zero-shot classifier.
"""
from __future__ import annotations

import re
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    doc_type: str
    confidence: float
    language: str
    signals: list[str]   # which keywords/patterns triggered


# ── Keyword rules ────────────────────────────────────────────────────────────

_RULES: list[tuple[str, list[str], float]] = [
    # (doc_type, [keyword patterns], base_score)
    ("invoice", [
        r'\binvoice\b', r'\bفاتورة\b', r'\binv[-\s]?\d+', r'\btax invoice\b',
        r'\bفاتورة ضريبية\b', r'\btotal amount\b', r'\bالمبلغ الإجمالي\b',
        r'\bdue date\b', r'\bتاريخ الاستحقاق\b',
    ], 0.85),
    ("receipt", [
        r'\breceipt\b', r'\bإيصال\b', r'\bوصل\b', r'\bpaid\b', r'\bمدفوع\b',
        r'\bcash receipt\b', r'\bتم الاستلام\b',
    ], 0.80),
    ("bank_statement", [
        r'\bbank statement\b', r'\bكشف حساب\b', r'\bstatement of account\b',
        r'\bbalance\b', r'\bرصيد\b', r'\bdebit\b', r'\bcredit\b',
        r'\biban\b', r'\bswift\b', r'\btransaction\b', r'\bمعاملة\b',
    ], 0.82),
    ("resume", [
        r'\bresume\b', r'\bcurriculum vitae\b', r'\bcv\b', r'\bسيرة ذاتية\b',
        r'\bwork experience\b', r'\bخبرة العمل\b', r'\bskills\b', r'\bمهارات\b',
        r'\beducation\b', r'\bالتعليم\b', r'\bobjective\b', r'\bالهدف الوظيفي\b',
    ], 0.85),
    ("contract", [
        r'\bcontract\b', r'\bعقد\b', r'\bagreement\b', r'\baتفاقية\b',
        r'\bparties\b', r'\bالأطراف\b', r'\bterms and conditions\b',
        r'\bالشروط والأحكام\b', r'\bsignature\b', r'\bالتوقيع\b',
        r'\beffective date\b', r'\bتاريخ السريان\b',
    ], 0.83),
    ("passport", [
        r'\bpassport\b', r'\bجواز سفر\b', r'\bجواز\b', r'\bnationality\b',
        r'\bالجنسية\b', r'\bdate of birth\b', r'\bتاريخ الميلاد\b',
        r'\bplace of birth\b', r'\bexpiry date\b', r'\bمرنة\b',
    ], 0.88),
    ("id", [
        r'\bnational id\b', r'\bهوية وطنية\b', r'\bid card\b', r'\bبطاقة هوية\b',
        r'\bidentity card\b', r'\bرقم الهوية\b', r'\bid number\b',
    ], 0.87),
    ("medical_report", [
        r'\bmedical report\b', r'\bتقرير طبي\b', r'\bdiagnosis\b', r'\bتشخيص\b',
        r'\bpatient\b', r'\bمريض\b', r'\bprescription\b', r'\bوصفة طبية\b',
        r'\bhospital\b', r'\bمستشفى\b', r'\bdoctor\b', r'\bطبيب\b',
    ], 0.82),
    ("research_paper", [
        r'\babstract\b', r'\bملخص\b', r'\breferences\b', r'\bالمراجع\b',
        r'\bdoi\b', r'\bjournal\b', r'\bمجلة\b', r'\bkeywords\b',
        r'\bالكلمات المفتاحية\b', r'\bintroduction\b', r'\bمقدمة\b',
        r'\bconclusion\b', r'\bالخاتمة\b',
    ], 0.80),
    ("form", [
        r'\bform\b', r'\bنموذج\b', r'\bstipple\b', r'\bplease fill\b',
        r'\bيرجى ملء\b', r'\bcheck box\b', r'\bاختر\b', r'\bdate.*:',
        r'\bname.*:', r'\bالاسم.*:',
    ], 0.70),
    ("certificate", [
        r'\bcertificate\b', r'\bشهادة\b', r'\bhereby certify\b',
        r'\bيشهد بذلك\b', r'\baward\b', r'\bجائزة\b', r'\bcompletion\b',
        r'\bإتمام\b', r'\baccreditation\b', r'\bاعتماد\b',
    ], 0.82),
    ("spreadsheet", [
        r'\bspreadsheet\b', r'\bjدول بيانات\b',
    ], 0.60),
]


class DocumentClassifier:
    """Fast rule-based document classifier."""

    def classify(self, text: str, filename: str = "") -> ClassificationResult:
        if not text and not filename:
            return ClassificationResult("unknown", 0.0, "en", [])

        combined = (text[:3000] + " " + filename).lower()
        language = self._detect_language(text)
        scores: dict[str, float] = {}
        signals: dict[str, list[str]] = {}

        for doc_type, patterns, base_score in _RULES:
            hits = []
            for pat in patterns:
                if re.search(pat, combined, re.IGNORECASE):
                    hits.append(pat)
            if hits:
                # More hits → higher confidence
                score = min(base_score + 0.02 * (len(hits) - 1), 0.97)
                scores[doc_type] = score
                signals[doc_type] = hits

        if not scores:
            return ClassificationResult("unknown", 0.3, language, [])

        best_type = max(scores, key=lambda k: scores[k])
        return ClassificationResult(
            doc_type=best_type,
            confidence=scores[best_type],
            language=language,
            signals=signals[best_type],
        )

    def classify_by_extension(self, filename: str) -> str | None:
        """Quick type from file extension."""
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        ext_map = {
            "pdf": None,       # need content analysis
            "xlsx": "spreadsheet", "xls": "spreadsheet", "csv": "spreadsheet",
            "pptx": "presentation", "ppt": "presentation",
            "docx": None, "doc": None,
        }
        return ext_map.get(ext)

    @staticmethod
    def _detect_language(text: str) -> str:
        if not text:
            return "en"
        arabic = len(re.findall(r'[\u0600-\u06FF]', text))
        latin = len(re.findall(r'[a-zA-Z]', text))
        total = arabic + latin
        if total == 0:
            return "en"
        return "ar" if arabic / total > 0.3 else "en"
