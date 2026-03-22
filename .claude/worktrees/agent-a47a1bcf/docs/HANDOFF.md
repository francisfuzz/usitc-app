# Handoff: hts-local

> Last updated: 2026-03-21
> Session: initial build (Steps 0–4 complete)

## Project Overview

A local HTS (Harmonized Tariff Schedule) lookup tool backed by SQLite, with a CLI and MCP server for agent use. Everything runs in Docker — no host Python required.

**Source data:** https://hts.usitc.gov/reststop/
**Full plan:** `docs/PLAN.md`
**API discovery notes:** `docs/LEARNING.md`

---

## What's Done

### Step 0 — Docker (`60ecee0`)

- `Dockerfile` — Python 3.12-slim, pip installs from `requirements.txt`, `data/` mount point
- `requirements.txt` — `requests`, `mcp`, `typer`, `rich`
- `.gitignore` — excludes `data/`, `__pycache__/`, etc.
- Image builds with `docker build -t hts-local .`

### Step 1–2 — Ingest (`50f9b5c`)

- `scripts/ingest.py` — fetches all 99 chapters from the USITC search API and loads into SQLite
- **Working endpoint:** `GET https://hts.usitc.gov/reststop/search?keyword=chapter%20XX&limit=5000`
- The plan's original endpoint (`/exportSections?format=JSON`) does not work — see `docs/LEARNING.md`
- **Dataset:** 28,750 unique HTS entries across 99 chapters, 14,413 with duty rates, 14,069 with footnotes
- Cross-chapter deduplication handled (entries appear in multiple chapter queries)
- Run: `docker run --rm -v "$(pwd)/data:/app/data" hts-local scripts/ingest.py`

### Step 3 — CLI (`704566a`)

- `hts.py` — typer-based CLI with three commands:
  - `search <keyword>` — LIKE search on description, default limit 10
  - `code <hts_code>` — exact code lookup
  - `chapter <num>` — list all entries in a chapter
- All commands support `--json` flag for structured output
- Rich tables for terminal display
- Run: `docker run --rm -v "$(pwd)/data:/app/data" hts-local hts.py <command>`

### Step 4 — MCP Server (`8185c98`)

- `mcp_server.py` — FastMCP server with stdio transport, 4 tools:
  - `search_hts(keyword, limit)` — keyword search
  - `get_code(hts_code)` — single entry lookup
  - `list_chapter(chapter)` — chapter listing
  - `get_chapters()` — chapter index with counts
- Verified over the wire: `initialize`, `tools/list`, `tools/call` all return correct JSON-RPC
- Run: `docker run --rm -i -v "$(pwd)/data:/app/data" hts-local mcp_server.py`
- Claude Desktop config:
  ```json
  {
    "mcpServers": {
      "hts": {
        "command": "docker",
        "args": ["run", "--rm", "-i", "-v", "/absolute/path/to/data:/app/data", "hts-local", "mcp_server.py"]
      }
    }
  }
  ```

### Documentation (`838ce47`)

- `docs/PLAN.md` — updated with correct API endpoint (original was broken)
- `docs/LEARNING.md` — full writeup of API discovery, why the original approach failed, verification process

---

## What's Not Done

### Step 5 — Revision Refresh (`scripts/refresh.py`)

Write `scripts/refresh.py` that:
1. Checks for new HTS revisions (the plan references `GET /reststop/releases` but that endpoint returned 404 — needs discovery like Step 1–2)
2. Compares latest revision against `data/last_revision.txt`
3. If changed: re-runs ingest, updates `last_revision.txt`
4. If unchanged: prints "Already up to date"

**Note:** The `/reststop/releases` endpoint does not work. You will need to find an alternative way to detect new revisions. Check `docs/LEARNING.md` for context on API exploration patterns that worked.

### Step 6 — Testing and Validation

The original plan called for manual smoke tests. That is not sufficient. Write proper automated tests.

---

## TODO: Automated Tests

### Add `pytest` to `requirements.txt`

After adding, rebuild the Docker image.

### Tests for `hts.py` CLI (`tests/test_cli.py`)

Use a small in-memory or temp SQLite database with known fixture data. Do not hit the real API.

Test cases to cover:

**`search` command:**
- Returns matching entries for a known keyword
- Returns empty result for a keyword with no matches
- `--limit` flag restricts result count
- `--json` flag outputs valid JSON array
- Case-insensitive matching works (search "COPPER" finds "copper")

**`code` command:**
- Returns correct entry for a known HTS code (verify all fields: description, rates, unit)
- Returns not-found message for a nonexistent code
- `--json` flag outputs valid JSON object

