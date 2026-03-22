#!/usr/bin/env python3
"""MCP server exposing HTS tariff data as tools."""

import json

from mcp.server.fastmcp import FastMCP

import hts_core

mcp = FastMCP("hts")


@mcp.tool()
def search_hts(keyword: str, limit: int = 10) -> str:
    """Search HTS entries by keyword in description."""
    db = hts_core.get_db()
    try:
        rows = hts_core.search_entries(db, keyword, limit, columns=hts_core.MCP_SELECT)
        results = [hts_core.row_to_mcp_dict(row) for row in rows]
        return json.dumps(results, indent=2)
    finally:
        db.close()


@mcp.tool()
def get_code(hts_code: str) -> str:
    """Get details for a specific HTS code."""
    db = hts_core.get_db()
    try:
        row = hts_core.get_entry(db, hts_code, columns=hts_core.MCP_SELECT)
        if not row:
            return json.dumps({"error": f"HTS code '{hts_code}' not found"})
        result = hts_core.row_to_mcp_dict(row)
        return json.dumps(result, indent=2)
    finally:
        db.close()


@mcp.tool()
def list_chapter(chapter: str) -> str:
    """List all HTS entries in a chapter."""
    db = hts_core.get_db()
    try:
        rows = hts_core.list_chapter_entries(db, chapter, columns=hts_core.MCP_SELECT)
        results = [hts_core.row_to_mcp_dict(row) for row in rows]
        return json.dumps(results, indent=2)
    finally:
        db.close()


@mcp.tool()
def get_chapters() -> str:
    """Get all chapters with their descriptions and entry counts."""
    db = hts_core.get_db()
    try:
        rows = hts_core.get_all_chapters(db)
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
