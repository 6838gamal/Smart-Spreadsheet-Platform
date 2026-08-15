"""
SQLAlchemy ORM models — all domain entities persisted here.
"""

import enum
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    BigInteger, Boolean, DateTime, Enum, Float, ForeignKey,
    Integer, String, Text, JSON, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ─── Enums ────────────────────────────────────────────────────────────────────

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"


class FileStatus(str, enum.Enum):
    UPLOADING = "uploading"
    READY = "ready"
    PROCESSING = "processing"
    ERROR = "error"


class OperationType(str, enum.Enum):
    UPLOAD = "upload"
    CONVERT = "convert"
    CLEAN = "clean"
    MERGE = "merge"
    COMPARE = "compare"
    FILTER = "filter"
    SORT = "sort"
    EXPORT = "export"
    DELETE = "delete"
    PREVIEW = "preview"


class OperationStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class AnalysisStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# ─── Models ───────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.USER)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    files: Mapped[list["File"]] = relationship("File", back_populates="owner", cascade="all, delete-orphan")
    operations: Mapped[list["OperationLog"]] = relationship("OperationLog", back_populates="user")
    chunks: Mapped[list["DocumentChunk"]] = relationship("DocumentChunk", back_populates="user", cascade="all, delete-orphan")

    @property
    def default_theme(self) -> str:
        return self.preferences.get("theme", "dark")

    @property
    def default_lang(self) -> str:
        return self.preferences.get("language", "ar")


class File(Base):
    __tablename__ = "files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    original_name: Mapped[str] = mapped_column(String(500), nullable=False)
    path: Mapped[str] = mapped_column(String(1000), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    format: Mapped[str] = mapped_column(String(50), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(200), default="application/octet-stream")
    status: Mapped[FileStatus] = mapped_column(Enum(FileStatus), default=FileStatus.READY)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    owner: Mapped["User"] = relationship("User", back_populates="files")
    operations: Mapped[list["OperationLog"]] = relationship("OperationLog", back_populates="file")
    analyses: Mapped[list["DocumentAnalysis"]] = relationship(
        "DocumentAnalysis", back_populates="file", cascade="all, delete-orphan"
    )
    suggestions: Mapped[list["AISuggestion"]] = relationship(
        "AISuggestion", back_populates="file", cascade="all, delete-orphan"
    )
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk", back_populates="file", cascade="all, delete-orphan"
    )

    @property
    def size_human(self) -> str:
        """Human-readable file size."""
        size = self.size_bytes
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    @property
    def extension(self) -> str:
        return self.format.lower().lstrip(".")


class OperationLog(Base):
    __tablename__ = "operation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    type: Mapped[OperationType] = mapped_column(Enum(OperationType), nullable=False)
    status: Mapped[OperationStatus] = mapped_column(Enum(OperationStatus), default=OperationStatus.PENDING)
    file_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("files.id"), nullable=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    input_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    output_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="operations")
    file: Mapped["File | None"] = relationship("File", back_populates="operations")


class ServerPing(Base):
    """Persisted record of every server/DB health-check ping."""
    __tablename__ = "server_pings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ok: Mapped[bool] = mapped_column(Boolean, nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detail: Mapped[str] = mapped_column(String(500), default="")
    pinged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    steps: Mapped[list] = mapped_column(JSON, default=list)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    run_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


# ─── Intelligence / Analysis Models ──────────────────────────────────────────

class DocumentAnalysis(Base):
    """تحليل المستندات - نتائج معالجة الذكاء الاصطناعي"""
    __tablename__ = "document_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    file_id: Mapped[int] = mapped_column(Integer, ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[AnalysisStatus] = mapped_column(Enum(AnalysisStatus), default=AnalysisStatus.PENDING)
    doc_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
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
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    # العلاقات
    file: Mapped["File"] = relationship("File", back_populates="analyses", foreign_keys=[file_id])
    extracted_tables: Mapped[list["ExtractedTable"]] = relationship(
        "ExtractedTable", back_populates="analysis", cascade="all, delete-orphan"
    )
    extracted_entities: Mapped[list["ExtractedEntity"]] = relationship(
        "ExtractedEntity", back_populates="analysis", cascade="all, delete-orphan"
    )
    suggestions: Mapped[list["AISuggestion"]] = relationship(
        "AISuggestion", back_populates="analysis", cascade="all, delete-orphan"
    )
    layout_elements: Mapped[list["LayoutElement"]] = relationship(
        "LayoutElement", back_populates="analysis", cascade="all, delete-orphan"
    )
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk", back_populates="analysis", cascade="all, delete-orphan"
    )


