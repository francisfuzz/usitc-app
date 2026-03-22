"""Tests for mcp_server.py MCP tools."""

import json

import pytest

from mcp_server import search_hts, get_code, list_chapter, get_chapters, get_data_freshness


# --- search_hts ---


def test_search_hts_returns_matches(test_db):
    result = json.loads(search_hts("copper"))
    assert isinstance(result, list)
    assert len(result) > 0
    assert all("hts_code" in e for e in result)


def test_search_hts_limit(test_db):
    result = json.loads(search_hts("copper", limit=2))
    assert len(result) <= 2


def test_search_hts_empty_keyword(test_db):
    result = json.loads(search_hts(""))
    assert isinstance(result, list)
    # Empty keyword with LIKE '%%' should return results
    assert len(result) > 0


def test_search_hts_no_matches(test_db):
    result = json.loads(search_hts("xyznonexistent"))
    assert result == []


# --- get_code ---


def test_get_code_known(test_db):
    result = json.loads(get_code("0101.21.00"))
    assert result["hts_code"] == "0101.21.00"
    assert result["description"] == "Live purebred breeding horses"
    assert result["unit"] == "No."
    assert result["general_rate"] == "Free"
    assert result["special_rate"] == "Free"
    assert result["column2_rate"] == "Free"


def test_get_code_all_six_fields(test_db):
    result = json.loads(get_code("7408.11.30"))
    expected_fields = {"hts_code", "description", "unit", "general_rate", "special_rate", "column2_rate"}
    assert set(result.keys()) == expected_fields


def test_get_code_unknown(test_db):
    result = json.loads(get_code("9999.99.99"))
    assert "error" in result


def test_get_code_empty_rates(test_db):
    """Entry with empty rates returns empty strings, not null."""
    result = json.loads(get_code("7408.00.00"))
    assert result["general_rate"] == ""
    assert result["special_rate"] == ""
    assert result["column2_rate"] == ""
    assert result["unit"] == ""


# --- list_chapter ---


def test_list_chapter_returns_entries(test_db):
    result = json.loads(list_chapter("74"))
    assert isinstance(result, list)
    assert len(result) > 0


def test_list_chapter_sorted(test_db):
    result = json.loads(list_chapter("74"))
    codes = [e["hts_code"] for e in result]
    assert codes == sorted(codes)


def test_list_chapter_zero_padding(test_db):
    """Single-digit chapter '7' should be padded to '07'."""
    result = json.loads(list_chapter("7"))
    assert len(result) > 0
    assert all(e["hts_code"].startswith("07") for e in result)


def test_list_chapter_nonexistent(test_db):
    result = json.loads(list_chapter("99"))
    assert result == []


# --- get_chapters ---


def test_get_chapters_returns_all(test_db):
    result = json.loads(get_chapters())
    assert isinstance(result, list)
    assert len(result) == 3  # 3 chapters in fixture


def test_get_chapters_fields(test_db):
    result = json.loads(get_chapters())
    for chapter in result:
        assert "number" in chapter
        assert "description" in chapter
        assert "entry_count" in chapter
        assert "last_checked_at" in chapter
        assert "last_changed_at" in chapter


def test_get_chapters_entry_counts(test_db):
    """Entry counts should match direct SQL count."""
    import sqlite3
    db = sqlite3.connect(str(test_db))
    try:
        result = json.loads(get_chapters())
        for chapter in result:
            num = chapter["number"]
            cursor = db.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM hts_entries WHERE hts_code LIKE ?",
                (f"{num}%",),
            )
            # Note: get_chapters uses chapter_id join, not LIKE, so use that for verification
            cursor.execute(
                """SELECT COUNT(h.id) FROM chapters c
                   LEFT JOIN hts_entries h ON c.id = h.chapter_id
                   WHERE c.number = ?""",
                (num,),
            )
            expected = cursor.fetchone()[0]
            assert chapter["entry_count"] == expected, f"Chapter {num}: expected {expected}, got {chapter['entry_count']}"
    finally:
        db.close()


def test_get_chapters_sorted(test_db):
    result = json.loads(get_chapters())
    numbers = [c["number"] for c in result]
    assert numbers == sorted(numbers)


def test_get_chapters_timestamps(test_db):
    """Chapters include freshness timestamps."""
    result = json.loads(get_chapters())
    for chapter in result:
        assert chapter["last_checked_at"] == "2026-03-21T04:00:00+00:00"
        assert chapter["last_changed_at"] == "2026-03-15T04:00:00+00:00"


# --- get_data_freshness ---


def test_get_data_freshness_structure(test_db):
    """Freshness response has expected top-level fields."""
    result = json.loads(get_data_freshness())
    assert result["last_full_refresh"] == "2026-03-21T04:00:00+00:00"
    assert result["refresh_duration_secs"] == 18.4
    assert result["chapters_changed_in_last_refresh"] == 3
    assert result["total_chapters"] == 99


def test_get_data_freshness_chapters(test_db):
    """Freshness response includes per-chapter timestamps."""
    result = json.loads(get_data_freshness())
    assert "chapters" in result
    assert isinstance(result["chapters"], list)
    assert len(result["chapters"]) == 3
    for chapter in result["chapters"]:
        assert "number" in chapter
        assert "last_checked_at" in chapter
        assert "last_changed_at" in chapter


def test_get_data_freshness_chapters_sorted(test_db):
    """Chapters in freshness response are sorted by number."""
    result = json.loads(get_data_freshness())
    numbers = [c["number"] for c in result["chapters"]]
    assert numbers == sorted(numbers)
