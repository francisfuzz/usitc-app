"""Tests for HTS chapter title enrichment."""

import sqlite3
import pytest


class TestChapterTitles:
    """Verify chapter titles are real descriptions, not 'Chapter XX'."""

    def test_titles_mapping_has_99_chapters(self):
        from scripts.chapter_titles import HTS_CHAPTER_TITLES
        assert len(HTS_CHAPTER_TITLES) == 99

    def test_titles_are_not_placeholder(self):
        from scripts.chapter_titles import HTS_CHAPTER_TITLES
        for num, title in HTS_CHAPTER_TITLES.items():
            assert not title.startswith("Chapter "), f"Chapter {num} still has placeholder title"

    def test_well_known_titles(self):
        from scripts.chapter_titles import HTS_CHAPTER_TITLES
        assert HTS_CHAPTER_TITLES["01"] == "Live Animals"
        assert HTS_CHAPTER_TITLES["74"] == "Copper and Articles Thereof"
        assert HTS_CHAPTER_TITLES["99"] == "Temporary Legislation; Temporary Modifications Proclaimed Pursuant to Trade Agreements Legislation; Additional Import Restrictions Proclaimed Pursuant to Section 22 of the Agricultural Adjustment Act, as Amended"

    def test_update_chapter_titles_in_db(self, tmp_path):
        """update_chapter_titles should replace placeholder descriptions."""
        from scripts.chapter_titles import HTS_CHAPTER_TITLES, update_chapter_titles

        db_path = tmp_path / "hts.db"
        db = sqlite3.connect(str(db_path))
        db.execute("""
            CREATE TABLE chapters (
                id INTEGER PRIMARY KEY,
                number TEXT NOT NULL UNIQUE,
                description TEXT
            )
        """)
        db.execute("INSERT INTO chapters (number, description) VALUES ('01', 'Chapter 01')")
        db.execute("INSERT INTO chapters (number, description) VALUES ('74', 'Chapter 74')")
        db.commit()

        update_chapter_titles(str(db_path))

        rows = db.execute("SELECT number, description FROM chapters ORDER BY number").fetchall()
        db.close()

        assert rows[0] == ("01", "Live Animals")
        assert rows[1] == ("74", "Copper and Articles Thereof")

    def test_update_is_idempotent(self, tmp_path):
        """Running update_chapter_titles twice should not error."""
        from scripts.chapter_titles import update_chapter_titles

        db_path = tmp_path / "hts.db"
        db = sqlite3.connect(str(db_path))
        db.execute("""
            CREATE TABLE chapters (
                id INTEGER PRIMARY KEY,
                number TEXT NOT NULL UNIQUE,
                description TEXT
            )
        """)
        db.execute("INSERT INTO chapters (number, description) VALUES ('01', 'Chapter 01')")
        db.commit()
        db.close()

        update_chapter_titles(str(db_path))
        update_chapter_titles(str(db_path))  # should not raise

        db = sqlite3.connect(str(db_path))
        row = db.execute("SELECT description FROM chapters WHERE number='01'").fetchone()
        db.close()
        assert row[0] == "Live Animals"