**`chapter` command:**
- Returns all entries for a chapter
- Single-digit chapter numbers are zero-padded (chapter "7" → "07")
- Returns empty result for nonexistent chapter
- `--json` flag outputs valid JSON array
- Entries are sorted by HTS code

**Edge cases:**
- Missing database file raises clean error (exit code 1, not a traceback)
- Entry with all empty rate fields (structural/hierarchy entry) displays correctly
- Entry with very long description (1700+ chars) doesn't break output
- Special characters in descriptions (¢, %, parentheses) serialize correctly in JSON

### Tests for `mcp_server.py` (`tests/test_mcp.py`)

Use the same fixture database. Test the tool functions directly (call `search_hts()`, `get_code()`, etc.) and verify the returned JSON strings.

Test cases to cover:

**`search_hts`:**
- Returns JSON array of matching entries
- `limit` parameter is respected
- Empty keyword returns results (not an error)
- No matches returns empty JSON array `[]`

**`get_code`:**
- Known code returns JSON object with all 6 fields (`hts_code`, `description`, `unit`, `general_rate`, `special_rate`, `column2_rate`)
- Unknown code returns JSON with `error` key
- Code with empty rates returns empty strings (not null)

**`list_chapter`:**
- Returns all entries for a chapter, sorted by HTS code
- Single-digit chapter input is zero-padded
- Nonexistent chapter returns empty array

**`get_chapters`:**
- Returns all chapters with `number`, `description`, `entry_count` fields
- Entry counts are accurate (cross-check against direct SQL count)
- Chapters are sorted by number

**MCP protocol integration (optional but recommended):**
- Server responds to `initialize` with correct protocol version
- `tools/list` returns all 4 tools with valid schemas
- `tools/call` with valid args returns `isError: false`
- `tools/call` with unknown tool name returns error

### Test Fixture

Create a shared fixture (`tests/conftest.py`) that:
1. Creates a temp SQLite database with ~20 known entries across 3 chapters
2. Includes entries with: full rates, empty rates, long descriptions, special characters, footnotes
3. Patches `DB_PATH` / `get_db()` so no real database is needed
4. Tears down after each test

### Running Tests

```bash
# Add pytest to requirements.txt, rebuild image
docker run --rm hts-local -m pytest tests/ -v
```

---

## Project Structure (Current)

```
hts-local/
├── data/                   # Mounted volume — hts.db lives here (gitignored)
├── docs/
│   ├── HANDOFF.md          # ← You are here
│   ├── LEARNING.md         # API discovery notes
│   └── PLAN.md             # Original build plan (updated)
├── scripts/
│   └── ingest.py           # Downloads + loads all 99 chapters into SQLite
├── hts.py                  # CLI: search, code, chapter commands
├── mcp_server.py           # MCP server: 4 tools, stdio transport
├── Dockerfile
├── requirements.txt
└── .gitignore
```

---

## Database Schema

```sql
CREATE TABLE chapters (
    id          INTEGER PRIMARY KEY,
    number      TEXT NOT NULL UNIQUE,  -- "01"–"99"
    description TEXT
);

CREATE TABLE hts_entries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    hts_code        TEXT NOT NULL UNIQUE,  -- e.g. "0201.10.10"
    indent          INTEGER,
    description     TEXT,
    unit            TEXT,
    general_rate    TEXT,
    special_rate    TEXT,
    column2_rate    TEXT,
    footnotes       TEXT,                  -- JSON string
    chapter_id      INTEGER REFERENCES chapters(id)
);
```

**Note:** `hts.py` (written in Step 3) queries 9 columns from `hts_entries` but the schema now has 10 (the `footnotes` column was added in Step 1–2 rewrite). The CLI's `SELECT` does not include `footnotes`, so `format_entry_as_dict` maps to 9 columns. This works but means the column-name mapping in `format_entry_as_dict` is fragile — if the SELECT changes, the zip will silently mismatch. The test suite should catch this.

---

## Docker Aliases (for convenience)

```bash
alias hts-run='docker run --rm -v "$(pwd)/data:/app/data" hts-local'
alias hts-mcp='docker run --rm -i -v "$(pwd)/data:/app/data" hts-local mcp_server.py'
```

---

## Known Issues

1. **`/reststop/releases` returns 404** — Step 5 refresh script cannot use the endpoint from the plan. Needs alternative discovery.
2. **Cross-chapter duplicates** — The search API returns the same HTS code in multiple chapter queries. Ingest handles this with `INSERT ... UNIQUE` + skip, but it means 134K API results collapse to 28.7K unique entries. This is correct behavior, not data loss.
3. **`format_entry_as_dict` column mapping** — Uses positional zip against hardcoded column names. Fragile if SELECT changes. Should use `cursor.description` or named tuples instead.
