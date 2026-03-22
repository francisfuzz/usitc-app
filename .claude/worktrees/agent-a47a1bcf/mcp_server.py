#!/usr/bin/env python3
"""MCP server exposing HTS tariff data as tools."""

import sqlite3
import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("hts")

DB_PATH = Path("data/hts.db")


def get_db() -> sqlite3.Connection:
    """Get database connection."""
    if not DB_PATH.exists():
        raise FileNotFoundError("data/hts.db not found. Run ingest first.")
    return sqlite3.connect(str(DB_PATH))


@mcp.tool()
def search_hts(keyword: str, limit: int = 10) -> str:
    """Search HTS entries by keyword in description."""
    db = get_db()
    try:
        cursor = db.cursor()
        cursor.execute(
            """SELECT hts_code, description, unit, general_rate, special_rate, column2_rate
               FROM hts_entries
               WHERE description LIKE ?
               LIMIT ?""",
            (f"%{keyword}%", limit),
        )
        rows = cursor.fetchall()
        results = [
            {
                "hts_code": r[0],
                "description": r[1],
                "unit": r[2] or "",
                "general_rate": r[3] or "",
                "special_rate": r[4] or "",
                "column2_rate": r[5] or "",
            }
            for r in rows
        ]
        return json.dumps(results, indent=2)
    finally:
        db.close()


@mcp.tool()
def get_code(hts_code: str) -> str:
    """Get details for a specific HTS code."""
    db = get_db()
    try:
        cursor = db.cursor()
        cursor.execute(
            """SELECT hts_code, description, unit, general_rate, special_rate, column2_rate
               FROM hts_entries
               WHERE hts_code = ?
               LIMIT 1""",
            (hts_code,),
        )
        row = cursor.fetchone()
        if not row:
            return json.dumps({"error": f"HTS code '{hts_code}' not found"})
        result = {
            "hts_code": row[0],
            "description": row[1],
            "unit": row[2] or "",
            "general_rate": row[3] or "",
            "special_rate": row[4] or "",
            "column2_rate": row[5] or "",
        }
        return json.dumps(result, indent=2)
    finally:
        db.close()


@mcp.tool()
def list_chapter(chapter: str) -> str:
    """List all HTS entries in a chapter."""
    db = get_db()
    try:
        cursor = db.cursor()
        chapter_padded = chapter.zfill(2)
        cursor.execute(
            """SELECT hts_code, description, unit, general_rate, special_rate, column2_rate
               FROM hts_entries
               WHERE hts_code LIKE ?
               ORDER BY hts_code""",
            (f"{chapter_padded}%",),
        )
        rows = cursor.fetchall()
        results = [
            {
                "hts_code": r[0],
                "description": r[1],
                "unit": r[2] or "",
                "general_rate": r[3] or "",
                "special_rate": r[4] or "",
                "column2_rate": r[5] or "",
            }
            for r in rows
        ]
        return json.dumps(results, indent=2)
    finally:
        db.close()


@mcp.tool()
def get_chapters() -> str:
    """Get all chapters with their descriptions and entry counts."""
    db = get_db()
    try:
        cursor = db.cursor()
        cursor.execute(
            """SELECT c.number, c.description, COUNT(h.id) as entry_count
               FROM chapters c
               LEFT JOIN hts_entries h ON c.id = h.chapter_id
               GROUP BY c.id
               ORDER BY c.number"""
        )
        rows = cursor.fetchall()
        results = [
            {
                "number": r[0],
                "description": r[1] or "",
                "entry_count": r[2],
            }
            for r in rows
        ]
        return json.dumps(results, indent=2)
    finally:
        db.close()


if __name__ == "__main__":
    mcp.run(transport="stdio")
