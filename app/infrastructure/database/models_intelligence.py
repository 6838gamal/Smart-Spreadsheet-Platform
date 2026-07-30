"""
SQLAlchemy ORM models for Document Intelligence features.
These models extend the base platform without modifying existing tables.
"""

import enum
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    BigInteger, Boolean, DateTime, Enum, Float, ForeignKey,
    Integer, SmallInteger, String, Text, JSON, Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.infrastructure.database.models import utcnow


# ─── Enums ────────────────────────────────────────────────────────────────────

class AnalysisStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentType(str, enum.Enum):
    INVOICE = "invoice"
    RECEIPT = "receipt"
    BANK_STATEMENT = "bank_statement"
    RESUME = "resume"
    CONTRACT = "contract"
    PASSPORT = "passport"
    ID = "id"
    MEDICAL_REPORT = "medical_report"
    SCHOOL_REPORT = "school_report"
    BOOK = "book"
    RESEARCH_PAPER = "research_paper"
    FORM = "form"
    CERTIFICATE = "certificate"
    SPREADSHEET = "spreadsheet"
    PRESENTATION = "presentation"
    REPORT = "report"
    LETTER = "letter"
    UNKNOWN = "unknown"


class ElementType(str, enum.Enum):
    PARAGRAPH = "paragraph"
    HEADER = "header"
    FOOTER = "footer"
    TABLE = "table"
    IMAGE = "image"
    CHART = "chart"
    LOGO = "logo"
    SIGNATURE = "signature"
    QR_CODE = "qr_code"
    BARCODE = "barcode"
    LIST = "list"
    PAGE_NUMBER = "page_number"
    TITLE = "title"
    CAPTION = "caption"
    OTHER = "other"


class JobType(str, enum.Enum):
    ANALYSIS = "analysis"
    OCR = "ocr"
    CLASSIFICATION = "classification"
    LAYOUT = "layout"
    TABLE = "table"
    NER = "ner"
    CLEANING = "cleaning"
    EMBEDDING = "embedding"
    TRAINING = "training"
    EXPORT = "export"


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ModelType(str, enum.Enum):
    OCR = "ocr"
    CLASSIFICATION = "classification"
    NER = "ner"
    LAYOUT = "layout"
    TABLE = "table"
    EMBEDDING = "embedding"
    CLEANING = "cleaning"


class FeedbackType(str, enum.Enum):
    ENTITY_CORRECTION = "entity_correction"
    TABLE_CORRECTION = "table_correction"
    CLASSIFICATION_CORRECTION = "classification_correction"
    OCR_CORRECTION = "ocr_correction"
    RATING = "rating"


class DatasetType(str, enum.Enum):
    OCR = "ocr"
    CLASSIFICATION = "classification"
    NER = "ner"
    LAYOUT = "layout"
    TABLE = "table"


class TrainingStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ─── Models ───────────────────────────────────────────────────────────────────

class DocumentAnalysis(Base):
    """Full analysis result for a document."""
    __tablename__ = "document_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    file_id: Mapped[int] = mapped_column(Integer, ForeignKey("files.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[AnalysisStatus] = mapped_column(Enum(AnalysisStatus), default=AnalysisStatus.PENDING, nullable=False)
    doc_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    doc_type_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    has_tables: Mapped[bool] = mapped_column(Boolean, default=False)
    has_images: Mapped[bool] = mapped_column(Boolean, default=False)
    has_handwriting: Mapped[bool] = mapped_column(Boolean, default=False)
    layout_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    processing_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    pipeline_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_versions: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    layout_elements: Mapped[list["LayoutElement"]] = relationship(
        "LayoutElement", back_populates="analysis", cascade="all, delete-orphan"
    )
    extracted_tables: Mapped[list["ExtractedTable"]] = relationship(
        "ExtractedTable", back_populates="analysis", cascade="all, delete-orphan"
    )
    extracted_entities: Mapped[list["ExtractedEntity"]] = relationship(
        "ExtractedEntity", back_populates="analysis", cascade="all, delete-orphan"
    )
    suggestions: Mapped[list["AISuggestion"]] = relationship(
        "AISuggestion", back_populates="analysis", cascade="all, delete-orphan"
    )


class LayoutElement(Base):
    """A detected region on a document page."""
    __tablename__ = "layout_elements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    analysis_id: Mapped[int] = mapped_column(Integer, ForeignKey("document_analyses.id", ondelete="CASCADE"), nullable=False, index=True)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    element_type: Mapped[str] = mapped_column(String(30), nullable=False)
    x1: Mapped[float | None] = mapped_column(Float, nullable=True)
    y1: Mapped[float | None] = mapped_column(Float, nullable=True)
    x2: Mapped[float | None] = mapped_column(Float, nullable=True)
    y2: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    analysis: Mapped["DocumentAnalysis"] = relationship("DocumentAnalysis", back_populates="layout_elements")


