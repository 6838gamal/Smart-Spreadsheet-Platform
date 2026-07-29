"""
Smart Cleaning Service.
Normalizes dates, currencies, numbers; removes duplicates and empty rows;
detects anomalies; suggests column names.
"""
from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Arabic-Indic digits → Western
_ARABIC_INDIC = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')

# Month name → number
_MONTH_MAP = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
    'يناير': 1, 'فبراير': 2, 'مارس': 3, 'أبريل': 4, 'مايو': 5, 'يونيو': 6,
    'يوليو': 7, 'أغسطس': 8, 'سبتمبر': 9, 'أكتوبر': 10, 'نوفمبر': 11, 'ديسمبر': 12,
}


@dataclass
class CleaningStats:
    removed_empty_rows: int = 0
    removed_duplicates: int = 0
    normalized_dates: int = 0
    normalized_numbers: int = 0
    normalized_currencies: int = 0
    anomalies_flagged: int = 0
    columns_renamed: int = 0


@dataclass
class CleaningResult:
    data: list[dict[str, Any]]
    stats: CleaningStats
    warnings: list[str] = field(default_factory=list)
    suggested_column_names: dict[str, str] = field(default_factory=dict)


class CleaningService:
    """Apply a configurable set of cleaning rules to tabular data."""

    def clean(
        self,
        rows: list[dict[str, Any]],
        rules: list[str] | None = None,
    ) -> CleaningResult:
        """
        Apply cleaning rules to a list of row dicts.
        rules: subset of ['remove_empty', 'remove_duplicates', 'normalize_dates',
                           'normalize_numbers', 'normalize_currencies', 'detect_anomalies']
        If None, all rules are applied.
        """
        if rules is None:
            rules = [
                "remove_empty", "remove_duplicates", "normalize_dates",
                "normalize_numbers", "normalize_currencies", "detect_anomalies",
            ]

        stats = CleaningStats()
        warnings: list[str] = []
        data = [dict(r) for r in rows]  # copy

        if "remove_empty" in rules:
            before = len(data)
            data = [r for r in data if any(str(v).strip() for v in r.values())]
            stats.removed_empty_rows = before - len(data)

        if "remove_duplicates" in rules:
            before = len(data)
            seen: set[str] = set()
            unique = []
            for row in data:
                key = str(sorted(row.items()))
                if key not in seen:
                    seen.add(key)
                    unique.append(row)
            data = unique
            stats.removed_duplicates = before - len(data)

        if "normalize_dates" in rules:
            for row in data:
                for k, v in row.items():
                    normalized = self._normalize_date(str(v))
                    if normalized and normalized != str(v):
                        row[k] = normalized
                        stats.normalized_dates += 1

        if "normalize_numbers" in rules:
            for row in data:
                for k, v in row.items():
                    normalized = self._normalize_number(str(v))
                    if normalized is not None and str(normalized) != str(v):
                        row[k] = normalized
                        stats.normalized_numbers += 1

        if "normalize_currencies" in rules:
            for row in data:
                for k, v in row.items():
                    normalized = self._normalize_currency(str(v))
                    if normalized and normalized != str(v):
                        row[k] = normalized
                        stats.normalized_currencies += 1

        if "detect_anomalies" in rules and data:
            flagged = self._detect_anomalies(data)
            stats.anomalies_flagged = flagged
            if flagged:
                warnings.append(f"{flagged} potential anomalies detected (marked with __anomaly__ flag)")

        suggested = self._suggest_column_names(data) if data else {}

        return CleaningResult(data=data, stats=stats, warnings=warnings, suggested_column_names=suggested)

    # ── Normalizers ───────────────────────────────────────────────────────────

    def _normalize_date(self, value: str) -> str | None:
        """Convert various date formats to YYYY-MM-DD."""
        value = value.strip().translate(_ARABIC_INDIC)

        # Already ISO
        if re.match(r'^\d{4}-\d{2}-\d{2}$', value):
            return value

        # DD/MM/YYYY or DD-MM-YYYY or DD.MM.YYYY
        m = re.match(r'^(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{2,4})$', value)
        if m:
            d, mo, y = m.groups()
            y = f"20{y}" if len(y) == 2 else y
            try:
                return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
            except ValueError:
                pass

        # YYYY/MM/DD
        m = re.match(r'^(\d{4})[\/\-\.](\d{1,2})[\/\-\.](\d{1,2})$', value)
        if m:
            y, mo, d = m.groups()
            try:
                return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
            except ValueError:
                pass

        # "15 Jan 2023" or "15 يناير 2023"
        m = re.match(r'^(\d{1,2})\s+([A-Za-z\u0600-\u06FF]+)\.?\s+(\d{2,4})$', value, re.IGNORECASE)
        if m:
            d, mon_str, y = m.groups()
            mon = _MONTH_MAP.get(mon_str.lower()[:3])
            if not mon:
                mon = _MONTH_MAP.get(mon_str)
            if mon:
                y = f"20{y}" if len(y) == 2 else y
                try:
                    return f"{int(y):04d}-{mon:02d}-{int(d):02d}"
                except ValueError:
                    pass

        return None

    def _normalize_number(self, value: str) -> float | int | None:
        """Convert localized numbers to standard float/int."""
        v = value.strip().translate(_ARABIC_INDIC)
        # Remove thousands separators
        v = re.sub(r'(?<=\d)[,،](?=\d{3})', '', v)
        try:
            f = float(v)
            return int(f) if f == int(f) else f
        except ValueError:
            return None

    def _normalize_currency(self, value: str) -> str | None:
        """Normalize currency strings: '$1,234.50' → '1234.50 USD'"""
        v = value.strip()
        # Symbol at start
        m = re.match(r'^([\$€£])\s*([\d,\.]+)$', v)
        if m:
            sym, amount = m.groups()
            sym_map = {'$': 'USD', '€': 'EUR', '£': 'GBP'}
            amount_clean = re.sub(r',', '', amount)
            return f"{amount_clean} {sym_map[sym]}"
        # Code at end
        m = re.match(r'^([\d,\.]+)\s*(USD|EUR|GBP|SAR|AED|KWD|EGP|دولار|يورو|ريال|درهم|دينار|جنيه)$', v, re.IGNORECASE)
        if m:
            amount, code = m.groups()
            amount_clean = re.sub(r',', '', amount)
            return f"{amount_clean} {code.upper()}"
        return None

    def _detect_anomalies(self, data: list[dict]) -> int:
        """Flag statistical outliers in numeric columns using IQR."""
        if len(data) < 4:
            return 0

        flagged = 0
        # Gather numeric columns
        numeric_cols: dict[str, list[float]] = {}
        for row in data:
            for k, v in row.items():
                try:
                    numeric_cols.setdefault(k, []).append(float(str(v).replace(',', '')))
                except (ValueError, TypeError):
                    pass

        for col, values in numeric_cols.items():
            if len(values) < 4:
                continue
            sorted_v = sorted(values)
            q1 = sorted_v[len(sorted_v) // 4]
            q3 = sorted_v[3 * len(sorted_v) // 4]
            iqr = q3 - q1
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr

            for row in data:
                try:
                    val = float(str(row.get(col, "")).replace(',', ''))
                    if val < lower or val > upper:
                        row[f"__anomaly_{col}__"] = True
                        flagged += 1
                except (ValueError, TypeError):
                    pass

        return flagged

    def _suggest_column_names(self, data: list[dict]) -> dict[str, str]:
        """Suggest better column names based on content patterns."""
        if not data:
            return {}
        suggestions: dict[str, str] = {}
        sample = data[:20]

        for col in sample[0].keys():
            values = [str(r.get(col, "")) for r in sample if r.get(col)]
            if not values:
                continue

            # Check patterns
            if all(_EMAIL_RE_CHK.match(v) for v in values[:5] if v):
                suggestions[col] = "email"
            elif all(re.match(r'^\+?[\d\s\-]{7,16}$', v) for v in values[:5] if v):
                suggestions[col] = "phone"
            elif all(re.match(r'^\d{4}-\d{2}-\d{2}$', v) for v in values[:5] if v):
                suggestions[col] = "date"
            elif all(re.match(r'^[\d,\.]+$', v) for v in values[:5] if v):
                suggestions[col] = "amount"

        return suggestions


_EMAIL_RE_CHK = re.compile(r'^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$')
