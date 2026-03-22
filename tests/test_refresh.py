"""Tests for scripts/refresh.py — safe refresh with backup.

Red-green TDD: These tests fail on main (no backup logic exists)
and pass on this branch.
"""

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from scripts.refresh import main


@pytest.fixture
def data_dir(tmp_path):
    """Create a temporary data directory with a fake database."""
    data = tmp_path / "data"
    data.mkdir()

    # Create a fake database with test data
    db_path = data / "hts.db"
    db = sqlite3.connect(str(db_path))
    db.execute("CREATE TABLE test (id INTEGER)")
    db.execute("INSERT INTO test VALUES (42)")
    db.commit()
    db.close()

    return data


def test_refresh_restores_backup_on_ingest_failure(data_dir):
    """When ingest fails, the backup is restored so data is not lost."""
    db_path = data_dir / "hts.db"

    with patch("scripts.refresh.DATA_DIR", data_dir), \
         patch("scripts.refresh.DB_PATH", db_path), \
         patch("scripts.refresh.fetch_all_chapter_hashes", return_value={"01": "newhash"}), \
         patch("scripts.refresh.get_stored_hashes", return_value={"01": "oldhash"}), \
         patch("scripts.refresh.run_ingest", return_value=1):
        with pytest.raises(SystemExit):
            main()

    # After failed ingest, DB should be restored from backup
    assert db_path.exists(), "Database was lost after failed ingest — backup/restore didn't work"
    db = sqlite3.connect(str(db_path))
    result = db.execute("SELECT * FROM test").fetchone()
    db.close()
    assert result == (42,), "Restored database doesn't contain original data"


def test_refresh_cleans_up_backup_on_success(data_dir):
    """After successful ingest, the backup file is removed."""
    db_path = data_dir / "hts.db"
    backup_path = data_dir / "hts.db.backup"

    with patch("scripts.refresh.DATA_DIR", data_dir), \
         patch("scripts.refresh.DB_PATH", db_path), \
         patch("scripts.refresh.fetch_all_chapter_hashes", return_value={"01": "newhash"}), \
         patch("scripts.refresh.get_stored_hashes", return_value={"01": "oldhash"}), \
         patch("scripts.refresh.run_ingest", return_value=0):
        main()

    assert not backup_path.exists(), "Backup file was not cleaned up after successful ingest"


def test_refresh_skips_when_up_to_date(data_dir, capsys):
    """When hashes match, refresh does nothing."""
    db_path = data_dir / "hts.db"

    # Need chapters table for update_checked_timestamps
    db = sqlite3.connect(str(db_path))
    db.execute("CREATE TABLE IF NOT EXISTS chapters (id INTEGER PRIMARY KEY, number TEXT, description TEXT, content_hash TEXT, last_changed_at TEXT, last_checked_at TEXT)")
    db.execute("""CREATE TABLE IF NOT EXISTS data_freshness (
        id INTEGER PRIMARY KEY, last_full_refresh TEXT NOT NULL,
        refresh_duration_secs REAL, chapters_changed INTEGER, total_chapters INTEGER)""")
    db.commit()
    db.close()

    with patch("scripts.refresh.DATA_DIR", data_dir), \
         patch("scripts.refresh.DB_PATH", db_path), \
         patch("scripts.refresh.fetch_all_chapter_hashes", return_value={"01": "samehash"}), \
         patch("scripts.refresh.get_stored_hashes", return_value={"01": "samehash"}):
        main()

    captured = capsys.readouterr()
    assert "Already up to date" in captured.out
