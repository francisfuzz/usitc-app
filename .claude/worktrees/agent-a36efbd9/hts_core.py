#!/usr/bin/env python3
"""Core HTS lookup library — shared by CLI, MCP server, and any future interface."""

import os
import sqlite3
from pathlib import Path
from typing import Optional


DEFAULT_DB_PATH = "data/hts.db"


def get_db(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Get a database connection.

    Uses db_path if provided, otherwise checks HTS_DB_PATH env var,
    otherwise falls back to data/hts.db.

    Raises FileNotFoundError if the database file does not exist.
    """
    path = Path(db_path or os.getenv("HTS_DB_PATH", DEFAULT_DB_PATH))
    if not path.exists():
        raise FileNotFoundError(f"{path} not found. Run ingest first.")
    return sqlite3.connect(str(path))


# Column list for the 9-column SELECT used by CLI
CLI_COLUMNS = [
    "id", "hts_code", "indent", "description", "unit",
    "general_rate", "special_rate", "column2_rate", "chapter_id",
]

# Column list for the 6-column SELECT used by MCP
MCP_COLUMNS = [
    "hts_code", "description", "unit",
    "general_rate", "special_rate", "column2_rate",
]

CLI_SELECT = f"SELECT {', '.join(CLI_COLUMNS)} FROM hts_entries"
MCP_SELECT = f"SELECT {', '.join(MCP_COLUMNS)} FROM hts_entries"


def _row_to_dict(row: tuple, columns: list) -> dict:
    """Convert a database row to a dictionary using the given column names."""
    return dict(zip(columns, row))


def row_to_cli_dict(row: tuple) -> dict:
    """Convert a 9-column CLI row to a dictionary."""
    return _row_to_dict(row, CLI_COLUMNS)


def row_to_mcp_dict(row: tuple) -> dict:
    """Convert a 6-column MCP row to a dictionary, replacing None with empty string."""
    d = _row_to_dict(row, MCP_COLUMNS)
    return {k: (v if v is not None else "") for k, v in d.items()}


def search_entries(db: sqlite3.Connection, keyword: str, limit: int = 10, columns: str = None) -> list:
    """Search HTS entries by keyword in description."""
    select = columns or CLI_SELECT
    cursor = db.cursor()
    cursor.execute(
        f"{select} WHERE description LIKE ? LIMIT ?",
        (f"%{keyword}%", limit),
    )
    return cursor.fetchall()


def get_entry(db: sqlite3.Connection, hts_code: str, columns: str = None) -> Optional[tuple]:
    """Get a single HTS entry by exact code."""
    select = columns or CLI_SELECT
    cursor = db.cursor()
    cursor.execute(f"{select} WHERE hts_code = ? LIMIT 1", (hts_code,))
    return cursor.fetchone()


def list_chapter_entries(db: sqlite3.Connection, chapter: str, columns: str = None) -> list:
    """List all entries in a chapter."""
    select = columns or CLI_SELECT
    chapter_padded = chapter.zfill(2)
    cursor = db.cursor()
    cursor.execute(
        f"{select} WHERE hts_code LIKE ? ORDER BY hts_code",
        (f"{chapter_padded}%",),
    )
    return cursor.fetchall()


def get_all_chapters(db: sqlite3.Connection) -> list:
    """Get all chapters with descriptions and entry counts."""
    cursor = db.cursor()
    cursor.execute(
        """SELECT c.number, c.description, COUNT(h.id) as entry_count
           FROM chapters c
           LEFT JOIN hts_entries h ON c.id = h.chapter_id
           GROUP BY c.id
           ORDER BY c.number"""
    )
    return cursor.fetchall()
