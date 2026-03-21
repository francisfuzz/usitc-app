# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**usitc-app** is a Harmonized Tariff Schedule (HTS) lookup service built in Python. It downloads tariff classification data from the US International Trade Commission's public API, stores it in SQLite, and exposes it through two interfaces:
1. **CLI** (`hts.py`) — terminal-based lookups for developers
2. **MCP Server** (`mcp_server.py`) — Model Context Protocol tools for AI agents

All development runs in Docker. No Python, pip, or virtualenv required on the host.

## Architecture

### Data Layer
- **Source:** https://hts.usitc.gov/reststop/ (public government API, no auth required)
- **Schema:** Two tables in `data/hts.db`:
  - `chapters` — HTS chapters (01-99), with descriptions and counts
  - `hts_entries` — ~134K tariff entries with rates, units, indent level, footnotes
- **Indexes:** `hts_code` (exact lookups), `description` (substring search)

### Application Layer
| File | Purpose |
|------|---------|
| `scripts/ingest.py` | Download HTS data from API, iterate chapters 01-99, parse JSON, insert into SQLite |
| `scripts/refresh.py` | Detect HTS data changes via content-hash probe, re-ingest if changed |
| `hts.py` | CLI entrypoint (typer) with `search`, `code`, `chapter` commands |
| `mcp_server.py` | Expose four tools over MCP stdio: `search_hts`, `get_code`, `list_chapter`, `get_chapters` |

### Key Patterns
- **Database connections:** Each command opens/closes a connection in a try-finally block. No connection pooling needed for CLI/MCP (low concurrency).
- **Formatting:** Two helper functions in `hts.py` (`format_entry_as_dict`, `format_entry_for_table`) standardize output across CLI table views and JSON responses.
- **JSON output:** CLI uses `print()` (not Rich `console.print()`) for all JSON output to avoid ANSI control character injection. Rich is only used for table display.
- **MCP tools:** Return JSON strings (not objects), matching MCP SDK conventions. Tool docstrings are exposed as help text to Claude.
- **Revision detection:** `scripts/refresh.py` hashes a probe chapter (01) response and compares against `data/last_revision.txt`. Since `/reststop/releases` returns 404, this content-hash approach is the alternative.

## Running & Development

### Docker Setup (one-time)
```bash
docker build -t hts-local .
```

### Run Commands

