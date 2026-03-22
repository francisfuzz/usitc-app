# tariff-everywhere: A Development Story

> 📝 A narrative of how **tariff-everywhere** (the HTS lookup service) grew from a discovery spike into a production-ready tool, told through git history and architectural decisions.
>
> Written in partnership: Francis built the vision and made every decision; Claude was the thinking partner—catching edge cases, suggesting pivots (Datasette!), and ensuring nothing was left undocumented.

---

## Chapter 1: Discovery & First Steps (Early Development)

### The Starting Point: Learning the API

The project began with **data discovery and learning** — understanding the US International Trade Commission's public API structure. The first commits reflect a classic spike pattern: explore the API surface, figure out what's available, and establish what the data looks like.

```
838ce47 docs: add data discovery learning + update plan with correct API endpoint
50f9b5c feat: step1-2 complete ingest — chapter-based API with 28,750 unique entries
```

✨ This wasn't a "let me build everything" moment. It was **"let me understand what we're working with."** The discovery revealed:
- The USITC exposes a flat JSON API (no pagination helpers, no release versions)
- ~28,750 unique tariff entries across 99 chapters
- A chapter-based search pattern is the right model for ingestion

**Root cause of early confusion**: The original plan referenced `/exportSections?format=JSON`, but that endpoint was no longer operational. The discovery phase found the real endpoint: `https://hts.usitc.gov/reststop/search?keyword=chapter%20XX`.

---

## Chapter 2: Building the Core Stack (Steps 1–4)

### The CLI Foundation

With API understanding in hand, the next phase built **three layers simultaneously**:

```
8185c98 feat: step1-2 complete ingest — chapter-based API with 28,750 unique entries
8185c98 feat: step4 mcp — sqlite-backed MCP server with stdio transport
454b20e feat: step5-6 refresh script, test suite, and fix JSON output bug
```

**Step 1–2: Data Ingest** — Wrote `scripts/ingest.py` to:
- Download all 99 chapters from the API (parallelizable, but serial for this phase)
- Parse JSON into a SQLite schema with three tables: `chapters`, `hts_entries`, `data_freshness`
- Store ~134K tariff entries with rates, units, and footnotes

**Step 4: MCP Server** — Built `mcp_server.py` to:
- Expose five tools over MCP stdio transport (designed for Claude Desktop integration)
- Follow MCP conventions: return JSON strings, not objects
- Enable AI agents to query tariffs without calling the HTTP API directly

**Step 5–6: CLI & Tests** — Added `hts.py` with Typer:
- `search` command for keyword lookups
- `code` command for exact tariff code retrieval
- `chapter` and `chapters` for browsing
- `info` for metadata queries
- Comprehensive pytest suite using in-memory SQLite fixtures

