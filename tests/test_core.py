"""Tests for hts_core — the shared HTS lookup library.

Red-green TDD: These tests fail on main (hts_core doesn't exist) and pass on feat/core-library.
"""

import sqlite3
import os
import json
import pytest
from pathlib import Path
from unittest.mock import patch


# --- RED on main: this import fails because hts_core doesn't exist ---
import hts_core


# --- get_db tests ---


def test_get_db_with_explicit_path(tmp_path):
    """get_db accepts an explicit db_path argument."""
    db_path = tmp_path / "test.db"
    # Create a minimal DB so it exists
    sqlite3.connect(str(db_path)).close()

    conn = hts_core.get_db(db_path=str(db_path))
    assert isinstance(conn, sqlite3.Connection)
    conn.close()


def test_get_db_env_var_override(tmp_path):
    """HTS_DB_PATH environment variable overrides default path."""
    db_path = tmp_path / "env_test.db"
    sqlite3.connect(str(db_path)).close()

    with patch.dict(os.environ, {"HTS_DB_PATH": str(db_path)}):
        conn = hts_core.get_db()
        assert isinstance(conn, sqlite3.Connection)
        conn.close()


def test_get_db_missing_file_raises():
    """get_db raises FileNotFoundError for nonexistent path."""
    with pytest.raises(FileNotFoundError, match="not found"):
        hts_core.get_db(db_path="/nonexistent/path/hts.db")


def test_get_db_env_var_missing_file_raises(tmp_path):
    """get_db raises FileNotFoundError when HTS_DB_PATH points to missing file."""
    with patch.dict(os.environ, {"HTS_DB_PATH": str(tmp_path / "nope.db")}):
        with pytest.raises(FileNotFoundError):
            hts_core.get_db()


# --- Column and SELECT constants ---


def test_cli_columns_has_nine_entries():
    """CLI_COLUMNS matches the 9-column SELECT pattern."""
    assert len(hts_core.CLI_COLUMNS) == 9
    assert "id" in hts_core.CLI_COLUMNS
    assert "hts_code" in hts_core.CLI_COLUMNS
    assert "chapter_id" in hts_core.CLI_COLUMNS


def test_mcp_columns_has_six_entries():
    """MCP_COLUMNS matches the 6-column SELECT pattern."""
    assert len(hts_core.MCP_COLUMNS) == 6
    assert "hts_code" in hts_core.MCP_COLUMNS
    assert "id" not in hts_core.MCP_COLUMNS
    assert "chapter_id" not in hts_core.MCP_COLUMNS


def test_cli_select_contains_all_columns():
    """CLI_SELECT string references all CLI columns."""
    for col in hts_core.CLI_COLUMNS:
        assert col in hts_core.CLI_SELECT


def test_mcp_select_contains_all_columns():
    """MCP_SELECT string references all MCP columns."""
    for col in hts_core.MCP_COLUMNS:
        assert col in hts_core.MCP_SELECT


# --- Row conversion tests ---


def test_row_to_cli_dict():
    """row_to_cli_dict maps a 9-tuple to named dict."""
    row = (1, "0101.21.00", 2, "Horses", "No.", "Free", "Free", "20%", 1)
    result = hts_core.row_to_cli_dict(row)
    assert result["id"] == 1
    assert result["hts_code"] == "0101.21.00"
    assert result["description"] == "Horses"
    assert result["chapter_id"] == 1


def test_row_to_mcp_dict():
    """row_to_mcp_dict maps a 6-tuple and replaces None with empty string."""
    row = ("0101.21.00", "Horses", None, "Free", None, "20%")
    result = hts_core.row_to_mcp_dict(row)
    assert result["hts_code"] == "0101.21.00"
    assert result["unit"] == ""  # None -> ""
    assert result["special_rate"] == ""  # None -> ""
    assert result["column2_rate"] == "20%"


def test_row_to_mcp_dict_no_none_values():
    """row_to_mcp_dict never returns None values."""
    row = (None, None, None, None, None, None)
    result = hts_core.row_to_mcp_dict(row)
    for v in result.values():
        assert v is not None
        assert v == ""


# --- Query function tests (using test_db fixture) ---


def test_search_entries_returns_matches(test_db):
    """search_entries finds entries by keyword."""
    db = sqlite3.connect(str(test_db))
    try:
        rows = hts_core.search_entries(db, "copper")
        assert len(rows) > 0
    finally:
        db.close()


def test_search_entries_respects_limit(test_db):
    """search_entries honors the limit parameter."""
    db = sqlite3.connect(str(test_db))
    try:
        rows = hts_core.search_entries(db, "copper", limit=2)
        assert len(rows) <= 2
    finally:
        db.close()


def test_search_entries_with_mcp_columns(test_db):
    """search_entries can use MCP_SELECT for 6-column results."""
    db = sqlite3.connect(str(test_db))
    try:
        rows = hts_core.search_entries(db, "copper", columns=hts_core.MCP_SELECT)
        assert len(rows) > 0
        assert len(rows[0]) == 6  # MCP has 6 columns
    finally:
        db.close()


def test_get_entry_found(test_db):
    """get_entry returns a row for a known code."""
    db = sqlite3.connect(str(test_db))
    try:
        row = hts_core.get_entry(db, "0101.21.00")
        assert row is not None
        assert row[1] == "0101.21.00"  # hts_code is second column in CLI
    finally:
        db.close()


def test_get_entry_not_found(test_db):
    """get_entry returns None for unknown code."""
    db = sqlite3.connect(str(test_db))
    try:
        row = hts_core.get_entry(db, "9999.99.99")
        assert row is None
    finally:
        db.close()


def test_list_chapter_entries_returns_sorted(test_db):
    """list_chapter_entries returns entries sorted by hts_code."""
    db = sqlite3.connect(str(test_db))
    try:
        rows = hts_core.list_chapter_entries(db, "74")
        codes = [r[1] for r in rows]  # hts_code at index 1
        assert codes == sorted(codes)
        assert len(rows) > 0
    finally:
        db.close()


def test_list_chapter_entries_pads_single_digit(test_db):
    """list_chapter_entries zero-pads single-digit chapter numbers."""
    db = sqlite3.connect(str(test_db))
    try:
        rows = hts_core.list_chapter_entries(db, "7")
        assert len(rows) > 0
        for r in rows:
            assert r[1].startswith("07")
    finally:
        db.close()


def test_get_all_chapters(test_db):
    """get_all_chapters returns chapter number, description, and count."""
    db = sqlite3.connect(str(test_db))
    try:
        rows = hts_core.get_all_chapters(db)
        assert len(rows) == 3  # fixture has 3 chapters
        numbers = [r[0] for r in rows]
        assert numbers == sorted(numbers)
    finally:
        db.close()
