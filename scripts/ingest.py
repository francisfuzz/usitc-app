#!/usr/bin/env python3
"""Download HTS schedule from API and load into SQLite."""

import sqlite3
import requests
import sys
import os


def create_schema(db):
    """Create the tables and indexes."""
    cursor = db.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chapters (
        id          INTEGER PRIMARY KEY,
        number      TEXT NOT NULL,
        description TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS hts_entries (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        hts_code        TEXT NOT NULL,
        indent          INTEGER,
        description     TEXT,
        unit            TEXT,
        general_rate    TEXT,
        special_rate    TEXT,
        column2_rate    TEXT,
        chapter_id      INTEGER REFERENCES chapters(id)
    )
    """)

    # Drop old indexes if they exist (to avoid issues on re-runs)
    cursor.execute("DROP INDEX IF EXISTS idx_hts_code")
    cursor.execute("DROP INDEX IF EXISTS idx_description")

    cursor.execute("CREATE INDEX idx_hts_code ON hts_entries(hts_code)")
    cursor.execute("CREATE INDEX idx_description ON hts_entries(description)")

    db.commit()


def fetch_hts_data_via_search():
    """Fetch HTS data using the search API with broad keywords."""
    # Start with broad searches to get a comprehensive sample
    keywords = [
        "copper", "iron", "steel", "aluminum", "nickel", "titanium", "zinc",
        "wire", "rod", "bar", "plate", "sheet", "pipe", "tube",
        "live animals", "meat", "fish", "vegetables", "fruit", "coffee", "tea",
        "textiles", "clothing", "footwear", "leather",
        "machinery", "vehicles", "electrical", "optical",
        "plastics", "rubber", "paper", "wood",
        "ceramic", "glass", "stone", "minerals"
    ]

    all_entries = {}

    for keyword in keywords:
        try:
            url = f"https://hts.usitc.gov/reststop/search?keyword={keyword}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            results = response.json()
            if isinstance(results, list):
                for entry in results:
                    # Use htsno as unique key
                    htsno = entry.get("htsno", "").strip()
                    if htsno and htsno not in all_entries:
                        all_entries[htsno] = entry
        except Exception as e:
            print(f"Warning: Failed to fetch keyword '{keyword}': {e}", file=sys.stderr)
            continue

    return all_entries


def ingest_data(db, entries_dict):
    """Parse search results and insert into database."""
    cursor = db.cursor()

    chapters_inserted = set()
    entries_inserted = 0

    for htsno, entry in entries_dict.items():
        # Extract chapter from HTS code (first 2 digits)
        hts_code = entry.get("htsno")
        if not hts_code:
            continue
        hts_code = str(hts_code).strip()
        if not hts_code or len(hts_code) < 2:
            continue

        chapter_number = hts_code[:2]

        # Insert chapter if not already done
        if chapter_number not in chapters_inserted:
            description = f"Chapter {chapter_number}"
            cursor.execute(
                "INSERT OR IGNORE INTO chapters (number, description) VALUES (?, ?)",
                (chapter_number, description)
            )
            chapters_inserted.add(chapter_number)

        # Get the chapter id for foreign key
        cursor.execute("SELECT id FROM chapters WHERE number = ?", (chapter_number,))
        chapter_row = cursor.fetchone()
        chapter_id = chapter_row[0] if chapter_row else None

        # Extract rate information - handle None values
        general_rate = entry.get("general") or ""
        if general_rate:
            general_rate = str(general_rate).strip()
        special_rate = entry.get("special") or ""
        if special_rate:
            special_rate = str(special_rate).strip()
        other_rate = entry.get("other") or ""
        if other_rate:
            other_rate = str(other_rate).strip()

        description = entry.get("description") or ""
        if description:
            description = str(description).strip()

        indent_val = entry.get("indent", 0)
        if isinstance(indent_val, str):
            indent = int(indent_val) if indent_val.isdigit() else 0
        else:
            indent = int(indent_val) if indent_val else 0

        # Get unit from units array if present
        units = entry.get("units")
        unit = ""
        if isinstance(units, list) and units:
            unit = str(units[0]).strip() if units[0] else ""

        cursor.execute(
            """INSERT INTO hts_entries
               (hts_code, indent, description, unit, general_rate, special_rate, column2_rate, chapter_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (hts_code, indent, description, unit, general_rate, special_rate, other_rate, chapter_id)
        )
        entries_inserted += 1

    db.commit()
    return entries_inserted, len(chapters_inserted)


def main():
    """Main ingest routine."""
    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)

    # Connect to database
    db_path = "data/hts.db"
    db = sqlite3.connect(db_path)

    try:
        print("Creating database schema...")
        create_schema(db)

        print("Fetching HTS data from API...")
        data = fetch_hts_data_via_search()

        if not data:
            print("Warning: No data retrieved from API", file=sys.stderr)
            print("Loaded 0 entries across 0 chapters")
            return

        print(f"Fetched {len(data)} entries, ingesting...")
        entries_count, chapters_count = ingest_data(db, data)

        print(f"Loaded {entries_count} entries across {chapters_count} chapters")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
