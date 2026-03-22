"""Shared content-hashing utility for HTS chapter data."""

import hashlib
import json


def compute_chapter_hash(data: list) -> str:
    """Compute a deterministic SHA256 hash for a chapter's API response."""
    sorted_data = sorted(data, key=lambda e: e.get("htsno", ""))
    content = json.dumps(sorted_data, sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()
