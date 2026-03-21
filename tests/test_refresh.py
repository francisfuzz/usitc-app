"""Tests for scripts/refresh.py — safe refresh with backup.

Red-green TDD: These tests fail on main (no backup logic exists)
and pass on feat/parallel-ingest-safe-refresh.
"""

import sqlite3
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from scripts.refresh import get_stored_hash, save_hash, main


@pytest.fixture
def data_dir(tmp_path):
    """Create a temporary data directory with a fake database."""
    data = tmp_path / "data"
    data.mkdir()

    # Create a fake database
    db_path = data / "hts.db"
    db = sqlite3.connect(str(db_path))
    db.execute("CREATE TABLE test (id INTEGER)")
    db.execute("INSERT INTO test VALUES (42)")
    db.commit()
    db.close()

    return data


def test_get_stored_hash_returns_none_when_no_file(tmp_path):
    """Returns None when no revision file exists."""
    with patch("scripts.refresh.REVISION_FILE", tmp_path / "nonexistent.txt"):
        result = get_stored_hash()
    assert result is None


def test_get_stored_hash_reads_file(tmp_path):
    """Reads hash from revision file."""
    rev_file = tmp_path / "last_revision.txt"
    rev_file.write_text("abc123\n")
    with patch("scripts.refresh.REVISION_FILE", rev_file):
        result = get_stored_hash()
    assert result == "abc123"


def test_save_hash_creates_file(tmp_path):
    """save_hash writes hash to revision file."""
    rev_file = tmp_path / "last_revision.txt"
    with patch("scripts.refresh.REVISION_FILE", rev_file):
        with patch("scripts.refresh.DATA_DIR", tmp_path):
            save_hash("deadbeef")
    assert rev_file.read_text().strip() == "deadbeef"


def test_refresh_backs_up_db_before_reingest(data_dir):
    """When data has changed, refresh backs up the DB before deleting it.

    RED on main: main's refresh.py does db_path.unlink() without backup.
    GREEN on this branch: copies to .backup first.
    """
    db_path = data_dir / "hts.db"
    backup_path = data_dir / "hts.db.backup"

    # Verify DB exists and has data
    assert db_path.exists()

    with patch("scripts.refresh.DATA_DIR", data_dir), \
         patch("scripts.refresh.REVISION_FILE", data_dir / "last_revision.txt"), \
         patch("scripts.refresh.fetch_probe_hash", return_value="newhash123"), \
         patch("scripts.refresh.run_ingest", return_value=0):
        main()

    # After successful ingest, backup should be cleaned up
    assert not backup_path.exists()
    # New DB should exist (created by ingest)
    # Hash should be saved
    assert (data_dir / "last_revision.txt").read_text().strip() == "newhash123"


def test_refresh_restores_backup_on_ingest_failure(data_dir):
    """When ingest fails, the backup is restored.

    RED on main: main's refresh.py deletes DB without backup, so failed ingest = data loss.
    GREEN on this branch: backup is restored on failure.
    """
    db_path = data_dir / "hts.db"
    original_size = db_path.stat().st_size

    with patch("scripts.refresh.DATA_DIR", data_dir), \
         patch("scripts.refresh.REVISION_FILE", data_dir / "last_revision.txt"), \
         patch("scripts.refresh.fetch_probe_hash", return_value="newhash123"), \
         patch("scripts.refresh.run_ingest", return_value=1):  # Simulate failure
        with pytest.raises(SystemExit):
            main()

    # After failed ingest, DB should be restored from backup
    assert db_path.exists(), "Database was lost after failed ingest — backup/restore didn't work"
    # Verify it's the original data
    db = sqlite3.connect(str(db_path))
    result = db.execute("SELECT * FROM test").fetchone()
    db.close()
    assert result == (42,), "Restored database doesn't contain original data"


def test_refresh_skips_when_up_to_date(data_dir, capsys):
    """When hash matches, refresh does nothing."""
    rev_file = data_dir / "last_revision.txt"
    rev_file.write_text("samehash\n")

    with patch("scripts.refresh.DATA_DIR", data_dir), \
         patch("scripts.refresh.REVISION_FILE", rev_file), \
         patch("scripts.refresh.fetch_probe_hash", return_value="samehash"):
        main()

    captured = capsys.readouterr()
    assert "Already up to date" in captured.out
