#!/usr/bin/env python3
"""Enable FTS5 full-text search on hts_entries for Datasette.

Creates an hts_entries_fts virtual table indexing the description column.
Idempotent: drops and recreates the FTS table on each run.

Usage:
    python scripts/build_fts.py [db_path]
    # default: data/hts.db
"""

import sqlite_utils
import sys


def build_fts(db_path: str = "data/hts.db"):
    """Enable FTS5 on hts_entries.description. Safe to re-run."""
    db = sqlite_utils.Database(db_path)
    table = db["hts_entries"]

    # Disable FTS first for idempotency (ignore if not enabled)
    try:
        table.disable_fts()
    except Exception:
        pass

    table.enable_fts(["description"], fts_version="fts5")
    print(f"FTS5 index created on hts_entries.description in {db_path}")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/hts.db"
    build_fts(path)
