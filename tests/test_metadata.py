"""Tests for metadata.json — Datasette configuration."""

import json
import pytest
from pathlib import Path


METADATA_PATH = Path(__file__).parent.parent / "metadata.json"


class TestMetadataStructure:
    """Validate metadata.json structure for Datasette."""

    @pytest.fixture(autouse=True)
    def load_metadata(self):
        assert METADATA_PATH.exists(), "metadata.json must exist at project root"
        with open(METADATA_PATH) as f:
            self.metadata = json.load(f)

    def test_has_title(self):
        assert self.metadata["title"] == "US Harmonized Tariff Schedule"

    def test_has_description(self):
        assert "hts.usitc.gov" in self.metadata["description"]

    def test_has_license(self):
        assert self.metadata["license"] == "Public Domain"

    def test_has_source(self):
        assert self.metadata["source"] == "US International Trade Commission"
        assert "usitc.gov" in self.metadata["source_url"]

    def test_database_key_is_hts(self):
        """Datasette strips .db extension — key must be 'hts' not 'hts.db'."""
        assert "hts" in self.metadata["databases"]

    def test_hts_entries_table_configured(self):
        tables = self.metadata["databases"]["hts"]["tables"]
        assert "hts_entries" in tables

    def test_hts_entries_has_label_column(self):
        entry_config = self.metadata["databases"]["hts"]["tables"]["hts_entries"]
        assert entry_config["label_column"] == "hts_code"

    def test_hts_entries_has_unit_facet(self):
        entry_config = self.metadata["databases"]["hts"]["tables"]["hts_entries"]
        assert "unit" in entry_config["facets"]

    def test_hts_entries_no_chapter_id_facet(self):
        """chapter_id has 99 values — Datasette truncates at 30, so it's a bad facet."""
        entry_config = self.metadata["databases"]["hts"]["tables"]["hts_entries"]
        assert "chapter_id" not in entry_config.get("facets", [])

    def test_chapters_table_configured(self):
        tables = self.metadata["databases"]["hts"]["tables"]
        assert "chapters" in tables

    def test_chapters_label_column_is_number(self):
        """chapters.description is useless ('Chapter 01'), number is better."""
        chapter_config = self.metadata["databases"]["hts"]["tables"]["chapters"]
        assert chapter_config["label_column"] == "number"

    def test_hts_entries_has_sortable_columns(self):
        entry_config = self.metadata["databases"]["hts"]["tables"]["hts_entries"]
        sortable = entry_config["sortable_columns"]
        assert "hts_code" in sortable
        assert "chapter_id" in sortable
