"""
Named Entity Recognition (NER) Service.
Uses regex patterns per document type — zero-dependency baseline.
Interface ready to plug in GLiNER / ModernBERT.
"""
from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Entity:
    entity_type: str
    value: str
    normalized_value: str = ""
    confidence: float = 0.8
    context: str = ""
    page_number: int | None = None


# ── Shared patterns ──────────────────────────────────────────────────────────

_EMAIL_RE = re.compile(r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b')
_PHONE_RE = re.compile(r'(?<!\d)(\+?[\d\s\-().]{7,16})(?!\d)')
_DATE_RE  = re.compile(
    r'\b(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}|\d{4}[\/\-\.]\d{1,2}[\/\-\.]\d{1,2}'
    r'|\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{2,4}'
    r'|\d{1,2}\s+(?:يناير|فبراير|مارس|أبريل|مايو|يونيو|يوليو|أغسطس|سبتمبر|أكتوبر|نوفمبر|ديسمبر)\s+\d{2,4})\b',
    re.IGNORECASE
)
_CURRENCY_RE = re.compile(
    r'\b(USD|EUR|GBP|SAR|AED|KWD|EGP|JOD|QAR|BHD|OMR|IQD|LYD|TND|MAD|DZD)\b'
    r'|[\$€£¥]\s*[\d,]+\.?\d*'
    r'|\b[\d,]+\.?\d*\s*(دولار|يورو|ريال|درهم|دينار|جنيه)\b',
    re.IGNORECASE
)
_URL_RE  = re.compile(r'https?://[^\s<>"]+|www\.[^\s<>"]+')
_IBAN_RE = re.compile(r'\b[A-Z]{2}\d{2}[A-Z0-9]{4,30}\b')
_TAX_RE  = re.compile(r'\b(?:VAT|ضريبة القيمة المضافة|tax|ضريبة)\s*(?:no\.?|number|رقم)?\s*[:\-]?\s*([\w\-\/]+)', re.IGNORECASE)
_AMOUNT_RE = re.compile(r'\b[\d,]+(?:\.\d{1,2})?\b')


class NERService:
    """Extract entities from text based on document type."""

    def extract(self, text: str, doc_type: str, page_number: int | None = None) -> list[Entity]:
        if not text:
            return []
        entities: list[Entity] = []

        # Always extract common entities
        entities.extend(self._extract_emails(text, page_number))
        entities.extend(self._extract_phones(text, page_number))
        entities.extend(self._extract_dates(text, page_number))
        entities.extend(self._extract_urls(text, page_number))
        entities.extend(self._extract_iban(text, page_number))

        # Document-specific extraction
        extractors = {
            "invoice": self._extract_invoice,
            "receipt": self._extract_invoice,
            "bank_statement": self._extract_bank_statement,
            "resume": self._extract_resume,
            "contract": self._extract_contract,
            "passport": self._extract_passport,
            "id": self._extract_id,
        }
        fn = extractors.get(doc_type)
        if fn:
            entities.extend(fn(text, page_number))

        return self._deduplicate(entities)

    # ── Invoice ──────────────────────────────────────────────────────────────

    def _extract_invoice(self, text: str, page: int | None) -> list[Entity]:
        result = []
        # Invoice number
        for pat in [
            r'(?:invoice|inv|فاتورة)\s*(?:no\.?|number|رقم|#)?\s*[:\-]?\s*([\w\-\/]+)',
            r'#\s*(INV[\-\w]+)',
        ]:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                result.append(Entity("invoice_number", m.group(1).strip(), confidence=0.9, page_number=page))
                break

        # Supplier
        for pat in [r'(?:from|supplier|vendor|من|المورد)\s*[:\-]?\s*(.{3,60})', r'bill from[:\s]+(.{3,60})']:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                result.append(Entity("supplier", m.group(1).strip()[:80], confidence=0.75, page_number=page))
                break

        # Customer
        for pat in [r'(?:to|bill to|customer|client|إلى|العميل)\s*[:\-]?\s*(.{3,60})', r'sold to[:\s]+(.{3,60})']:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                result.append(Entity("customer", m.group(1).strip()[:80], confidence=0.75, page_number=page))
                break

        # Total
        for pat in [r'(?:total|grand total|المجموع|الإجمالي)\s*[:\-]?\s*([\d,\.]+)', r'amount due[:\s]*([\d,\.]+)']:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                result.append(Entity("total", m.group(1).strip(), confidence=0.85, page_number=page))
                break

        # Tax
        m = _TAX_RE.search(text)
        if m:
            result.append(Entity("tax_number", m.group(1).strip(), confidence=0.80, page_number=page))

        # Currency
        for m in _CURRENCY_RE.finditer(text):
            result.append(Entity("currency", m.group(0).strip(), confidence=0.70, page_number=page))
            break  # Just first match

        return result

    # ── Bank Statement ────────────────────────────────────────────────────────

    def _extract_bank_statement(self, text: str, page: int | None) -> list[Entity]:
        result = []
        for pat in [r'(?:account|حساب)\s*(?:no\.?|number|رقم)?\s*[:\-]?\s*([\d\-]+)']:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                result.append(Entity("account_number", m.group(1).strip(), confidence=0.85, page_number=page))
        for pat in [r'(?:balance|رصيد)\s*[:\-]?\s*([\d,\.]+)']:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                result.append(Entity("balance", m.group(1).strip(), confidence=0.80, page_number=page))
        return result

    # ── Resume ────────────────────────────────────────────────────────────────

    def _extract_resume(self, text: str, page: int | None) -> list[Entity]:
        result = []
        # Name: typically first non-empty line of resume
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if lines and len(lines[0]) < 60:
            result.append(Entity("full_name", lines[0], confidence=0.65, page_number=page))

        # Skills section
        skills_match = re.search(r'(?:skills|مهارات)[:\s\n]+(.*?)(?:\n\n|\Z)', text, re.IGNORECASE | re.DOTALL)
        if skills_match:
            skills_text = skills_match.group(1)[:300]
            result.append(Entity("skills_section", skills_text.strip(), confidence=0.75, page_number=page))

        # LinkedIn
        linkedin = re.search(r'linkedin\.com/in/[\w\-]+', text, re.IGNORECASE)
        if linkedin:
            result.append(Entity("linkedin", linkedin.group(0), confidence=0.95, page_number=page))

        return result

    # ── Contract ──────────────────────────────────────────────────────────────

    def _extract_contract(self, text: str, page: int | None) -> list[Entity]:
        result = []
        # Effective date
        for pat in [r'(?:effective date|تاريخ السريان)\s*[:\-]?\s*(\d[\d\w\s,\/\-\.]{3,20})']:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                result.append(Entity("effective_date", m.group(1).strip(), confidence=0.80, page_number=page))

        # Expiry date
        for pat in [r'(?:expir|termination date|تاريخ الانتهاء)\s*[:\-]?\s*(\d[\d\w\s,\/\-\.]{3,20})']:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                result.append(Entity("expiry_date", m.group(1).strip(), confidence=0.80, page_number=page))

        # Amount
        for pat in [r'(?:contract value|amount|مبلغ|قيمة العقد)\s*[:\-]?\s*([\d,\.]+)']:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                result.append(Entity("contract_amount", m.group(1).strip(), confidence=0.75, page_number=page))

        return result

    # ── Passport / ID ─────────────────────────────────────────────────────────

    def _extract_passport(self, text: str, page: int | None) -> list[Entity]:
        result = []
        # Passport number (e.g., A12345678)
        m = re.search(r'\b([A-Z]{1,2}\d{6,8})\b', text)
        if m:
            result.append(Entity("passport_number", m.group(1), confidence=0.85, page_number=page))
        m = re.search(r'(?:nationality|الجنسية)\s*[:\-]?\s*([A-Za-z\u0600-\u06FF ]{3,30})', text, re.IGNORECASE)
        if m:
            result.append(Entity("nationality", m.group(1).strip(), confidence=0.80, page_number=page))
        return result

    def _extract_id(self, text: str, page: int | None) -> list[Entity]:
        result = []
        m = re.search(r'(?:id number|رقم الهوية|national id)\s*[:\-]?\s*(\d{8,12})', text, re.IGNORECASE)
        if m:
            result.append(Entity("id_number", m.group(1), confidence=0.90, page_number=page))
        return result

    # ── Common ────────────────────────────────────────────────────────────────

    def _extract_emails(self, text: str, page: int | None) -> list[Entity]:
        return [Entity("email", m.group(0), confidence=0.98, page_number=page)
                for m in _EMAIL_RE.finditer(text)]

    def _extract_phones(self, text: str, page: int | None) -> list[Entity]:
        result = []
        for m in _PHONE_RE.finditer(text):
            val = re.sub(r'\s+', '', m.group(1))
            if len(val) >= 7:
                result.append(Entity("phone", val, confidence=0.75, page_number=page))
        return result

    def _extract_dates(self, text: str, page: int | None) -> list[Entity]:
        return [Entity("date", m.group(0), confidence=0.85, page_number=page)
                for m in _DATE_RE.finditer(text)]

    def _extract_urls(self, text: str, page: int | None) -> list[Entity]:
        return [Entity("url", m.group(0), confidence=0.98, page_number=page)
                for m in _URL_RE.finditer(text)]

    def _extract_iban(self, text: str, page: int | None) -> list[Entity]:
        return [Entity("iban", m.group(0), confidence=0.92, page_number=page)
                for m in _IBAN_RE.finditer(text)]

    @staticmethod
    def _deduplicate(entities: list[Entity]) -> list[Entity]:
        seen: set[tuple[str, str]] = set()
        result = []
        for e in entities:
            key = (e.entity_type, e.value[:50])
            if key not in seen:
                seen.add(key)
                result.append(e)
        return result
