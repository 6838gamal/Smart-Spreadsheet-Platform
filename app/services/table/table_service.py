"""
Table Detection and Extraction Service.
Uses pdfplumber (primary) and img2table (image fallback).
Interface ready to plug in Table Transformer (TATR).
"""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CellData:
    row: int
    col: int
    value: str
    rowspan: int = 1
    colspan: int = 1


@dataclass
class TableData:
    page_number: int
    row_count: int
    col_count: int
    headers: list[str]
    cells: list[CellData]
    has_merged_cells: bool = False
    confidence: float = 0.8
    x1: float = 0.0
    y1: float = 0.0
    x2: float = 1.0
    y2: float = 1.0

    def to_dict_list(self) -> list[dict[str, str]]:
        """Convert to list of row dicts."""
        if not self.cells:
            return []
        rows: dict[int, dict[str, str]] = {}
        for cell in self.cells:
            row = rows.setdefault(cell.row, {})
            col_name = self.headers[cell.col] if cell.col < len(self.headers) else f"col_{cell.col}"
            row[col_name] = cell.value
        return [rows[r] for r in sorted(rows)]

    def to_nested_list(self) -> list[list[str]]:
        """Convert to 2D list."""
        if not self.cells:
            return []
        grid: dict[tuple[int, int], str] = {(c.row, c.col): c.value for c in self.cells}
        rows = range(self.row_count)
        cols = range(self.col_count)
        return [[grid.get((r, c), "") for c in cols] for r in rows]


class TableService:
    """Extract tables from PDFs and images."""

    def extract(self, file_path: str | Path) -> list[TableData]:
        path = Path(file_path)
        ext = path.suffix.lower()

        if ext == ".pdf":
            return self._extract_pdf(path)
        elif ext in {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"}:
            return self._extract_image(path)
        elif ext in {".xlsx", ".xls", ".csv", ".ods"}:
            return self._extract_spreadsheet(path)
        return []

    # ── PDF ──────────────────────────────────────────────────────────────────

    def _extract_pdf(self, path: Path) -> list[TableData]:
        tables: list[TableData] = []
        try:
            import pdfplumber
            with pdfplumber.open(str(path)) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    w = page.width or 1
                    h = page.height or 1
                    for pdf_table in (page.extract_tables() or []):
                        if not pdf_table:
                            continue
                        bbox_tables = page.find_tables()
                        bbox = bbox_tables[len(tables) % max(len(bbox_tables), 1)].bbox if bbox_tables else (0, 0, w, h)

                        # Determine headers from first row
                        first_row = [str(c or "").strip() for c in pdf_table[0]]
                        data_rows = pdf_table[1:] if len(pdf_table) > 1 else pdf_table

                        # Check if first row looks like headers
                        is_header = all(not str(c or "").strip().replace(".", "").replace(",", "").isdigit()
                                        for c in first_row if c)

                        if is_header:
                            headers = first_row
                            data_rows = pdf_table[1:]
                        else:
                            headers = [f"Column {i+1}" for i in range(len(first_row))]
                            data_rows = pdf_table

                        cells: list[CellData] = []
                        for r_idx, row in enumerate(data_rows):
                            for c_idx, val in enumerate(row):
                                cells.append(CellData(
                                    row=r_idx, col=c_idx,
                                    value=str(val or "").strip()
                                ))

                        tables.append(TableData(
                            page_number=page_num,
                            row_count=len(data_rows),
                            col_count=len(headers),
                            headers=headers,
                            cells=cells,
                            confidence=0.85,
                            x1=bbox[0] / w, y1=bbox[1] / h,
                            x2=bbox[2] / w, y2=bbox[3] / h,
                        ))
        except Exception as e:
            logger.warning("PDF table extraction failed for %s: %s", path, e)
        return tables

    # ── Image ─────────────────────────────────────────────────────────────────

    def _extract_image(self, path: Path) -> list[TableData]:
        tables: list[TableData] = []
        try:
            from img2table.document import Image as Img2Image
            from img2table.ocr import TesseractOCR
            import cv2

            ocr = TesseractOCR(lang="ara+eng")
            doc = Img2Image(src=str(path))
            extracted = doc.extract_tables(ocr=ocr, implicit_rows=True, borderless_tables=True)

            for table in extracted:
                df = table.df
                if df is None or df.empty:
                    continue
                headers = list(df.columns)
                cells = []
                for r_idx, row in df.iterrows():
                    for c_idx, val in enumerate(row):
                        cells.append(CellData(row=int(r_idx), col=c_idx, value=str(val or "").strip()))

                tables.append(TableData(
                    page_number=1,
                    row_count=len(df),
                    col_count=len(headers),
                    headers=[str(h) for h in headers],
                    cells=cells,
                    confidence=0.75,
                ))
        except Exception as e:
            logger.debug("Image table extraction failed: %s", e)
        return tables

    # ── Spreadsheet ───────────────────────────────────────────────────────────

    def _extract_spreadsheet(self, path: Path) -> list[TableData]:
        tables: list[TableData] = []
        try:
            import pandas as pd
            ext = path.suffix.lower()
            if ext == ".csv":
                dfs = {"Sheet1": pd.read_csv(str(path), nrows=1000)}
            elif ext in {".xlsx", ".xls"}:
                dfs = pd.read_excel(str(path), sheet_name=None, nrows=1000)
            else:
                return []

            for sheet_name, df in dfs.items():
                if df.empty:
                    continue
                headers = [str(c) for c in df.columns]
                cells = []
                for r_idx, row in df.iterrows():
                    for c_idx, val in enumerate(row):
                        cells.append(CellData(row=int(r_idx), col=c_idx, value=str(val if val == val else "").strip()))

                tables.append(TableData(
                    page_number=1,
                    row_count=len(df),
                    col_count=len(headers),
                    headers=headers,
                    cells=cells,
                    confidence=1.0,
                    meta={"sheet": sheet_name},
                ))
        except Exception as e:
            logger.warning("Spreadsheet table extraction failed: %s", e)
        return tables

    def export_to_excel(self, tables: list[TableData], output_path: str | Path) -> bool:
        """Export extracted tables to Excel, one sheet per table."""
        if not tables:
            return False
        try:
            import openpyxl
            wb = openpyxl.Workbook()
            wb.remove(wb.active)  # remove default sheet

            for i, table in enumerate(tables):
                ws = wb.create_sheet(title=f"Table_{i+1}_p{table.page_number}")
                if table.headers:
                    ws.append(table.headers)
                for row_dict in table.to_nested_list():
                    ws.append(row_dict)

            wb.save(str(output_path))
            return True
        except Exception as e:
            logger.warning("Excel export failed: %s", e)
            return False
