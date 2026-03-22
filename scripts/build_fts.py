#!/usr/bin/env python3
"""Enable FTS5 full-text search on hts_entries for Datasette.

Creates an hts_entries_fts virtual table indexing the description column.
Idempotent: drops and recreates the FTS table on each run.

Usage:
    python scripts/build_fts.py [db_path]
    # default: data/hts.db
"""

import sqlite3
import sys


def build_fts(db_path: str = "data/hts.db"):
    """Enable FTS5 on hts_entries.description. Safe to re-run."""
    db = sqlite3.connect(db_path)
    try:
        cursor = db.cursor()

        # Drop existing FTS tables for idempotency
        cursor.execute("DROP TABLE IF EXISTS hts_entries_fts")

        # Create FTS5 virtual table indexing description
        cursor.execute("""
        CREATE VIRTUAL TABLE hts_entries_fts USING fts5(
            description,
            content='hts_entries',
            content_rowid='id'
        )
        """)

        # Populate the FTS index from existing data
        cursor.execute("""
        INSERT INTO hts_entries_fts(rowid, description)
        SELECT id, description FROM hts_entries
        """)

        db.commit()
        print(f"FTS5 index created on hts_entries.description in {db_path}")
    finally:
        db.close()


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/hts.db"
    build_fts(path)
