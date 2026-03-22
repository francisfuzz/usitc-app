#!/usr/bin/env python3
"""Download complete HTS schedule from API and load into SQLite."""

import sqlite3
import time
import requests
import sys
import os
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from scripts.hashing import compute_chapter_hash


def create_schema(db):
    """Create the tables and indexes."""
    cursor = db.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chapters (
        id              INTEGER PRIMARY KEY,
        number          TEXT NOT NULL UNIQUE,
        description     TEXT,
        content_hash    TEXT,
        last_changed_at TEXT,
        last_checked_at TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS hts_entries (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        hts_code        TEXT NOT NULL UNIQUE,
        indent          INTEGER,
        description     TEXT,
        unit            TEXT,
        general_rate    TEXT,
        special_rate    TEXT,
        column2_rate    TEXT,
        footnotes       TEXT,
        chapter_id      INTEGER REFERENCES chapters(id)
    )
    """)

    # Drop old indexes if they exist (to avoid issues on re-runs)
    cursor.execute("DROP INDEX IF EXISTS idx_hts_code")
    cursor.execute("DROP INDEX IF EXISTS idx_description")

    cursor.execute("CREATE INDEX idx_hts_code ON hts_entries(hts_code)")
    cursor.execute("CREATE INDEX idx_description ON hts_entries(description)")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS data_freshness (
        id                    INTEGER PRIMARY KEY,
        last_full_refresh     TEXT NOT NULL,
        refresh_duration_secs REAL,
        chapters_changed      INTEGER,
        total_chapters        INTEGER
    )
    """)

    db.commit()


def fetch_chapter(chapter_num: int) -> tuple:
    """Fetch a chapter from the API. Returns (chapter_num, data) or (chapter_num, None) on error."""
    try:
        chapter_str = f"{chapter_num:02d}"
        url = f"https://hts.usitc.gov/reststop/search?keyword=chapter%20{chapter_str}&limit=5000"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()

        if not isinstance(data, list):
            print(f"Warning: Chapter {chapter_str} returned non-list", file=sys.stderr)
            return chapter_num, None

        return chapter_num, data

    except Exception as e:
        print(f"Error fetching chapter {chapter_num:02d}: {e}", file=sys.stderr)
        return chapter_num, None


def ingest_chapter(db, chapter_num: int, data: list, now: str | None = None) -> tuple:
    """Insert a chapter's data into the database. Returns (entries_inserted, duplicates_skipped)."""
    chapter_str = f"{chapter_num:02d}"
    cursor = db.cursor()
    timestamp = now or datetime.now(timezone.utc).isoformat()
    content_hash = compute_chapter_hash(data)

    # Insert chapter with content hash and timestamps
    cursor.execute(
        """INSERT OR IGNORE INTO chapters
           (number, description, content_hash, last_changed_at, last_checked_at)
           VALUES (?, ?, ?, ?, ?)""",
        (chapter_str, f"Chapter {chapter_str}", content_hash, timestamp, timestamp)
    )

    # Get chapter id
    cursor.execute("SELECT id FROM chapters WHERE number = ?", (chapter_str,))
    chapter_row = cursor.fetchone()
    chapter_id = chapter_row[0] if chapter_row else None

    entries_inserted = 0
    duplicates_skipped = 0

    for entry in data:
        hts_code = entry.get("htsno")
        if not hts_code:
            continue

        hts_code = str(hts_code).strip()

        description = entry.get("description") or ""
        if description:
            description = str(description).strip()

        indent_val = entry.get("indent", 0)
        if isinstance(indent_val, str):
            indent = int(indent_val) if indent_val.isdigit() else 0
        else:
            indent = int(indent_val) if indent_val else 0

        units = entry.get("units")
        unit = ""
        if isinstance(units, list) and units:
            unit = str(units[0]).strip() if units[0] else ""

        general_rate = entry.get("general") or ""
        if general_rate:
            general_rate = str(general_rate).strip()

        special_rate = entry.get("special") or ""
        if special_rate:
            special_rate = str(special_rate).strip()

        column2_rate = entry.get("other") or ""
        if column2_rate:
            column2_rate = str(column2_rate).strip()

        footnotes_data = entry.get("footnotes")
        footnotes_str = ""
        if footnotes_data:
            try:
                footnotes_str = json.dumps(footnotes_data)
            except (TypeError, ValueError):
                pass

        try:
            cursor.execute(
                """INSERT INTO hts_entries
                   (hts_code, indent, description, unit, general_rate, special_rate, column2_rate, footnotes, chapter_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (hts_code, indent, description, unit, general_rate, special_rate, column2_rate, footnotes_str, chapter_id)
            )
            entries_inserted += 1
        except sqlite3.IntegrityError:
            duplicates_skipped += 1

    return entries_inserted, duplicates_skipped


def main():
    """Main ingest routine."""
    os.makedirs("data", exist_ok=True)

    db_path = "data/hts.db"
    db = sqlite3.connect(db_path)

    try:
        print("Creating database schema...")
        create_schema(db)

        print("Fetching HTS data from all 99 chapters (parallel)...")
        start_time = time.time()
        now = datetime.now(timezone.utc).isoformat()
        max_workers = int(os.getenv("HTS_INGEST_WORKERS", "10"))

        # Phase 1: Fetch all chapters in parallel
        chapter_data = {}
        fetch_errors = 0

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(fetch_chapter, ch): ch for ch in range(1, 100)}
            for future in as_completed(futures):
                chapter_num, data = future.result()
                if data is not None:
                    chapter_data[chapter_num] = data
                else:
                    fetch_errors += 1

        print(f"  Fetched {len(chapter_data)} chapters ({fetch_errors} errors)")

        # Phase 2: Insert into DB sequentially (SQLite is single-writer)
        print("Inserting data into database...")
        total_entries = 0
        total_duplicates = 0

        for ch in sorted(chapter_data.keys()):
            entries, duplicates = ingest_chapter(db, ch, chapter_data[ch], now=now)
            total_entries += entries
            total_duplicates += duplicates

        duration = time.time() - start_time

        # Record freshness metadata
        db.execute(
            """INSERT INTO data_freshness
               (last_full_refresh, refresh_duration_secs, chapters_changed, total_chapters)
               VALUES (?, ?, ?, ?)""",
            (now, round(duration, 2), len(chapter_data), 99)
        )
        db.commit()

        print(f"Loaded {total_entries} entries across {len(chapter_data)} chapters in {duration:.1f}s")
        if total_duplicates > 0:
            print(f"(Skipped {total_duplicates} duplicate HTS codes)")
        if fetch_errors > 0:
            print(f"Warning: {fetch_errors} chapters failed to fetch", file=sys.stderr)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