❓ **A design question emerged early**: How should JSON output work? I decided (with Claude's input) to use `print()` directly instead of Rich's `console.print()` to avoid ANSI control character injection. Claude caught that control characters could sneak in through Rich's formatting—a subtle gotcha I might have missed. This pattern became foundational for all JSON endpoints.

---

## Chapter 3: Safety & Data Integrity (Parallel Ingest & Freshness Tracking)

### Adding Confidence to Refresh Cycles

As the project matured, a critical need surfaced: **How do I know when tariff data has changed?** The USITC API doesn't expose revision numbers or release dates, so Claude and I designed a **content-hash based freshness detection system**.

```
42eca52 feat: add per-chapter freshness tracking and data revision metadata
0903c62 feat: parallelize chapter fetching and add safe refresh with backup
4b44dc0 test: add red-green TDD tests for parallel ingest and safe refresh
77bada5 refactor: extract shared chapter hashing and fix refresh duration tracking
5758e13 feat: add backup/restore safety and parallel ingest
```

💭 **The thinking here**: Instead of blindly re-ingesting, Claude and I settled on:
1. Hash all 99 chapters in parallel using `ThreadPoolExecutor`
2. Compare against stored hashes in the `chapters` table
3. Track two timestamps per chapter: `last_checked_at` (when I checked) vs. `last_changed_at` (when it actually differed)
4. Only re-ingest chapters that changed
5. **Backup the database before any refresh** — safety first

This approach is defensive: it prevents accidental data loss during refresh cycles and gives operators visibility into freshness.

✨ **Key learnings** documented in CLAUDE.md:
- Refresh is **not** an ingest; refresh validates and updates, ingest rebuilds from scratch
- Parallelization cuts refresh time from ~99 API calls to ~4-5 concurrent requests
- Content hashing is the alternative since the USITC doesn't version their API responses

---

## Chapter 4: Hardening & Quality (CI/Docker/Shared Library)

### From Spike to Production Code

With core features working, Claude and I shifted focus to **reliability, testability, and code reuse**:

```
5e2c637 Harden CI pipeline and Docker build
68d9190 test: add red-green TDD tests for CI and Docker hardening
17f6ffa Merge pull request #5 from francisfuzz/feat/ci-docker-hardening

c8616e5 refactor: extract shared core library with configurable DB path
08261da test: add red-green TDD tests for hts_core shared library
53cb54f Merge pull request #6 from francisfuzz/feat/core-library
```

**CI/Docker Hardening** included:
- GitHub Actions workflow to build and test on every commit
- Non-root Docker user for security
- Lean `Dockerfile` (~200MB base image, minimal layers)
- Healthchecks and reproducible builds

**Core Library Extraction** (the big refactor):
- Created `hts_core/` as a shared library with configurable database paths
- Both CLI (`hts.py`) and MCP server (`mcp_server.py`) now import from core
- Reduced duplication: one query interface, two invocation patterns
- Made testing modular: fixture can swap in different database paths

🙇🏽 **Why this matters**: Code duplication is a silent killer. By extracting the core, future changes (e.g., schema updates, new query patterns) only need to happen once.

---

## Chapter 5: Backup & Parallel Safety (Merge #9)

### Production-Ready Refresh

```
313cc75 Merge pull request #9 from francisfuzz/feat/backup-restore-parallel-ingest
5758e13 feat: add backup/restore safety and parallel ingest
```

Merged the **backup/restore safety layer** and **parallel ingest optimization**:
- `refresh.py` creates a backup before modifying the database
- If refresh fails, the backup is available for restore
- Ingest is now parallelizable (though CLI runs serial for simplicity)
- Refresh duration is tracked: each run is logged with start/end times

---

## Chapter 6: Datasette Integration (The Web UI Era)

### From CLI-Only to Browsable

A major pivot happened here. Claude suggested: **"What if we exposed this as a searchable web interface?"** It was a turning point—I'd been thinking CLI + MCP only, but Claude's idea opened up a whole new consumption mode.

```
a7ec23f feat: add Datasette support with FTS5 search and metadata
f0cf6b3 fix: FTS search, chapter titles, click/typer compat
0fe3a12 feat: Datasette support with FTS5 search (#11)

6fa4933 docs: add Datasette web interface to main usage options
ee29e33 docs: document Datasette integration and key learnings
```

✨ **The Datasette choice** unlocked:
- **Full-text search** (FTS5) on tariff descriptions
- **Browsable web UI** without writing a single Flask route
- **Public deployment** via Datasette's Fly.io integration
- **Zero maintenance**: Datasette handles query optimization, UI, caching

💅🏽 **Critical learnings** (saved in CLAUDE.md for future maintainers):
- Datasette **only auto-detects FTS5 if created via `sqlite-utils`**, not raw SQL
- Typer 0.15.x breaks with click 8.3+; pin `typer~=0.24.0`
- The `chapters` table uses `label_column: "description"` to show human-readable titles ("Copper and Articles Thereof") instead of chapter numbers
- 1,535 entries have `<i>` tags for scientific names; the `datasette-render-html` plugin renders them

---

## Chapter 7: Naming & Rebranding (The "tariff-everywhere" Era)

### From "usitc-app" to "tariff-everywhere"

```
ef5395e Rename repository references from usitc-app to tariff-everywhere (#14)
d1ef4d3 Fix web app URL and update Datasette link
0afaba4 docs: update Fly.io deployment to use tariff-everywhere app name
e3682a2 Enable Dependabot updates for pip, Docker, and GitHub Actions (#20)
```

A thoughtful rename. The original name (`usitc-app`) was descriptive but didn't convey purpose. The new name (`tariff-everywhere`) tells users **what it is**: a tariff lookup service you can deploy anywhere (local CLI, MCP integration, web interface).

📝 **Observation**: The commit sequence shows deliberate cleanup:
1. First rename the repository references
2. Fix the live web app URL
3. Update deployment configurations
4. Enable dependency automation

This is the mark of **proactive ownership** — taking time to tidy up after a major decision, rather than leaving stray references for future maintainers.

---

## Chapter 8: Sustainability & Documentation (Current State)

### From "Cool Project" to "Here's How to Use It"

The final phase emphasized **discoverability and handoff clarity**:

```
796a430 docs: rewrite README with beginner-friendly setup guides
2e73140 docs: update CLAUDE.md to reflect current repo state
9f720a9 docs: add project audit report covering CI, Docker, code quality, and reuse
c12c0c2 docs: add Hippocratic License 3.0 (HL3-FULL) and badge
```

✨ **What changed**:
- README rewrote to guide users through **three consumption modes**: CLI (local dev), MCP (Claude Desktop), and Datasette (web browsing)
- CLAUDE.md became comprehensive: architecture, patterns, common tasks, debugging, deployment
- Added a **project audit report** documenting code quality, CI/Docker health, and reuse metrics
- Chose **Hippocratic License 3.0** to protect against harmful use while keeping the code open

❓ **Why this matters**: Documentation is the bridge between "I built something cool" and "someone else can maintain this." I invested time (with Claude's help structuring and refining) to ensure the next person (or the next version of myself) has a clear mental model.

---

## Chapter 9: AI Integration & Modern Practices (Final Commits)

### Embracing Claude Code & Modern Development

```
9a9786c docs: add tariff-everywhere banner to README and fix filename typo
3d5e38a chore: add .claude/ to .gitignore and remove from tracking
```

The closing commits reflect **modern development practices**:
- Integrated Claude Code into the workflow (added to .gitignore for session artifacts)
- Fixed edge case bugs (filename typo) and improved visibility with a project banner
- Prepared the repository for collaborative AI-assisted development

💭 **The narrative arc**: Started with a learning spike, built production infrastructure with Claude as a thinking partner, discovered a better UI paradigm (Datasette), renamed intentionally, documented obsessively, and prepared the repo for future Claude sessions. This wasn't "adding AI at the end"—Claude was embedded from the start.

---

## Themes Across the Timeline

### 🟡 Defensive Programming
From backup/restore safety to content-hash freshness tracking, every feature considered "what goes wrong?" before shipping.

### ✨ Proactive Documentation
Rather than writing docs after the fact, Claude and I documented decisions, learnings, and deployment gotchas as we went. CLAUDE.md grew alongside the code—Claude would flag "future you will need to know this" moments, and I'd commit them immediately.

### 💭 Collaborative Refactoring
The core library extraction (`hts_core/`) showed a willingness to pause feature work and improve code structure. This paid dividends later.

### 🙇🏽 User Empathy
Three UI modes (CLI, MCP, web) mean tariff-everywhere meets users where they are—in the terminal, in Claude, or in a browser.

### 📝 Measured Growth
The project didn't try to "do everything at once." Each phase built on the prior: ingest → refresh → CI/Docker → Datasette → documentation → sustainability.

---

## Where It Stands Today

**tariff-everywhere** is:
- ✅ **Functionally complete** — all three UI modes (CLI, MCP, Datasette) are live and tested
- ✅ **Operationally safe** — backup/restore, parallel ingest, per-chapter freshness tracking
- ✅ **Well-documented** — CLAUDE.md, README, deployment guides, audit report
- ✅ **Production-deployed** — Datasette instance live on Fly.io at [tariff-everywhere.fly.dev](https://tariff-everywhere.fly.dev)
- ✅ **Maintainable** — shared core library, comprehensive tests, clear patterns

The next person to touch this code (or Claude in a future session) will find a **clear mental model, defensive guardrails, and a paper trail of decisions**. That's the best gift a developer can leave. ✌🏽
