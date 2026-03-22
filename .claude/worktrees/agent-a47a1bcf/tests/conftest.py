"""Shared test fixtures for HTS tests."""

import sqlite3
import tempfile
import os
import pytest
from pathlib import Path
from unittest.mock import patch


FIXTURE_ENTRIES = [
    # Chapter 01 entries (animals)
    {
        "hts_code": "0101.21.00",
        "indent": 2,
        "description": "Live purebred breeding horses",
        "unit": "No.",
        "general_rate": "Free",
        "special_rate": "Free",
        "column2_rate": "Free",
        "footnotes": "",
        "chapter": "01",
    },
    {
        "hts_code": "0101.29.00",
        "indent": 2,
        "description": "Live horses other than purebred breeding",
        "unit": "No.",
        "general_rate": "Free",
        "special_rate": "Free",
        "column2_rate": "20%",
        "footnotes": '[{"id": "1", "text": "See note 1"}]',
        "chapter": "01",
    },
    {
        "hts_code": "0101.30.00",
        "indent": 1,
        "description": "Live asses",
        "unit": "No.",
        "general_rate": "Free",
        "special_rate": "",
        "column2_rate": "6.8¢/kg",
        "footnotes": "",
        "chapter": "01",
    },
    {
        "hts_code": "0101.90.00",
        "indent": 1,
        "description": "Mules and hinnies, live",
        "unit": "",
        "general_rate": "",
        "special_rate": "",
        "column2_rate": "",
        "footnotes": "",
        "chapter": "01",
    },
    # Chapter 07 entries (vegetables) - tests zero-padding
    {
        "hts_code": "0701.10.00",
        "indent": 1,
        "description": "Seed potatoes",
        "unit": "kg",
        "general_rate": "Free",
        "special_rate": "Free",
        "column2_rate": "0.5¢/kg",
        "footnotes": "",
        "chapter": "07",
    },
    {
        "hts_code": "0701.90.10",
        "indent": 2,
        "description": "Yellow (Solanum tuberosum) seed certified by a state agency",
        "unit": "kg",
        "general_rate": "0.5%",
        "special_rate": "Free (A,AU,BH,CL,CO,D,E,IL,JO,KR,MA,OM,P,PA,PE,S,SG)",
        "column2_rate": "0.5¢/kg",
        "footnotes": "",
        "chapter": "07",
    },
    {
        "hts_code": "0701.90.50",
        "indent": 2,
        "description": "Other potatoes, fresh or chilled",
        "unit": "kg",
        "general_rate": "1.1¢/kg",
        "special_rate": "Free (A+,AU,BH,CL,CO,D,E,IL,JO,KR,MA,OM,P,PA,PE,S,SG)",
        "column2_rate": "0.5¢/kg",
        "footnotes": "",
        "chapter": "07",
    },
    {
        "hts_code": "0702.00.20",
        "indent": 1,
        "description": "Tomatoes, fresh or chilled, entered during March 1 through July 14, inclusive, or September 1 through November 14, inclusive, in any year",
        "unit": "kg",
        "general_rate": "2.8¢/kg",
        "special_rate": "Free (A+,AU,BH,CL,CO,D,E,IL,JO,KR,MA,OM,P,PA,PE,S,SG)",
        "column2_rate": "5.5¢/kg",
        "footnotes": '[{"id": "2", "text": "See subheading note 1"}]',
        "chapter": "07",
    },
    {
        "hts_code": "0702.00.40",
        "indent": 1,
        "description": "Tomatoes, fresh or chilled, entered at other times",
        "unit": "kg",
        "general_rate": "2.8¢/kg",
        "special_rate": "",
        "column2_rate": "5.5¢/kg",
        "footnotes": "",
        "chapter": "07",
    },
    {
        "hts_code": "0703.10.20",
        "indent": 2,
        "description": "Onion sets",
        "unit": "kg",
        "general_rate": "1.6¢/kg",
        "special_rate": "",
        "column2_rate": "3.3¢/kg",
        "footnotes": "",
        "chapter": "07",
    },
    # Chapter 74 entries (copper)
    {
        "hts_code": "7401.00.00",
        "indent": 0,
        "description": "Copper mattes; cement copper (precipitated copper)",
        "unit": "kg",
        "general_rate": "Free",
        "special_rate": "Free",
        "column2_rate": "Free",
        "footnotes": "",
        "chapter": "74",
    },
    {
        "hts_code": "7408.11.30",
        "indent": 3,
        "description": "Refined copper wire, of which the maximum cross-sectional dimension exceeds 9.5 mm",
        "unit": "kg",
        "general_rate": "3%",
        "special_rate": "Free (A,AU,BH,CL,CO,D,E,IL,JO,KR,MA,OM,P,PA,PE,S,SG)",
        "column2_rate": "8.5¢/kg",
        "footnotes": "",
        "chapter": "74",
    },
    {
        "hts_code": "7408.11.60",
        "indent": 3,
        "description": "Refined copper wire, of which the maximum cross-sectional dimension does not exceed 9.5 mm",
        "unit": "kg",
        "general_rate": "3%",
        "special_rate": "Free (A,AU,BH,CL,CO,D,E,IL,JO,KR,MA,OM,P,PA,PE,S,SG)",
        "column2_rate": "8.5¢/kg",
        "footnotes": "",
        "chapter": "74",
    },
    # Entry with empty rates (structural/hierarchy entry)
    {
        "hts_code": "7408.00.00",
        "indent": 0,
        "description": "Copper wire:",
        "unit": "",
        "general_rate": "",
        "special_rate": "",
        "column2_rate": "",
        "footnotes": "",
        "chapter": "74",
    },
    # Entry with very long description (1700+ chars)
    {
        "hts_code": "7408.99.99",
        "indent": 2,
        "description": (
            "Other copper wire, not elsewhere specified or included, including wire of copper alloys "
            "(other than copper-zinc base alloys (brass) or copper-nickel base alloys (cupro-nickel) "
            "or copper-nickel-zinc base alloys (nickel silver)), whether or not coated or plated with "
            "metal or clad with metal, or covered with insulating material, of a kind used in the "
            "manufacture of electrical apparatus, electrical machinery, or electrical equipment, or "
            "of a kind used in the construction of buildings, bridges, tunnels, or other structures, "
            "or of a kind used in the manufacture of vehicles, vessels, aircraft, or spacecraft, or "
            "of a kind used in the manufacture of instruments, apparatus, or appliances for measuring, "
            "checking, testing, navigating, or for other purposes, or of a kind used in medical, "
            "surgical, dental, or veterinary sciences, including items for diagnostics, monitoring, "
            "treatment, or rehabilitation purposes, or for use in laboratory research, development, "
            "or quality control operations, encompassing both standard and specialized applications "
            "across multiple industrial, commercial, and scientific sectors, with properties including "
            "but not limited to high electrical conductivity, thermal conductivity, corrosion resistance, "
            "and mechanical strength, suitable for both indoor and outdoor installation environments, "
            "meeting applicable ASTM, ISO, IEC, or equivalent national or international standards "
            "for composition, dimensions, tolerances, and performance characteristics, whether supplied "
            "in coils, reels, drums, or straight lengths, and whether or not annealed, drawn, or "
            "otherwise processed after initial production, including but not limited to tinned, "
            "silver-plated, nickel-plated, or gold-plated varieties for specialized electronic "
            "or telecommunications applications requiring enhanced surface properties"
        ),
        "unit": "kg",
        "general_rate": "3%",
        "special_rate": "Free (A,AU,BH)",
        "column2_rate": "40%",
        "footnotes": "",
        "chapter": "74",
    },
    # Entry with special characters
    {
        "hts_code": "7410.11.00",
        "indent": 2,
        "description": "Copper foil (whether or not printed, or backed with paper, paperboard, plastics or similar backing materials), of a thickness (excluding any backing) not exceeding 0.15 mm: Of refined copper: Not backed",
        "unit": "kg",
        "general_rate": "3%",
        "special_rate": "Free (A+,AU,BH,CL,CO,D,E,IL,JO,KR,MA,OM,P,PA,PE,S,SG)",
        "column2_rate": "40¢/kg + 35%",
        "footnotes": '[{"id": "3", "text": "Rate includes (5%) ad valorem"}]',
        "chapter": "74",
    },
]


