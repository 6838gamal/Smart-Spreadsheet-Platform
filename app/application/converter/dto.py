"""DTOs for the conversion module."""

from pydantic import BaseModel


class ConvertRequestDTO(BaseModel):
    file_id: int
    target_format: str
    sheet: str | None = None          # single-sheet (legacy)
    sheets: list[str] | None = None   # multi-sheet selection
    options: dict = {}


class ConvertResultDTO(BaseModel):
    output_path: str
    output_filename: str
    rows: int
    columns: int
    duration_ms: int
