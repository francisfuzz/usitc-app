"""Tests for scripts/build_fts.py — FTS5 index builder."""

import sqlite3
import pytest
from pathlib import Path


def _create_minimal_db(db_path):
    """Create a minimal DB with hts_entries table for FTS testing."""
    db = sqlite3.connect(str(db_path))
    cursor = db.cursor()
    cursor.execute("""
    CREATE TABLE hts_entries (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        hts_code    TEXT NOT NULL UNIQUE,
        description TEXT
    )
    """)
    cursor.execute(
        "INSERT INTO hts_entries (hts_code, description) VALUES (?, ?)",
        ("0101.21.00", "Live purebred breeding horses"),
    )
    cursor.execute(
        "INSERT INTO hts_entries (hts_code, description) VALUES (?, ?)",
        ("2823.00.00", "Titanium oxides"),
    )
    db.commit()
    db.close()


class TestBuildFts:
    """Tests for the build_fts function."""

    def test_creates_fts_virtual_table(self, tmp_path):
        """FTS5 virtual table hts_entries_fts should exist after build."""
        db_path = tmp_path / "hts.db"
        _create_minimal_db(db_path)

        from scripts.build_fts import build_fts
        build_fts(str(db_path))

        db = sqlite3.connect(str(db_path))
        tables = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='hts_entries_fts'"
        ).fetchall()
        db.close()
        assert len(tables) == 1

    def test_fts_search_returns_results(self, tmp_path):
        """FTS5 search should find entries by description keyword."""
        db_path = tmp_path / "hts.db"
        _create_minimal_db(db_path)

        from scripts.build_fts import build_fts
        build_fts(str(db_path))

        db = sqlite3.connect(str(db_path))
        results = db.execute(
            "SELECT * FROM hts_entries_fts WHERE hts_entries_fts MATCH 'titanium'"
        ).fetchall()
        db.close()
        assert len(results) == 1

    def test_fts_search_no_match(self, tmp_path):
        """FTS5 search should return empty for non-matching terms."""
        db_path = tmp_path / "hts.db"
        _create_minimal_db(db_path)

        from scripts.build_fts import build_fts
        build_fts(str(db_path))

        db = sqlite3.connect(str(db_path))
        results = db.execute(
            "SELECT * FROM hts_entries_fts WHERE hts_entries_fts MATCH 'nonexistent'"
        ).fetchall()
        db.close()
        assert len(results) == 0

    def test_idempotent_reruns(self, tmp_path):
        """Running build_fts twice should not error or duplicate data."""
        db_path = tmp_path / "hts.db"
        _create_minimal_db(db_path)

        from scripts.build_fts import build_fts
        build_fts(str(db_path))
        build_fts(str(db_path))  # second run should not raise

        db = sqlite3.connect(str(db_path))
        results = db.execute(
            "SELECT * FROM hts_entries_fts WHERE hts_entries_fts MATCH 'titanium'"
        ).fetchall()
        db.close()
        assert len(results) == 1

    def test_fts_indexes_description_column(self, tmp_path):
        """FTS should index the description column specifically."""
        db_path = tmp_path / "hts.db"
        _create_minimal_db(db_path)

        from scripts.build_fts import build_fts
        build_fts(str(db_path))

        db = sqlite3.connect(str(db_path))
        # "horses" appears in description of 0101.21.00
        results = db.execute(
            "SELECT * FROM hts_entries_fts WHERE hts_entries_fts MATCH 'horses'"
        ).fetchall()
        db.close()
        assert len(results) == 1