class ExtractedTable(Base):
    """جداول مستخرجة من المستندات"""
    __tablename__ = "extracted_tables"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    analysis_id: Mapped[int] = mapped_column(Integer, ForeignKey("document_analyses.id", ondelete="CASCADE"), nullable=False)
    layout_element_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("layout_elements.id"), nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    col_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    table_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    has_header: Mapped[bool] = mapped_column(Boolean, default=False)
    has_merged_cells: Mapped[bool] = mapped_column(Boolean, default=False)
    spans_pages: Mapped[bool] = mapped_column(Boolean, default=False)
    table_data: Mapped[list | None] = mapped_column(JSON, nullable=True)
    headers: Mapped[list | None] = mapped_column(JSON, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    excel_output_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # العلاقات
    analysis: Mapped["DocumentAnalysis"] = relationship("DocumentAnalysis", back_populates="extracted_tables")
    layout_element: Mapped["LayoutElement | None"] = relationship("LayoutElement", back_populates="extracted_tables")


class ExtractedEntity(Base):
    """كيانات مستخرجة من المستندات (أسماء، بريد، هاتف، إلخ)"""
    __tablename__ = "extracted_entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    analysis_id: Mapped[int] = mapped_column(Integer, ForeignKey("document_analyses.id", ondelete="CASCADE"), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
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

    # العلاقات
    analysis: Mapped["DocumentAnalysis"] = relationship("DocumentAnalysis", back_populates="extracted_entities")


class AISuggestion(Base):
    """اقتراحات ذكية من الذكاء الاصطناعي"""
    __tablename__ = "ai_suggestions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    file_id: Mapped[int] = mapped_column(Integer, ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    analysis_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("document_analyses.id", ondelete="CASCADE"), nullable=True)
    suggestion_type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    action_params: Mapped[dict] = mapped_column(JSON, default=dict)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # العلاقات
    file: Mapped["File"] = relationship("File", back_populates="suggestions", foreign_keys=[file_id])
    analysis: Mapped["DocumentAnalysis | None"] = relationship("DocumentAnalysis", back_populates="suggestions")


class LayoutElement(Base):
    """عناصر تخطيط المستند"""
    __tablename__ = "layout_elements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    analysis_id: Mapped[int] = mapped_column(Integer, ForeignKey("document_analyses.id", ondelete="CASCADE"), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    element_type: Mapped[str] = mapped_column(String(50), nullable=False)  # paragraph, header, table, image, etc.
    x1: Mapped[float] = mapped_column(Float, nullable=False)
    y1: Mapped[float] = mapped_column(Float, nullable=False)
    x2: Mapped[float] = mapped_column(Float, nullable=False)
    y2: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # العلاقات
    analysis: Mapped["DocumentAnalysis"] = relationship("DocumentAnalysis", back_populates="layout_elements")
    extracted_tables: Mapped[list["ExtractedTable"]] = relationship(
        "ExtractedTable", back_populates="layout_element", cascade="all, delete-orphan"
    )


class DocumentChunk(Base):
    """أجزاء المستند للبحث الدلالي"""
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    file_id: Mapped[int] = mapped_column(Integer, ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    analysis_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("document_analyses.id", ondelete="CASCADE"), nullable=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    doc_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # العلاقات
    file: Mapped["File"] = relationship("File", back_populates="chunks", foreign_keys=[file_id])
    analysis: Mapped["DocumentAnalysis | None"] = relationship("DocumentAnalysis", back_populates="chunks")
    user: Mapped["User"] = relationship("User", back_populates="chunks", foreign_keys=[user_id])
