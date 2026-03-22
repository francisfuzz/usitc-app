"""Tests for the public Python API module."""

from unittest.mock import patch

import tariff_everywhere


def test_search_hts_returns_dicts(test_db):
    """search_hts returns matching entries as dictionaries."""
    results = tariff_everywhere.search_hts("copper", limit=2)

    assert len(results) == 2
    assert results[0]["hts_code"].startswith("74")
    assert "description" in results[0]
    assert "general_rate" in results[0]


def test_lookup_code_returns_single_entry(test_db):
    """lookup_code returns a single matching entry."""
    entry = tariff_everywhere.lookup_code("7408.11.30")

    assert entry is not None
    assert entry["hts_code"] == "7408.11.30"
    assert entry["general_rate"] == "3%"


def test_lookup_code_returns_none_for_unknown_code(test_db):
    """lookup_code returns None when the HTS code is not found."""
    assert tariff_everywhere.lookup_code("9999.99.99") is None


def test_list_chapter_zero_pads_numbers(test_db):
    """list_chapter accepts single-digit chapter numbers."""
    results = tariff_everywhere.list_chapter("7")

    assert len(results) > 0
    assert all(result["hts_code"].startswith("07") for result in results)


def test_get_chapters_returns_counts(test_db):
    """get_chapters returns chapter summaries with entry counts."""
    chapters = tariff_everywhere.get_chapters()

    assert chapters == sorted(chapters, key=lambda chapter: chapter["number"])
    assert chapters[0]["entry_count"] > 0
    assert "last_checked_at" in chapters[0]
    assert "last_changed_at" in chapters[0]


def test_search_hts_raises_file_not_found_for_missing_database():
    """search_hts surfaces database setup errors to callers."""
    with patch("tariff_everywhere.hts_core.get_db", side_effect=FileNotFoundError("data/hts.db not found")):
        try:
            tariff_everywhere.search_hts("copper")
        except FileNotFoundError as exc:
            assert "not found" in str(exc)
        else:
            raise AssertionError("Expected FileNotFoundError")
