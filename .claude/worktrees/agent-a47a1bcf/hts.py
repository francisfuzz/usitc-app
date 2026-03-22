#!/usr/bin/env python3
"""HTS CLI for tariff lookups."""

import sqlite3
import json
import os
from typing import Optional
from pathlib import Path

import typer
from rich.table import Table
from rich.console import Console

app = typer.Typer(help="HTS (Harmonized Tariff Schedule) lookup tool")
console = Console()


def get_db() -> sqlite3.Connection:
    """Get database connection."""
    db_path = Path("data/hts.db")
    if not db_path.exists():
        console.print("[red]Error: data/hts.db not found. Run ingest first.[/red]")
        raise typer.Exit(1)
    return sqlite3.connect(str(db_path))


def format_entry_as_dict(row: tuple) -> dict:
    """Convert database row to dictionary."""
    columns = ["id", "hts_code", "indent", "description", "unit", "general_rate", "special_rate", "column2_rate", "chapter_id"]
    return dict(zip(columns, row))


def format_entry_for_table(row: tuple) -> list:
    """Format row for table display."""
    _, hts_code, _, description, unit, general_rate, special_rate, column2_rate, _ = row
    return [
        hts_code or "",
        description or "",
        general_rate or "",
        special_rate or "",
        column2_rate or ""
    ]


@app.command()
def search(
    keyword: str = typer.Argument(..., help="Keyword to search for"),
    limit: int = typer.Option(10, "--limit", "-l", help="Maximum results to return"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON")
) -> None:
    """Search HTS entries by keyword in description."""
    db = get_db()
    try:
        cursor = db.cursor()

        # Search in description column (case insensitive)
        query = """
            SELECT id, hts_code, indent, description, unit, general_rate, special_rate, column2_rate, chapter_id
            FROM hts_entries
            WHERE description LIKE ?
            LIMIT ?
        """
        search_term = f"%{keyword}%"
        cursor.execute(query, (search_term, limit))
        rows = cursor.fetchall()

        if not rows:
            if json_output:
                print(json.dumps([]))
            else:
                console.print(f"[yellow]No results found for '{keyword}'[/yellow]")
            return

        if json_output:
            results = [format_entry_as_dict(row) for row in rows]
            print(json.dumps(results, indent=2))
        else:
            table = Table(title=f"Search results for '{keyword}'")
            table.add_column("HTS Code", style="cyan")
            table.add_column("Description", style="green")
            table.add_column("General Rate", style="magenta")
            table.add_column("Special Rate", style="blue")
            table.add_column("Column 2 Rate", style="yellow")

            for row in rows:
                table.add_row(*format_entry_for_table(row))

            console.print(table)

    finally:
        db.close()


@app.command()
def code(
    hts_code: str = typer.Argument(..., help="HTS code to look up"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON")
) -> None:
    """Look up a specific HTS code."""
    db = get_db()
    try:
        cursor = db.cursor()

        query = """
            SELECT id, hts_code, indent, description, unit, general_rate, special_rate, column2_rate, chapter_id
            FROM hts_entries
            WHERE hts_code = ?
            LIMIT 1
        """
        cursor.execute(query, (hts_code,))
        row = cursor.fetchone()

        if not row:
            if json_output:
                print(json.dumps(None))
            else:
                console.print(f"[yellow]HTS code '{hts_code}' not found[/yellow]")
            return

        if json_output:
            result = format_entry_as_dict(row)
            print(json.dumps(result, indent=2))
        else:
            table = Table(title=f"HTS Code: {hts_code}")
            table.add_column("Field", style="cyan")
            table.add_column("Value", style="green")

            _, hts_code_val, indent, description, unit, general_rate, special_rate, column2_rate, chapter_id = row

            fields = [
                ("HTS Code", hts_code_val or ""),
                ("Description", description or ""),
                ("Unit", unit or ""),
                ("Indent", str(indent) if indent is not None else ""),
                ("General Rate", general_rate or ""),
                ("Special Rate", special_rate or ""),
                ("Column 2 Rate", column2_rate or ""),
            ]

            for field_name, field_value in fields:
                table.add_row(field_name, field_value)

            console.print(table)

    finally:
        db.close()


@app.command()
def chapter(
    chapter_num: str = typer.Argument(..., help="Chapter number (e.g., 74, 01)"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON")
) -> None:
    """List all entries in a chapter."""
    db = get_db()
    try:
        cursor = db.cursor()

        # Pad chapter number to 2 digits
        chapter_num = chapter_num.zfill(2)

        query = """
            SELECT id, hts_code, indent, description, unit, general_rate, special_rate, column2_rate, chapter_id
            FROM hts_entries
            WHERE hts_code LIKE ?
            ORDER BY hts_code
        """
        search_pattern = f"{chapter_num}%"
        cursor.execute(query, (search_pattern,))
        rows = cursor.fetchall()

        if not rows:
            if json_output:
                print(json.dumps([]))
            else:
                console.print(f"[yellow]No entries found for chapter {chapter_num}[/yellow]")
            return

        if json_output:
            results = [format_entry_as_dict(row) for row in rows]
            print(json.dumps(results, indent=2))
        else:
            table = Table(title=f"Chapter {chapter_num} ({len(rows)} entries)")
            table.add_column("HTS Code", style="cyan")
            table.add_column("Description", style="green")
            table.add_column("General Rate", style="magenta")
            table.add_column("Special Rate", style="blue")
            table.add_column("Column 2 Rate", style="yellow")

            for row in rows:
                table.add_row(*format_entry_for_table(row))

            console.print(table)

    finally:
        db.close()


@app.command()
def chapters(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON")
) -> None:
    """List all chapters with descriptions and entry counts."""
    db = get_db()
    try:
        cursor = db.cursor()
        cursor.execute(
            """SELECT c.number, c.description, COUNT(h.id) as entry_count
               FROM chapters c
               LEFT JOIN hts_entries h ON c.id = h.chapter_id
               GROUP BY c.id
               ORDER BY c.number"""
        )
        rows = cursor.fetchall()

        if json_output:
            results = [
                {"number": r[0], "description": r[1] or "", "entry_count": r[2]}
                for r in rows
            ]
            print(json.dumps(results, indent=2))
        else:
            table = Table(title=f"HTS Chapters ({len(rows)} chapters)")
            table.add_column("Chapter", style="cyan")
            table.add_column("Description", style="green")
            table.add_column("Entries", style="magenta", justify="right")

            for number, description, entry_count in rows:
                table.add_row(number, description or "", str(entry_count))

            console.print(table)

    finally:
        db.close()


if __name__ == "__main__":
    app()
