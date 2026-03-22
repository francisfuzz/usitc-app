#!/usr/bin/env python3
"""Check for HTS data updates and re-ingest if changes are detected.

Since the /reststop/releases endpoint returns 404, this script detects changes
by fetching all 99 chapters from the API in parallel and comparing content
hashes against the stored hashes in the database.

If any chapter's data has changed (or no database exists), it runs a full
re-ingest. Per-chapter timestamps track when each chapter was last checked
and when its content actually changed.
"""

import shutil
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import requests

from scripts.hashing import compute_chapter_hash

DATA_DIR = Path("data")
DB_PATH = DATA_DIR / "hts.db"
API_BASE = "https://hts.usitc.gov/reststop/search"
MAX_WORKERS = 10


def fetch_chapter(chapter_num: int) -> tuple[str, list]:
    """Fetch a chapter from the API. Returns (chapter_str, data)."""
    chapter_str = f"{chapter_num:02d}"
    url = f"{API_BASE}?keyword=chapter%20{chapter_str}&limit=5000"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list):
        return chapter_str, []
    return chapter_str, data


def fetch_all_chapter_hashes() -> dict[str, str]:
    """Fetch all 99 chapters in parallel and return {chapter_str: hash}."""
    hashes = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(fetch_chapter, ch): ch for ch in range(1, 100)}
        for future in as_completed(futures):
            chapter_num = futures[future]
            try:
                chapter_str, data = future.result()
                hashes[chapter_str] = compute_chapter_hash(data)
            except Exception as e:
                print(f"Error fetching chapter {chapter_num:02d}: {e}", file=sys.stderr)
    return hashes


def get_stored_hashes() -> dict[str, str]:
    """Read stored content hashes from the database. Returns {chapter_number: hash}."""
    if not DB_PATH.exists():
        return {}
    try:
        db = sqlite3.connect(str(DB_PATH))
        cursor = db.execute("SELECT number, content_hash FROM chapters WHERE content_hash IS NOT NULL")
        result = {row[0]: row[1] for row in cursor.fetchall()}
        db.close()
        return result
    except sqlite3.OperationalError:
        return {}


def update_checked_timestamps(now: str, duration_secs: float = 0) -> None:
    """Update last_checked_at on all chapters without re-ingesting."""
    if not DB_PATH.exists():
        return
    db = sqlite3.connect(str(DB_PATH))
    try:
        db.execute("UPDATE chapters SET last_checked_at = ?", (now,))
        db.execute(
            """INSERT INTO data_freshness
               (last_full_refresh, refresh_duration_secs, chapters_changed, total_chapters)
               VALUES (?, ?, 0, 99)""",
            (now, round(duration_secs, 2))
        )
        db.commit()
    finally:
        db.close()


def run_ingest() -> int:
    """Run the ingest script. Returns the exit code."""
    import subprocess
    result = subprocess.run(
        [sys.executable, "scripts/ingest.py"],
        capture_output=False,
    )
    return result.returncode


def main():
    print("Checking for HTS data updates (all 99 chapters)...")
    start_time = time.time()
    now = datetime.now(timezone.utc).isoformat()

    try:
        current_hashes = fetch_all_chapter_hashes()
    except Exception as e:
        print(f"Error fetching chapter data: {e}", file=sys.stderr)
        sys.exit(1)

    if len(current_hashes) < 99:
        print(f"Warning: only fetched {len(current_hashes)}/99 chapters", file=sys.stderr)

    stored_hashes = get_stored_hashes()
    fetch_duration = time.time() - start_time

    if not stored_hashes:
        print(f"No previous data found. Running initial ingest... (probed in {fetch_duration:.1f}s)")
    else:
        changed = [ch for ch in current_hashes if current_hashes[ch] != stored_hashes.get(ch)]
        if not changed:
            print(f"Already up to date. (checked all 99 chapters in {fetch_duration:.1f}s)")
            update_checked_timestamps(now, duration_secs=fetch_duration)
            return

        print(f"Data changed in {len(changed)} chapter(s): {', '.join(sorted(changed))}")
        print(f"(probed in {fetch_duration:.1f}s)")
        print("Running re-ingest...")

    # Back up existing database before re-ingesting
    backup_path = DATA_DIR / "hts.db.backup"
    had_existing_db = DB_PATH.exists()

    if had_existing_db:
        print(f"Backing up existing database to {backup_path}...")
        shutil.copy2(str(DB_PATH), str(backup_path))
        DB_PATH.unlink()

    exit_code = run_ingest()
    if exit_code != 0:
        print("Ingest failed!", file=sys.stderr)
        if had_existing_db and backup_path.exists():
            print("Restoring database from backup...", file=sys.stderr)
            shutil.copy2(str(backup_path), str(DB_PATH))
        sys.exit(exit_code)

    # Success — remove backup
    if backup_path.exists():
        backup_path.unlink()

    total_duration = time.time() - start_time
    print(f"Refresh complete in {total_duration:.1f}s.")


if __name__ == "__main__":
    main()