def _create_test_db(db_path):
    """Create a test database with fixture data."""
    db = sqlite3.connect(str(db_path))
    cursor = db.cursor()

    cursor.execute("""
    CREATE TABLE chapters (
        id          INTEGER PRIMARY KEY,
        number      TEXT NOT NULL UNIQUE,
        description TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE hts_entries (
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

    cursor.execute("CREATE INDEX idx_hts_code ON hts_entries(hts_code)")
    cursor.execute("CREATE INDEX idx_description ON hts_entries(description)")

    # Insert chapters
    chapters = {"01": "Chapter 01", "07": "Chapter 07", "74": "Chapter 74"}
    chapter_ids = {}
    for num, desc in chapters.items():
        cursor.execute("INSERT INTO chapters (number, description) VALUES (?, ?)", (num, desc))
        chapter_ids[num] = cursor.lastrowid

    # Insert entries
    for entry in FIXTURE_ENTRIES:
        chapter_id = chapter_ids[entry["chapter"]]
        cursor.execute(
            """INSERT INTO hts_entries
               (hts_code, indent, description, unit, general_rate, special_rate, column2_rate, footnotes, chapter_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entry["hts_code"],
                entry["indent"],
                entry["description"],
                entry["unit"],
                entry["general_rate"],
                entry["special_rate"],
                entry["column2_rate"],
                entry["footnotes"],
                chapter_id,
            ),
        )

    db.commit()
    db.close()


@pytest.fixture
def test_db(tmp_path):
    """Create a temporary test database and patch DB_PATH / get_db for both hts.py and mcp_server.py."""
    db_path = tmp_path / "hts.db"
    _create_test_db(db_path)

    # Create the data/ directory structure that hts.py expects
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    # Symlink or copy to data/hts.db path
    data_db_path = data_dir / "hts.db"
    import shutil
    shutil.copy2(str(db_path), str(data_db_path))

    with patch("hts.get_db", lambda: sqlite3.connect(str(db_path))):
        with patch("mcp_server.get_db", lambda: sqlite3.connect(str(db_path))):
            with patch("mcp_server.DB_PATH", db_path):
                yield db_path
