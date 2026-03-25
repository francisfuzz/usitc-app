#!/usr/bin/env python3
"""MCP server exposing HTS tariff data as tools."""

import json
import os

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
    """Get all chapters with their descriptions, entry counts, and freshness timestamps.

    Each chapter includes last_checked_at (when we last verified against the USITC source)
    and last_changed_at (when the chapter's content actually changed).
    """
    db = hts_core.get_db()
    try:
        rows = hts_core.get_all_chapters(db)
        results = [
            {
                "number": r[0],
                "description": r[1] or "",
                "entry_count": r[2],
                "last_checked_at": r[3] or "",
                "last_changed_at": r[4] or "",
            }
            for r in rows
        ]
        return json.dumps(results, indent=2)
    finally:
        db.close()


@mcp.tool()
def get_data_freshness() -> str:
    """Check when HTS data was last refreshed and which chapters have changed.

    Returns the date of the last full refresh, plus per-chapter timestamps
    showing when each chapter's data was last verified against the USITC source
    and when its content actually changed. Use this to assess whether the tariff
    data is current before relying on query results.
    """
    db = hts_core.get_db()
    try:
        freshness = hts_core.get_data_freshness(db)
        return json.dumps(freshness, indent=2)
    finally:
        db.close()


if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    if transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport=transport, host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