**Ingest data (if `data/hts.db` doesn't exist):**
```bash
docker run --rm -v "$(pwd)/data:/app/data" hts-local scripts/ingest.py
```

**CLI usage (after ingest):**
```bash
docker run --rm -v "$(pwd)/data:/app/data" hts-local hts.py search "copper wire"
docker run --rm -v "$(pwd)/data:/app/data" hts-local hts.py code 7408.11
docker run --rm -v "$(pwd)/data:/app/data" hts-local hts.py chapter 74
docker run --rm -v "$(pwd)/data:/app/data" hts-local hts.py --help
```

**Refresh data (check for updates and re-ingest if changed):**
```bash
docker run --rm -v "$(pwd)/data:/app/data" hts-local scripts/refresh.py
```

**MCP server (stdio, for Claude Desktop integration):**
```bash
docker run --rm -i -v "$(pwd)/data:/app/data" hts-local mcp_server.py
```

### Running Tests
```bash
docker run --rm hts-local -m pytest tests/ -v
```

The test suite (35 tests) covers CLI commands, MCP server tools, and edge cases using an in-memory SQLite fixture. No real database or API access needed.

### Testing a Command Locally (without Docker)
If you have Python 3.12+ installed:
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Now test directly
python hts.py search "titanium"
python hts.py code 0101.21.00

# Or verify DB directly
python -c "import sqlite3; db = sqlite3.connect('data/hts.db'); print(db.execute('SELECT COUNT(*) FROM hts_entries').fetchone()[0])"
```

## Common Development Tasks

### Add a New CLI Command
1. Add a `@app.command()` function in `hts.py`
2. Use `typer.Argument()` for positional args, `typer.Option()` for flags
3. Follow the pattern: connect to DB → execute query → format output (JSON or table) → close DB
4. For `--json` output, use `print()` — never `console.print()` (Rich injects control characters)
5. Update the table schema in both `format_entry_for_table` and `format_entry_as_dict` if querying new columns
6. Add corresponding tests in `tests/test_cli.py`

### Add a New MCP Tool
1. Add a `@mcp.tool()` function in `mcp_server.py`
2. Docstring becomes the tool description (shown to Claude)
3. Always return a JSON string (`json.dumps()`)
4. Follow the DB pattern: open → execute → format → close
5. Handle errors gracefully (return JSON error object, don't raise)
6. Add corresponding tests in `tests/test_mcp.py`

### Update the SQLite Schema
1. Edit `create_schema()` in `scripts/ingest.py`
2. Re-run ingest to rebuild: `docker run --rm -v "$(pwd)/data:/app/data" hts-local scripts/ingest.py` (will recreate tables)
3. Update column references in formatting functions if needed

### Verify Data Integrity
```bash
# Count entries by chapter
docker run --rm -v "$(pwd)/data:/app/data" hts-local python -c "
import sqlite3
db = sqlite3.connect('data/hts.db')
result = db.execute('SELECT COUNT(*) FROM hts_entries').fetchone()[0]
print(f'Total entries: {result}')
"

# Quick smoke test
docker run --rm -v "$(pwd)/data:/app/data" hts-local hts.py code 0101.21.00
```

## API & Data Notes

### HTS API Endpoint
```
GET https://hts.usitc.gov/reststop/search?keyword=chapter%20XX&limit=5000
```
- No authentication required (public endpoint)
- Returns flat JSON array of entries
- All 99 chapters can be fetched in parallel (~15-20s for full ingest)
- The original plan endpoint (`/exportSections?format=JSON`) is no longer operational

### Data Model
Each `hts_entries` row contains:
- `hts_code` — tariff code (e.g., "7408.11.30")
- `description` — product description
- `indent` — hierarchy level (0 = chapter, 1 = heading, etc.)
- `unit` — measurement unit (e.g., "kg", "liters")
- `general_rate`, `special_rate`, `column2_rate` — duty rates (strings like "5%", "Free")
- `footnotes` — JSON string of footnote objects (may be empty string)
- `chapter_id` — foreign key to `chapters` table

Note: The CLI SELECT queries omit `footnotes` — the `format_entry_as_dict` column list has 9 columns. The MCP server queries 6 columns (no `id`, `indent`, `footnotes`, `chapter_id`).

## MCP Server Integration (Claude Desktop)

To use the HTS tools in Claude Desktop:

```json
{
  "mcpServers": {
    "hts": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-v", "/absolute/path/to/usitc-app/data:/app/data",
        "hts-local",
        "mcp_server.py"
      ]
    }
  }
}
```

The server uses stdio transport (no port exposed). Claude Desktop spawns the container, communicates over stdin/stdout, and the container exits cleanly when the session ends.

## Known Limitations

- **Single-threaded CLI** — no parallel queries; acceptable for interactive lookups
- **No pagination in CLI search** — hardcoded limit of 10 results; use `--limit` flag to increase
- **No full-text search** — uses simple LIKE queries; could upgrade to SQLite FTS5 for better relevance
- **Revision detection is approximate** — `scripts/refresh.py` probes chapter 01 only; a change in another chapter without a chapter 01 change would be missed
- **`format_entry_as_dict` column mapping** — uses positional `zip` against hardcoded column names; fragile if the SELECT changes. Consider using `cursor.description` or named tuples.

## Debugging

**Database locked error:**
- Likely a stale connection. Ensure all CLI commands close the DB in a finally block.
- If Docker container hangs, `docker ps` to find the container ID, then `docker kill <id>`.

**"hts.db not found" error:**
- Run the ingest script first to populate `data/hts.db`.

**MCP server not starting:**
- Check that the data volume is mounted and readable: `docker run --rm -v "$(pwd)/data:/app/data" hts-local ls -la /app/data/`

**Slow searches:**
- Add missing indexes if querying new columns; see `scripts/ingest.py:create_schema()`.
