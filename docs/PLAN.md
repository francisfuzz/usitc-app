# hts-local: Build Plan

A local HTS (Harmonized Tariff Schedule) lookup tool backed by SQLite, with a CLI and MCP server for agent use.

**Source:** https://hts.usitc.gov/reststop/  
**Target:** ~60 min build, Git-checkpointed in 5 steps  
**Dependencies:** Docker only — nothing installed on the host machine

---

## How Docker is used here

Everything runs inside a single image built from `Dockerfile`. The `data/` folder is mounted as a volume so the SQLite database persists on your host across container runs without being in the image itself.

**Two aliases do all the work** — add these to your shell profile once:

```bash
# Run any one-off command (ingest, refresh, smoke tests)
alias hts-run='docker run --rm -v "$(pwd)/data:/app/data" hts-local'

# Run the MCP server (stays alive, stdio transport)
alias hts-mcp='docker run --rm -i -v "$(pwd)/data:/app/data" hts-local python mcp_server.py'
```

After that, every interaction in this plan is just `hts-run <command>`. No `python`, no `pip`, no virtualenv — ever.

---

## Project structure

```
hts-local/
├── data/                   # Mounted volume — persists hts.db on host (gitignored)
│   └── hts.db
├── scripts/
│   ├── ingest.py           # Download + parse HTS JSON into SQLite
│   └── refresh.py          # Check for new revisions, re-ingest if changed
├── hts.py                  # CLI entrypoint
├── mcp_server.py           # MCP server exposing SQLite as tools
├── Dockerfile
├── requirements.txt
└── .gitignore
```

---

## Step 0 — Dockerfile (~ 5 min)

**Goal:** One image that runs the CLI, scripts, and MCP server. Build once, use everywhere.

### Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# data/ is a mount point — ensure the directory exists inside the image
RUN mkdir -p /app/data

ENTRYPOINT ["python"]
CMD ["hts.py", "--help"]
```

### requirements.txt

```
requests
mcp
typer
rich
```

### .gitignore

```
data/
__pycache__/
*.pyc
```

### Build command

```bash
docker build -t hts-local .
```

This is the only build you'll ever run. All subsequent steps use `hts-run` (the alias from above).

### Git checkpoint

```bash
git add Dockerfile requirements.txt .gitignore
git commit -m "chore: step0 docker — base image + volume setup"
```

---

## Step 1+2 — Ingest (~ 1 min)

**Goal:** Download the complete HTS schedule (134,019 entries) as JSON and load it into SQLite.

### API endpoint

```
GET https://hts.usitc.gov/reststop/search?keyword=chapter%20XX&limit=5000
```

**Important:** The plan's original endpoint (`/exportSections?format=JSON`) is not operational. The working endpoint uses chapter-based queries: iterate chapters 01-99, each returns complete chapter data in a flat JSON array. See `docs/LEARNING.md` for discovery details.

### SQLite schema

```sql
CREATE TABLE chapters (
    id          INTEGER PRIMARY KEY,
    number      TEXT NOT NULL,
    description TEXT
);

CREATE TABLE hts_entries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    hts_code        TEXT NOT NULL,
    indent          INTEGER,
    description     TEXT,
    unit            TEXT,
    general_rate    TEXT,
    special_rate    TEXT,
    column2_rate    TEXT,
    chapter_id      INTEGER REFERENCES chapters(id)
);

CREATE INDEX idx_hts_code ON hts_entries(hts_code);
CREATE INDEX idx_description ON hts_entries(description);
```

### Task

Write `scripts/ingest.py` that:
1. Iterates chapters 01-99
2. For each chapter, GETs `/reststop/search?keyword=chapter%20XX&limit=5000`
3. Parses flat JSON array and inserts into `hts_entries`
4. Saves `data/hts.db`
5. Prints a summary: `Loaded N entries across M chapters`

### Run it

```bash
hts-run scripts/ingest.py
# Output: Loaded 134019 entries across 99 chapters
```

Note: First run takes ~1 minute. Uses requests library to parallelize chapter fetches (all 99 chapters in ~15-20 seconds total, database inserts add the rest).

### Git checkpoint

```bash
git add scripts/ingest.py
git commit -m "feat: step1-2 ingest — download + SQLite loader"
```

---

## Step 3 — CLI (~ 10 min)

**Goal:** A fast command-line tool for developer lookups.

### Commands

```bash
# Keyword search across descriptions
hts search "copper wire"

# Exact code lookup
hts code 7408.11

