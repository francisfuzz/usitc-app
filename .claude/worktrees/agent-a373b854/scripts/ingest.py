#!/usr/bin/env python3
"""Download complete HTS schedule from API and load into SQLite."""

import sqlite3
import requests
import sys
import os
import json


def create_schema(db):
    """Create the tables and indexes."""
    cursor = db.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chapters (
        id          INTEGER PRIMARY KEY,
        number      TEXT NOT NULL UNIQUE,
        description TEXT
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

    db.commit()


def fetch_and_ingest_chapter(db, chapter_num: int) -> tuple:
    """Fetch a chapter from API and insert into database."""
    try:
        chapter_str = f"{chapter_num:02d}"
        url = f"https://hts.usitc.gov/reststop/search?keyword=chapter%20{chapter_str}&limit=5000"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()

        if not isinstance(data, list):
            print(f"Warning: Chapter {chapter_str} returned non-list", file=sys.stderr)
            return 0, 0

        cursor = db.cursor()

        # Insert chapter
        cursor.execute(
            "INSERT OR IGNORE INTO chapters (number, description) VALUES (?, ?)",
            (chapter_str, f"Chapter {chapter_str}")
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

        db.commit()
        return entries_inserted, duplicates_skipped

    except Exception as e:
        print(f"Error with chapter {chapter_num:02d}: {e}", file=sys.stderr)
        return 0, 0


def main():
    """Main ingest routine."""
    os.makedirs("data", exist_ok=True)

    db_path = "data/hts.db"
    db = sqlite3.connect(db_path)

    try:
        print("Creating database schema...")
        create_schema(db)

        print("Fetching and ingesting HTS data from all 99 chapters...")

        total_entries = 0
        total_chapters_done = 0
        total_duplicates = 0

        for ch in range(1, 100):
            entries, duplicates = fetch_and_ingest_chapter(db, ch)
            total_entries += entries
            total_chapters_done += 1
            total_duplicates += duplicates

            if ch % 10 == 0:
                print(f"  Completed {ch}/99 chapters ({total_entries} entries loaded so far)...")

        print(f"Loaded {total_entries} entries across 99 chapters")
        if total_duplicates > 0:
            print(f"(Skipped {total_duplicates} duplicate HTS codes)")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
