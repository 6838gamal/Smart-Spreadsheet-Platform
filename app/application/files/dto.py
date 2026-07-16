"""DTOs for file management."""

from pydantic import BaseModel
from datetime import datetime


class FileDTO(BaseModel):
    id: int
    name: str
    original_name: str
    size_bytes: int
    size_human: str
    format: str
    status: str
    is_favorite: bool
    tags: list[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class RenameFileDTO(BaseModel):
    new_name: str


class FileMetaDTO(BaseModel):
    rows: int | None = None
    columns: int | None = None
    sheets: list[str] | None = None
    encoding: str | None = None
    has_header: bool | None = None
