"""Tests for hts.py CLI."""

import json
import sqlite3

import pytest
from typer.testing import CliRunner
from unittest.mock import patch
from pathlib import Path

from hts import app

runner = CliRunner()


# --- search command ---


def test_search_returns_matching_entries(test_db):
    result = runner.invoke(app, ["search", "copper"])
    assert result.exit_code == 0
    assert "copper" in result.output.lower()


def test_search_no_matches(test_db):
    result = runner.invoke(app, ["search", "xyznonexistent"])
    assert result.exit_code == 0
    assert "No results found" in result.output


def test_search_limit_flag(test_db):
    result = runner.invoke(app, ["search", "copper", "--limit", "2", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data) <= 2


def test_search_json_output(test_db):
    result = runner.invoke(app, ["search", "horse", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) > 0
    assert "hts_code" in data[0]


def test_search_case_insensitive(test_db):
    result = runner.invoke(app, ["search", "COPPER", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data) > 0
    # Verify it found lowercase "copper" entries
    descriptions = [e["description"].lower() for e in data]
    assert any("copper" in d for d in descriptions)


def test_search_empty_results_json(test_db):
    result = runner.invoke(app, ["search", "xyznonexistent", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data == []


# --- code command ---


def test_code_known_entry(test_db):
    result = runner.invoke(app, ["code", "0101.21.00"])
    assert result.exit_code == 0
    assert "purebred breeding horses" in result.output.lower()


def test_code_known_entry_json(test_db):
    result = runner.invoke(app, ["code", "0101.21.00", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["hts_code"] == "0101.21.00"
    assert data["description"] == "Live purebred breeding horses"
    assert data["general_rate"] == "Free"
    assert data["unit"] == "No."


def test_code_not_found(test_db):
    result = runner.invoke(app, ["code", "9999.99.99"])
    assert result.exit_code == 0
    assert "not found" in result.output.lower()


def test_code_not_found_json(test_db):
    result = runner.invoke(app, ["code", "9999.99.99", "--json"])
    assert result.exit_code == 0
    # hts.py outputs json.dumps(None) for not found
    assert result.output.strip() == "null"


# --- chapter command ---


def test_chapter_returns_entries(test_db):
    result = runner.invoke(app, ["chapter", "74"])
    assert result.exit_code == 0
    assert "copper" in result.output.lower()


def test_chapter_json_output(test_db):
    result = runner.invoke(app, ["chapter", "74", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) > 0


def test_chapter_zero_padding(test_db):
    """Chapter '7' should be treated as '07'."""
    result = runner.invoke(app, ["chapter", "7", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data) > 0
    assert all(e["hts_code"].startswith("07") for e in data)


def test_chapter_nonexistent(test_db):
    result = runner.invoke(app, ["chapter", "99", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data == []


def test_chapter_sorted_by_hts_code(test_db):
    result = runner.invoke(app, ["chapter", "74", "--json"])
    data = json.loads(result.output)
    codes = [e["hts_code"] for e in data]
    assert codes == sorted(codes)


# --- chapters command ---


def test_chapters_returns_all(test_db):
    """Lists all chapters with descriptions and entry counts."""
    result = runner.invoke(app, ["chapters"])
    assert result.exit_code == 0
    assert "01" in result.output
    assert "07" in result.output
    assert "74" in result.output


def test_chapters_json_output(test_db):
    """JSON output returns list with number, description, entry_count."""
    result = runner.invoke(app, ["chapters", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) == 3  # 3 chapters in fixture
    for ch in data:
        assert "number" in ch
        assert "description" in ch
        assert "entry_count" in ch


def test_chapters_entry_counts_accurate(test_db):
    """Entry counts match the actual number of entries per chapter."""
    result = runner.invoke(app, ["chapters", "--json"])
    data = json.loads(result.output)
    counts = {ch["number"]: ch["entry_count"] for ch in data}
    assert counts["01"] == 4
    assert counts["07"] == 6
    assert counts["74"] == 6


def test_chapters_sorted_by_number(test_db):
    """Chapters are sorted by number."""
    result = runner.invoke(app, ["chapters", "--json"])
    data = json.loads(result.output)
    numbers = [ch["number"] for ch in data]
    assert numbers == sorted(numbers)


# --- edge cases ---


def test_missing_database():
    """Missing database should exit with code 1, not a traceback."""
    with patch("hts.get_db") as mock_get_db:
        import typer
        mock_get_db.side_effect = typer.Exit(1)
        result = runner.invoke(app, ["search", "anything"])
        assert result.exit_code == 1


def test_entry_with_empty_rates(test_db):
    """Structural entry with all empty rates displays correctly."""
    result = runner.invoke(app, ["code", "7408.00.00", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["general_rate"] == ""
    assert data["special_rate"] == ""
    assert data["column2_rate"] == ""


def test_entry_with_long_description(test_db):
    """Entry with 1700+ char description doesn't break output."""
    result = runner.invoke(app, ["code", "7408.99.99", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data["description"]) > 1700


def test_special_characters_in_json(test_db):
    """Special characters (¢, %, parentheses) serialize correctly."""
    result = runner.invoke(app, ["code", "7410.11.00", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "¢" in data["column2_rate"]
    assert "%" in data["column2_rate"]

    result2 = runner.invoke(app, ["code", "0101.30.00", "--json"])
    data2 = json.loads(result2.output)
    assert "¢" in data2["column2_rate"]
