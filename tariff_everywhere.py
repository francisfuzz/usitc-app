#!/usr/bin/env python3
"""Public Python API for programmatic access to HTS tariff data.

This module provides connection-managing wrapper functions around the lower-level
query helpers in ``hts_core.py`` so callers can perform lookups directly from
Python code without using the CLI or MCP server.
"""

from __future__ import annotations

from typing import TypedDict

import hts_core


class HTSEntry(TypedDict):
    """Programmatic representation of a tariff entry."""

    id: int
    hts_code: str
    indent: int
    description: str
    unit: str
    general_rate: str
    special_rate: str
    column2_rate: str
    chapter_id: int


class ChapterSummary(TypedDict):
    """Programmatic representation of a chapter summary."""

    number: str
    description: str
    entry_count: int
    last_checked_at: str | None
    last_changed_at: str | None


def search_hts(keyword: str, limit: int = 10, db_path: str | None = None) -> list[HTSEntry]:
    """Search HTS entries by keyword in the description field."""
    db = hts_core.get_db(db_path)
    try:
        return [hts_core.row_to_cli_dict(row) for row in hts_core.search_entries(db, keyword, limit=limit)]
    finally:
        db.close()


def lookup_code(code: str, db_path: str | None = None) -> HTSEntry | None:
    """Look up a single HTS code and return it as a dictionary."""
    db = hts_core.get_db(db_path)
    try:
        row = hts_core.get_entry(db, code)
        return hts_core.row_to_cli_dict(row) if row else None
    finally:
        db.close()


def list_chapter(chapter_num: str | int, db_path: str | None = None) -> list[HTSEntry]:
    """List all HTS entries in a chapter."""
    db = hts_core.get_db(db_path)
    try:
        return [hts_core.row_to_cli_dict(row) for row in hts_core.list_chapter_entries(db, str(chapter_num))]
    finally:
        db.close()


def get_chapters(db_path: str | None = None) -> list[ChapterSummary]:
    """Return all chapters with descriptions, entry counts, and freshness timestamps."""
    db = hts_core.get_db(db_path)
    try:
        return [
            {
                "number": row[0],
                "description": row[1] or "",
                "entry_count": row[2],
                "last_checked_at": row[3],
                "last_changed_at": row[4],
            }
            for row in hts_core.get_all_chapters(db)
        ]
    finally:
        db.close()


__all__ = ["ChapterSummary", "HTSEntry", "get_chapters", "list_chapter", "lookup_code", "search_hts"]
