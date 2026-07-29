"""
AI Suggestions Engine.
After document analysis, generates contextual action suggestions for the user.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Suggestion:
    suggestion_type: str
    title: str
    title_ar: str
    description: str
    priority: int
    action_params: dict[str, Any]
    icon: str = "sparkles"


class SuggestionEngine:

    def generate(
        self,
        doc_type: str,
        has_tables: bool,
        has_images: bool,
        raw_text: str,
        entities: list[dict],
        file_id: int,
        file_format: str = "",
    ) -> list[Suggestion]:
        suggestions: list[Suggestion] = []
        text_lower = raw_text.lower() if raw_text else ""

        # ── Tables ────────────────────────────────────────────────────────────
        if has_tables:
            suggestions.append(Suggestion(
                suggestion_type="extract_tables",
                title="Extract tables to Excel",
                title_ar="استخراج الجداول إلى Excel",
                description="Found tables in this document — export them as a structured Excel file.",
                priority=1,
                action_params={"action": "extract_tables", "file_id": file_id},
                icon="table-cells",
            ))

        # ── PDF conversion ─────────────────────────────────────────────────────
        if file_format.lower() == "pdf":
            suggestions.append(Suggestion(
                suggestion_type="convert_excel",
                title="Convert to Excel",
                title_ar="تحويل إلى Excel",
                description="Convert this PDF to an editable Excel spreadsheet.",
                priority=2,
                action_params={"action": "convert", "target": "xlsx", "file_id": file_id},
                icon="document-arrow-down",
            ))
            suggestions.append(Suggestion(
                suggestion_type="convert_word",
                title="Convert to Word",
                title_ar="تحويل إلى Word",
                description="Convert this PDF to an editable Word document.",
                priority=3,
                action_params={"action": "convert", "target": "docx", "file_id": file_id},
                icon="document-text",
            ))

        # ── Emails ────────────────────────────────────────────────────────────
        email_entities = [e for e in entities if e.get("entity_type") == "email"]
        if email_entities:
            suggestions.append(Suggestion(
                suggestion_type="extract_emails",
                title=f"Export {len(email_entities)} email address(es)",
                title_ar=f"تصدير {len(email_entities)} بريد إلكتروني",
                description="Email addresses were detected — export them as CSV.",
                priority=4,
                action_params={"action": "export_entities", "entity_type": "email", "file_id": file_id},
                icon="envelope",
            ))

        # ── Phones ────────────────────────────────────────────────────────────
        phone_entities = [e for e in entities if e.get("entity_type") == "phone"]
        if phone_entities:
            suggestions.append(Suggestion(
                suggestion_type="extract_phones",
                title=f"Export {len(phone_entities)} phone number(s)",
                title_ar=f"تصدير {len(phone_entities)} رقم هاتف",
                description="Phone numbers were detected — export them as CSV.",
                priority=5,
                action_params={"action": "export_entities", "entity_type": "phone", "file_id": file_id},
                icon="phone",
            ))

        # ── Invoice data ──────────────────────────────────────────────────────
        if doc_type == "invoice":
            suggestions.append(Suggestion(
                suggestion_type="export_invoice_json",
                title="Export invoice data as JSON",
                title_ar="تصدير بيانات الفاتورة بصيغة JSON",
                description="Export structured invoice fields (number, supplier, total, etc.) as JSON.",
                priority=1,
                action_params={"action": "export_entities", "entity_type": "all", "format": "json", "file_id": file_id},
                icon="code-bracket",
            ))

        # ── Resume ────────────────────────────────────────────────────────────
        if doc_type == "resume":
            suggestions.append(Suggestion(
                suggestion_type="export_cv_json",
                title="Export CV data as JSON",
                title_ar="تصدير بيانات السيرة الذاتية",
                description="Extract name, email, phone, skills and experience as structured JSON.",
                priority=1,
                action_params={"action": "export_entities", "entity_type": "all", "format": "json", "file_id": file_id},
                icon="user",
            ))

        # ── Clean data ────────────────────────────────────────────────────────
        if has_tables or doc_type in {"spreadsheet", "bank_statement"}:
            suggestions.append(Suggestion(
                suggestion_type="clean_data",
                title="Clean and normalize data",
                title_ar="تنظيف البيانات وتوحيدها",
                description="Remove empty rows, normalize dates and numbers.",
                priority=6,
                action_params={"action": "clean", "file_id": file_id},
                icon="sparkles",
            ))

        # ── Search ────────────────────────────────────────────────────────────
        if raw_text and len(raw_text) > 200:
            suggestions.append(Suggestion(
                suggestion_type="search_document",
                title="Search within this document",
                title_ar="البحث داخل هذا المستند",
                description="Use full-text search to find anything in this document.",
                priority=7,
                action_params={"action": "search", "file_id": file_id},
                icon="magnifying-glass",
            ))

        return sorted(suggestions, key=lambda s: s.priority)
