"""Read-only SQLite query layer built from the inspected PBS Table 1 workbook."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from tds.ingestion.table_01 import parse_table_01


SCHEMA = """
CREATE TABLE geography_catalog (
  name TEXT PRIMARY KEY,
  geography_type TEXT NOT NULL CHECK (geography_type IN ('country', 'province'))
);
CREATE TABLE school_participation (
  source_row INTEGER PRIMARY KEY,
  geography TEXT NOT NULL REFERENCES geography_catalog(name),
  area_type TEXT,
  gender TEXT,
  ever_attended_pct REAL NOT NULL CHECK (ever_attended_pct BETWEEN 0 AND 100),
  completed_primary_pct REAL NOT NULL CHECK (completed_primary_pct BETWEEN 0 AND 100),
  out_of_school_pct REAL NOT NULL CHECK (out_of_school_pct BETWEEN 0 AND 100)
);
"""


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def create_database() -> sqlite3.Connection:
    """Create a fresh, read-only-by-convention analytical database."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    source = project_root() / "edu" / (
        "Table-1-Population-10-Year-and-older-that-has-Ever-Attended-School-"
        "completed-primary-and-out-of-school-by-Province-Region-and-Gender.xlsx"
    )
    rows = parse_table_01(source)
    conn.executemany(
        "INSERT INTO geography_catalog VALUES (?, ?)",
        [(name, "country" if name == "Pakistan" else "province") for name in sorted({r.geography_name for r in rows})],
    )
    conn.executemany(
        """INSERT INTO school_participation VALUES (?, ?, ?, ?, ?, ?, ?)""",
        [
            (
                row.worksheet_row_number, row.geography_name, row.area_type,
                row.gender, float(row.ever_attended_pct),
                float(row.completed_primary_pct), float(row.out_of_school_pct),
            )
            for row in rows
        ],
    )
    return conn
