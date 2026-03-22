[![Hippocratic License HL3-FULL](https://img.shields.io/static/v1?label=Hippocratic%20License&message=HL3-FULL&labelColor=5e2751&color=bc8c3d)](https://firstdonoharm.dev/version/3/0/full.html)

# tariff-everywhere

A [Harmonized Tariff Schedule](https://hts.usitc.gov/) (HTS) lookup tool. Search tariff codes, duty rates, and product classifications from the US International Trade Commission.

Four ways to use it:

| Interface | Best for | Setup time |
|-----------|----------|-----------|
| **Web** (Datasette) | Browse, search, export without any setup | None — it's live now |
| **CLI** | Quick terminal lookups (`search`, `code`, `chapter`, `chapters`) | Docker or Python |
| **MCP Server** | Giving AI agents (like Claude) access to tariff data | Docker setup |
| **Python directly** | Development without Docker | Python 3.12+ |

**🌐 Jump straight to the web app:** https://usitc-hts.fly.dev/

---

## Prerequisites

### Docker (recommended)

Everything runs in a container — no Python installation needed on your machine.

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) for your OS
2. Verify it's running:
   ```bash
   docker --version
   ```

### Without Docker

If you prefer not to use Docker, you'll need:

- [Python 3.12+](https://www.python.org/downloads/)
- pip (comes with Python)

---

## Quick Start (Docker)

### 1. Clone the repo

```bash
git clone https://github.com/francisfuzz/tariff-everywhere.git
cd tariff-everywhere
```

### 2. Build the Docker image

```bash
docker build -t hts-local .
```

This installs all Python dependencies inside the container. You only need to do this once (or again after pulling updates).

### 3. Download the tariff data

The first run fetches all 99 chapters from the USITC public API and stores them in a local SQLite database. This takes about 15-20 seconds and requires an internet connection.

```bash
docker run --rm -v "$(pwd)/data:/app/data" hts-local scripts/ingest.py
```

You should see output like:

```
Creating database schema...
Fetching and ingesting HTS data from all 99 chapters...
  Completed 10/99 chapters (3214 entries loaded so far)...
  ...
Loaded 28750 entries across 99 chapters
```

The data is saved to `data/hts.db` on your machine. You won't need to run this again unless you want to refresh the data.

### 4. Try it out

```bash
# Search for products by keyword
docker run --rm -v "$(pwd)/data:/app/data" hts-local hts.py search "copper wire"

# Look up a specific tariff code
docker run --rm -v "$(pwd)/data:/app/data" hts-local hts.py code 7408.11.30

# List all entries in a chapter
docker run --rm -v "$(pwd)/data:/app/data" hts-local hts.py chapter 74

# List all 99 chapters with entry counts
docker run --rm -v "$(pwd)/data:/app/data" hts-local hts.py chapters

# See all available commands
docker run --rm -v "$(pwd)/data:/app/data" hts-local hts.py --help
```

Every command supports a `--json` flag for machine-readable output:

```bash
docker run --rm -v "$(pwd)/data:/app/data" hts-local hts.py search "titanium" --json
```

---

## Quick Start (without Docker)

### 1. Clone and set up a virtual environment

```bash
git clone https://github.com/francisfuzz/tariff-everywhere.git
cd tariff-everywhere

python3 -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Download the tariff data

```bash
python scripts/ingest.py
```

### 3. Use the CLI

```bash
python hts.py search "copper wire"
python hts.py code 7408.11.30
python hts.py chapter 74
python hts.py chapters
```

---

## Connecting to Claude Desktop (MCP Server)

The MCP (Model Context Protocol) server lets Claude Desktop use the HTS data directly. Once configured, you can ask Claude questions like _"What's the tariff rate for copper wire?"_ and it will look up the answer from your local database.

### Prerequisites

- Complete the [Quick Start](#quick-start-docker) steps above (build the image and download the data)
- Install the [Claude Desktop app](https://claude.ai/download)

### Step 1 — Find your absolute data path

The Claude Desktop config requires an **absolute path** to your `data/` directory. Run this from the repo root to get it:

```bash
echo "$(pwd)/data"
```

Copy the output — you'll need it in the next step. It will look something like:

```
/Users/yourname/projects/tariff-everywhere/data
```

### Step 2 — Edit the Claude Desktop config

Open the Claude Desktop config file:

- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux:** `~/.config/Claude/claude_desktop_config.json`

If the file doesn't exist, create it. Add the `hts` server entry, replacing `/absolute/path/to/tariff-everywhere/data` with the path you copied above:

```json
{
  "mcpServers": {
    "hts": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-v", "/absolute/path/to/tariff-everywhere/data:/app/data",
        "hts-local",
        "mcp_server.py"
      ]
    }
  }
}
```

> **Already have other MCP servers configured?** Add the `"hts": { ... }` block inside your existing `"mcpServers"` object — don't replace the whole file.

### Step 3 — Restart Claude Desktop

Quit and reopen Claude Desktop. The HTS tools should now appear in the tools menu (the hammer icon in the chat input area).

You should see five tools available:

| Tool | What it does |
|------|-------------|
| `search_hts` | Search tariff entries by keyword |
| `get_code` | Look up a specific HTS code |
| `list_chapter` | List all entries in a chapter |
| `get_chapters` | Get all chapters with entry counts and descriptions |
| `get_data_freshness` | Check when the database was last updated |

### Step 4 — Try it

Start a new conversation in Claude Desktop and ask something like:

- _"What's the tariff classification for live horses?"_
- _"Look up HTS code 0101.21.00"_
- _"Show me all entries in chapter 74"_
- _"What are the duty rates for copper foil?"_

Claude will call the appropriate HTS tool and return the tariff data from your local database.

### Troubleshooting

**Tools don't appear in Claude Desktop:**
- Make sure Docker Desktop is running
- Verify the absolute path to `data/` is correct and `data/hts.db` exists
- Check for JSON syntax errors in the config file (trailing commas, etc.)
- Restart Claude Desktop after any config change

**"hts.db not found" error in Claude's response:**
- Run the ingest step: `docker run --rm -v "$(pwd)/data:/app/data" hts-local scripts/ingest.py`

**Docker container errors:**
- Rebuild the image: `docker build -t hts-local .`
- Check Docker is running: `docker ps`

---

## Browsable Web Interface (Datasette)

The HTS database is published as a live, searchable web app at **https://usitc-hts.fly.dev/** — no setup required, just open it in your browser.

### What you can do on the web interface

- **Search by keyword** — Full-text search across product descriptions (e.g., "coffee", "copper", "titanium")
- **Browse by chapter** — Click chapters to see all tariff entries (e.g., Chapter 74 = "Copper and Articles Thereof")
- **Exact code lookup** — Filter by HTS code (e.g., `7408.11.30`)
- **Export data** — Download search results as CSV or JSON
- **Global search** — Search across all 99 chapters at once
- **View rates & specifications** — See duty rates, units, and classifications for each product

### Running your own Datasette locally

If you want to host the interface on your own machine:

```bash
# 1. Build and ingest data (as usual)
docker build -t hts-local .
docker run --rm -v "$(pwd)/data:/app/data" hts-local scripts/ingest.py

# 2. Update chapter titles (real names instead of "Chapter 01")
python3 scripts/chapter_titles.py data/hts.db

# 3. Build the FTS5 search index (must use sqlite-utils for Datasette to detect it)
python3 -m sqlite_utils enable-fts data/hts.db hts_entries description --fts5 --replace

# 4. Serve locally on http://localhost:8321
docker run --rm -p 8321:8321 -v "$(pwd)/data:/app/data" -v "$(pwd)/metadata.json:/app/metadata.json" hts-local \
  -m datasette data/hts.db --metadata metadata.json --port 8321 --host 0.0.0.0 --setting default_page_size 50
```

Then open **http://localhost:8321/** in your browser.

### Deploying to Fly.io (free tier)

To deploy your own instance on Fly.io's free tier:

```bash
# 1. Install flyctl: https://fly.io/docs/hands-on/install-flyctl/
# 2. Log in: flyctl auth login
# 3. Deploy:

datasette publish fly data/hts.db \
  --app="my-hts-instance" \
  --metadata metadata.json \
  --install=datasette-search-all \
  --install=datasette-render-html \
  --setting default_page_size 50
```

Your instance will be live at `https://my-hts-instance.fly.dev/`. The entire deployment is free using Fly.io's always-free tier (2 shared CPUs, 256 MB RAM).

---

## Keeping Data Up to Date

The tariff schedule is updated periodically by the USITC. To check for updates and re-download if the data has changed:

```bash
# Docker
docker run --rm -v "$(pwd)/data:/app/data" hts-local scripts/refresh.py

# Without Docker
python scripts/refresh.py
```

If the data hasn't changed, you'll see `Already up to date.` — otherwise it will re-ingest all 99 chapters.

---

## Running Tests

```bash
# Docker
docker run --rm hts-local -m pytest tests/ -v

# Without Docker (with venv activated)
python -m pytest tests/ -v
```

The test suite uses an in-memory SQLite database with fixture data — no internet connection or real database needed.

---

## Project Structure

```
tariff-everywhere/
├── hts.py                  # CLI: search, code, chapter, chapters commands
├── mcp_server.py           # MCP server: 4 tools, stdio transport
├── metadata.json           # Datasette config (titles, facets, descriptions)
├── scripts/
│   ├── ingest.py           # Download + load all 99 chapters into SQLite
│   ├── refresh.py          # Check for data updates, re-ingest if changed
│   ├── build_fts.py        # Build FTS5 search index (uses sqlite-utils)
│   ├── chapter_titles.py   # Enrich chapter descriptions with real HTS titles
│   └── hashing.py          # Compute content hashes for change detection
├── tests/
│   ├── conftest.py         # Shared test fixtures
│   ├── test_cli.py         # CLI tests
│   ├── test_mcp.py         # MCP server tests
│   ├── test_build_fts.py   # FTS index tests
│   ├── test_chapter_titles.py  # Chapter title enrichment tests
│   └── test_metadata.py    # Datasette metadata validation
├── data/                   # SQLite database (created by ingest, gitignored)
├── docs/                   # Design docs, Datasette plan
├── Dockerfile
├── requirements.txt
├── CLAUDE.md               # Development guidance for Claude Code
└── README.md               # This file
```

---

## License

This project is licensed under the [Hippocratic License 3.0 (HL3-FULL)](https://firstdonoharm.dev/version/3/0/full.html). See [LICENSE](LICENSE) for the full text.

This project uses publicly available data from the [US International Trade Commission](https://hts.usitc.gov/).
