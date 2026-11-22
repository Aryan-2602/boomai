"""Read the student CSV into plain dicts.

Blank cells become None (never 0 or NaN), so a missing LMS login count is
distinguishable from a real zero. The literal string "None" (used by
aid_hold_type) is kept as-is; it is a value, not a blank.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

DATE_FIELDS = (
    "lms_last_login",
    "aid_hold_since",
    "last_advisor_contact",
    "last_outreach_date",
)
INT_FIELDS = (
    "units_enrolled",
    "term_number",
    "lms_logins_last_14_days",
    "missing_assignments",
)
FLOAT_FIELDS = ("cumulative_gpa",)

Student = dict[str, Any]


def _blank_to_none(value: str) -> str | None:
    value = value.strip()
    return value or None


def _parse_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def _parse_int(value: str | None) -> int | None:
    return int(value) if value else None


def _parse_float(value: str | None) -> float | None:
    return float(value) if value else None


def parse_row(raw: dict[str, str]) -> Student:
    row: Student = {key: _blank_to_none(val) for key, val in raw.items()}
    for field in DATE_FIELDS:
        row[field] = _parse_date(row.get(field))
    for field in INT_FIELDS:
        row[field] = _parse_int(row.get(field))
    for field in FLOAT_FIELDS:
        row[field] = _parse_float(row.get(field))
    return row


def load_students(csv_path: str | Path) -> list[Student]:
    # dtype=str + keep_default_na=False: pandas must not turn "" or "None"
    # into NaN; we decide what counts as missing ourselves.
    df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    return [parse_row(raw) for raw in df.to_dict(orient="records")]