# List all headings in a chapter
hts chapter 74
```

### Output format (default: table, --json flag for JSON)

```
7408.11.30  Copper wire, of which the max cross-section > 6mm    5%    Free    35%
7408.11.60  Copper wire, other                                    3%    Free    35%
```

### Task

Write `hts.py` using `typer` that:
1. Connects to `data/hts.db`
2. Implements the three commands above
3. Supports `--json` flag for structured output
4. Shows a clean `--help`

### Run it

```bash
hts-run hts.py search "copper wire"
hts-run hts.py code 7408.11
hts-run hts.py chapter 74
```

### Git checkpoint

```bash
git add hts.py
git commit -m "feat: step3 cli — search, code, chapter commands"
```

---

## Step 4 — MCP server (~ 25 min)

**Goal:** Expose the SQLite database as MCP tools so Claude and other agents can do tariff lookups without any manual steps.

### Tools to expose

| Tool | Args | Returns |
|---|---|---|
| `search_hts` | `keyword: str, limit: int = 10` | list of matching entries |
| `get_code` | `hts_code: str` | single entry with all rate columns |
| `list_chapter` | `chapter: str` | all entries in that chapter |
| `get_chapters` | — | all chapter numbers + descriptions |

### Response shape (each entry)

```json
{
  "hts_code": "7408.11.30",
  "description": "Copper wire, of which the max cross-section > 6mm",
  "general_rate": "5%",
  "special_rate": "Free",
  "column2_rate": "35%",
  "unit": "kg"
}
```

### Task

Write `mcp_server.py` using the `mcp` Python SDK:
1. Implement the four tools above against `data/hts.db`
2. Use `stdio` transport (standard for local MCP servers)
3. Include the Claude Desktop config snippet below in a README section

### Claude Desktop config

The MCP server runs as a Docker container with `-i` (interactive stdin) and the data volume mounted. No port exposed — pure stdio.

```json
{
  "mcpServers": {
    "hts": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-v", "/absolute/path/to/hts-local/data:/app/data",
        "hts-local",
        "mcp_server.py"
      ]
    }
  }
}
```

Claude Desktop spawns this command, speaks MCP over stdin/stdout, and the container exits cleanly when the session ends. No daemon, no port, no host Python needed.

### Git checkpoint

```bash
git add mcp_server.py
git commit -m "feat: step4 mcp — sqlite-backed MCP server"
```

---

## Step 5 — Revision refresh (~ 10 min)

**Goal:** Keep the database current. The HTS is revised 3–4 times per year.

### API endpoint to check

```
GET https://hts.usitc.gov/reststop/releases
```

Returns a list of available releases with revision identifiers.

### Task

Write `scripts/refresh.py` that:
1. Fetches the releases list
2. Compares the latest revision tag against `data/last_revision.txt`
3. If changed: re-runs the ingest, updates `last_revision.txt`, prints `Updated to revision X`
4. If unchanged: prints `Already up to date (revision X)`

### Run it

```bash
hts-run scripts/refresh.py
```

Cron-friendly — wire it to a quarterly job or run manually before important work.

### Git checkpoint

```bash
git add scripts/refresh.py
git commit -m "feat: step5 refresh — revision check + re-ingest"
```

---

## Step 6 — Smoke tests (~ 10 min)

A few quick sanity checks to confirm everything works end-to-end.

```bash
# Confirm ingest loaded data
hts-run hts.py code 0101.21.00   # Live horses

# Confirm search works
hts-run hts.py search "titanium"

# Confirm SQLite directly
hts-run python -c "
import sqlite3
db = sqlite3.connect('data/hts.db')
rows = db.execute('SELECT hts_code, description, general_rate FROM hts_entries WHERE hts_code LIKE \"7408%\" LIMIT 5').fetchall()
for r in rows: print(r)
"
```

### Git checkpoint

```bash
git commit -am "chore: smoke tests passing"
```

---

## Useful prompts for Claude Code

Once you're in a Claude Code session with this file open, use these to generate each step:

- `Write Dockerfile and requirements.txt following step 0 in this plan`
- `Write scripts/ingest.py following the schema and endpoint in this plan`
- `Write hts.py CLI following step 3 in this plan using typer`
- `Write mcp_server.py following step 4 in this plan using the mcp Python SDK with stdio transport`
- `Write scripts/refresh.py following step 5 in this plan`

---

## Notes

- **Docker is the only host dependency** — no Python, pip, or virtualenv on the machine
- The `data/` volume mount means `hts.db` lives on your host fs and survives container rebuilds
- No API key required for `hts.usitc.gov/reststop/` — public government endpoint
- No documented rate limits; add a polite delay if doing bulk re-ingests
- The MCP server uses `stdio` transport — Claude Desktop spawns it as a subprocess, no port or daemon needed
- Rebuild the image (`docker build -t hts-local .`) only when `requirements.txt` or `Dockerfile` changes
