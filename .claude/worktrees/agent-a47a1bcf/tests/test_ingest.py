"""Tests for scripts/ingest.py — parallel ingest.

Red-green TDD: These tests fail on main (fetch_chapter and ingest_chapter
don't exist as separate functions) and pass on feat/parallel-ingest-safe-refresh.
"""

import sqlite3
import json
import pytest
from unittest.mock import patch, MagicMock

import sys
import os

# Add project root to path so we can import scripts
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from scripts.ingest import create_schema, fetch_chapter, ingest_chapter


@pytest.fixture
def empty_db(tmp_path):
    """Create an empty database with schema."""
    db_path = tmp_path / "test.db"
    db = sqlite3.connect(str(db_path))
    create_schema(db)
    yield db
    db.close()


# --- fetch_chapter tests (RED on main: function doesn't exist) ---


def test_fetch_chapter_returns_tuple():
    """fetch_chapter returns (chapter_num, data) tuple."""
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {"htsno": "0101.21.00", "description": "Horses", "indent": 2,
         "units": ["No."], "general": "Free", "special": "Free", "other": "20%"}
    ]
    mock_response.raise_for_status = MagicMock()

    with patch("scripts.ingest.requests.get", return_value=mock_response):
        chapter_num, data = fetch_chapter(1)

    assert chapter_num == 1
    assert isinstance(data, list)
    assert len(data) == 1


def test_fetch_chapter_returns_none_on_error():
    """fetch_chapter returns (chapter_num, None) on network error."""
    with patch("scripts.ingest.requests.get", side_effect=Exception("Network error")):
        chapter_num, data = fetch_chapter(5)

    assert chapter_num == 5
    assert data is None


def test_fetch_chapter_returns_none_for_non_list():
    """fetch_chapter returns None data when API returns non-list."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"error": "not found"}
    mock_response.raise_for_status = MagicMock()

    with patch("scripts.ingest.requests.get", return_value=mock_response):
        chapter_num, data = fetch_chapter(99)

    assert chapter_num == 99
    assert data is None


# --- ingest_chapter tests (RED on main: function doesn't exist) ---


def test_ingest_chapter_inserts_entries(empty_db):
    """ingest_chapter inserts entries and returns count."""
    data = [
        {"htsno": "0101.21.00", "description": "Horses", "indent": 2,
         "units": ["No."], "general": "Free", "special": "Free", "other": "20%"},
        {"htsno": "0101.29.00", "description": "Other horses", "indent": 2,
         "units": ["No."], "general": "Free", "special": "", "other": ""},
    ]

    entries, duplicates = ingest_chapter(empty_db, 1, data)

    assert entries == 2
    assert duplicates == 0


def test_ingest_chapter_creates_chapter_record(empty_db):
    """ingest_chapter creates a chapter record in the chapters table."""
    data = [
        {"htsno": "0101.21.00", "description": "Horses", "indent": 2,
         "units": ["No."], "general": "Free", "special": "Free", "other": "20%"},
    ]

    ingest_chapter(empty_db, 1, data)

    cursor = empty_db.cursor()
    cursor.execute("SELECT number, description FROM chapters WHERE number = '01'")
    row = cursor.fetchone()
    assert row is not None
    assert row[0] == "01"


def test_ingest_chapter_skips_duplicates(empty_db):
    """ingest_chapter counts duplicate HTS codes."""
    data = [
        {"htsno": "0101.21.00", "description": "Horses", "indent": 2,
         "units": ["No."], "general": "Free", "special": "Free", "other": "20%"},
    ]

    # Insert once
    ingest_chapter(empty_db, 1, data)
    empty_db.commit()

    # Insert again — should skip duplicate
    entries, duplicates = ingest_chapter(empty_db, 1, data)
    assert entries == 0
    assert duplicates == 1


def test_ingest_chapter_skips_entries_without_htsno(empty_db):
    """Entries without htsno field are skipped."""
    data = [
        {"description": "No code entry", "indent": 0},
        {"htsno": "0101.21.00", "description": "Horses", "indent": 2,
         "units": ["No."], "general": "Free", "special": "Free", "other": "20%"},
    ]

    entries, duplicates = ingest_chapter(empty_db, 1, data)
    assert entries == 1  # Only the one with htsno


def test_ingest_chapter_handles_string_indent(empty_db):
    """Indent value can be a string and gets converted to int."""
    data = [
        {"htsno": "0101.21.00", "description": "Horses", "indent": "2",
         "units": ["No."], "general": "Free", "special": "Free", "other": "20%"},
    ]

    ingest_chapter(empty_db, 1, data)
    empty_db.commit()

    cursor = empty_db.cursor()
    cursor.execute("SELECT indent FROM hts_entries WHERE hts_code = '0101.21.00'")
    assert cursor.fetchone()[0] == 2


def test_ingest_chapter_handles_footnotes(empty_db):
    """Footnotes data is serialized to JSON string."""
    data = [
        {"htsno": "0101.21.00", "description": "Horses", "indent": 2,
         "units": ["No."], "general": "Free", "special": "Free", "other": "20%",
         "footnotes": [{"id": "1", "text": "See note"}]},
    ]

    ingest_chapter(empty_db, 1, data)
    empty_db.commit()

    cursor = empty_db.cursor()
    cursor.execute("SELECT footnotes FROM hts_entries WHERE hts_code = '0101.21.00'")
    footnotes = cursor.fetchone()[0]
    parsed = json.loads(footnotes)
    assert parsed[0]["id"] == "1"