class ExtractedTable(Base):
    """A table extracted from a document."""
    __tablename__ = "extracted_tables"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    analysis_id: Mapped[int] = mapped_column(Integer, ForeignKey("document_analyses.id", ondelete="CASCADE"), nullable=False, index=True)
    layout_element_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("layout_elements.id"), nullable=True)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    col_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    has_header: Mapped[bool] = mapped_column(Boolean, default=True)
    has_merged_cells: Mapped[bool] = mapped_column(Boolean, default=False)
    spans_pages: Mapped[bool] = mapped_column(Boolean, default=False)
    table_data: Mapped[list] = mapped_column(JSON, default=list)
    headers: Mapped[list | None] = mapped_column(JSON, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    excel_output_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    analysis: Mapped["DocumentAnalysis"] = relationship("DocumentAnalysis", back_populates="extracted_tables")


class ExtractedEntity(Base):
    """A named entity extracted from a document."""
    __tablename__ = "extracted_entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    analysis_id: Mapped[int] = mapped_column(Integer, ForeignKey("document_analyses.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    x1: Mapped[float | None] = mapped_column(Float, nullable=True)
    y1: Mapped[float | None] = mapped_column(Float, nullable=True)
    x2: Mapped[float | None] = mapped_column(Float, nullable=True)
    y2: Mapped[float | None] = mapped_column(Float, nullable=True)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    corrected_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    analysis: Mapped["DocumentAnalysis"] = relationship("DocumentAnalysis", back_populates="extracted_entities")


class AISuggestion(Base):
    """AI-generated action suggestion for a file."""
    __tablename__ = "ai_suggestions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    file_id: Mapped[int] = mapped_column(Integer, ForeignKey("files.id", ondelete="CASCADE"), nullable=False, index=True)
    analysis_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("document_analyses.id", ondelete="CASCADE"), nullable=True)
    suggestion_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_params: Mapped[dict] = mapped_column(JSON, default=dict)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    accepted: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    analysis: Mapped["DocumentAnalysis | None"] = relationship("DocumentAnalysis", back_populates="suggestions")


class UserFeedback(Base):
    """User corrections and ratings."""
    __tablename__ = "user_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    file_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("files.id"), nullable=True)
    analysis_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("document_analyses.id"), nullable=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("extracted_entities.id"), nullable=True)
    feedback_type: Mapped[str] = mapped_column(String(30), nullable=False)
    original_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    corrected_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    doc_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    rating: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    used_in_training: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AIModelRegistry(Base):
    """Registry of all AI models (local and remote)."""
    __tablename__ = "ai_model_registry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    model_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(30), nullable=False)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)  # huggingface | local | builtin
    model_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    hf_model_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    size_mb: Mapped[float | None] = mapped_column(Float, nullable=True)
    languages: Mapped[list] = mapped_column(JSON, default=list)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    loaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Dataset(Base):
    """Training dataset."""
    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    dataset_type: Mapped[str] = mapped_column(String(30), nullable=False)
    version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="building")
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    split_train: Mapped[float] = mapped_column(Float, default=0.8)
    split_val: Mapped[float] = mapped_column(Float, default=0.1)
    split_test: Mapped[float] = mapped_column(Float, default=0.1)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    samples: Mapped[list["DatasetSample"]] = relationship(
        "DatasetSample", back_populates="dataset", cascade="all, delete-orphan"
    )


class DatasetSample(Base):
    """A single training sample."""
    __tablename__ = "dataset_samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    dataset_id: Mapped[int] = mapped_column(Integer, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    file_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("files.id"), nullable=True)
    analysis_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("document_analyses.id"), nullable=True)
    feedback_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("user_feedback.id"), nullable=True)
    split: Mapped[str] = mapped_column(String(10), default="train")
    input_path: Mapped[str] = mapped_column(Text, nullable=False)
    output_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    labels: Mapped[dict] = mapped_column(JSON, default=dict)
    bounding_boxes: Mapped[list | None] = mapped_column(JSON, nullable=True)
    doc_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    ocr_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    entities: Mapped[list | None] = mapped_column(JSON, nullable=True)
    corrections: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    training_status: Mapped[str] = mapped_column(String(20), default="pending")
    version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    dataset: Mapped["Dataset"] = relationship("Dataset", back_populates="samples")


class DocumentChunk(Base):
    """
    A text chunk extracted from a processed document, used for BM25 / embedding search.

    Phase 1: chunk_text only (no vector). embedding field added in Phase 2.
    """
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    file_id: Mapped[int] = mapped_column(Integer, ForeignKey("files.id", ondelete="CASCADE"), nullable=False, index=True)
    analysis_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("document_analyses.id", ondelete="SET NULL"), nullable=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str | None] = mapped_column(String(500), nullable=True)
    doc_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    # Phase 2: add embedding JSON column here (vector stored as list[float])
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProcessingJob(Base):
    """Internal async job queue."""
    __tablename__ = "processing_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("files.id"), nullable=True)
    analysis_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("document_analyses.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued", index=True)
    priority: Mapped[int] = mapped_column(SmallInteger, default=5)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(SmallInteger, default=0)
    max_retries: Mapped[int] = mapped_column(SmallInteger, default=3)
    worker_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_processing_jobs_status_priority", "status", "priority", "queued_at"),
    )


class TrainingExperiment(Base):
    """Fine-tuning experiment."""
    __tablename__ = "training_experiments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    model_type: Mapped[str] = mapped_column(String(30), nullable=False)
    base_model_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("ai_model_registry.id"), nullable=True)
    dataset_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("datasets.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    hyperparams: Mapped[dict] = mapped_column(JSON, default=dict)
    metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    best_metric: Mapped[float | None] = mapped_column(Float, nullable=True)
    epochs_run: Mapped[int] = mapped_column(Integer, default=0)
    total_epochs: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_model_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("ai_model_registry.id"), nullable=True)
    log_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
