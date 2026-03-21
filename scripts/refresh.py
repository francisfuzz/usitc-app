#!/usr/bin/env python3
"""Check for HTS data updates and re-ingest if changes are detected.

Since the /reststop/releases endpoint returns 404, this script detects changes
by fetching a probe chapter (chapter 01) from the API and comparing a hash of
its response against the last-known hash stored in data/last_revision.txt.

If the data has changed (or no previous hash exists), it runs a full re-ingest.
"""

import hashlib
import json
import os
import sys
from pathlib import Path

import requests


DATA_DIR = Path("data")
REVISION_FILE = DATA_DIR / "last_revision.txt"
PROBE_URL = "https://hts.usitc.gov/reststop/search?keyword=chapter%2001&limit=5000"


def fetch_probe_hash() -> str:
    """Fetch chapter 01 from the API and return a content hash."""
    response = requests.get(PROBE_URL, timeout=30)
    response.raise_for_status()
    data = response.json()
    # Sort entries by hts code for deterministic hashing
    if isinstance(data, list):
        data.sort(key=lambda e: e.get("htsno", ""))
    content = json.dumps(data, sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()


def get_stored_hash() -> str | None:
    """Read the last stored revision hash, or None if not present."""
    if not REVISION_FILE.exists():
        return None
    return REVISION_FILE.read_text().strip()


def save_hash(hash_value: str) -> None:
    """Save the revision hash to disk."""
    os.makedirs(DATA_DIR, exist_ok=True)
    REVISION_FILE.write_text(hash_value + "\n")


def run_ingest() -> int:
    """Run the ingest script. Returns the exit code."""
    import subprocess
    result = subprocess.run(
        [sys.executable, "scripts/ingest.py"],
        capture_output=False,
    )
    return result.returncode


def main():
    print("Checking for HTS data updates...")

    try:
        current_hash = fetch_probe_hash()
    except Exception as e:
        print(f"Error fetching probe data: {e}", file=sys.stderr)
        sys.exit(1)

    stored_hash = get_stored_hash()

    if stored_hash == current_hash:
        print("Already up to date.")
        return

    if stored_hash is None:
        print("No previous revision recorded. Running initial ingest...")
    else:
        print(f"Data changed (old: {stored_hash[:12]}... new: {current_hash[:12]}...)")
        print("Running re-ingest...")

    # Remove old database so ingest creates fresh tables
    db_path = DATA_DIR / "hts.db"
    if db_path.exists():
        db_path.unlink()

    exit_code = run_ingest()
    if exit_code != 0:
        print("Ingest failed!", file=sys.stderr)
        sys.exit(exit_code)

    save_hash(current_hash)
    print(f"Refresh complete. Revision hash: {current_hash[:12]}...")


if __name__ == "__main__":
    main()
