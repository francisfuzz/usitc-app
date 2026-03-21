# Project Audit Report

**Date:** 2026-03-21
**Scope:** CI workflows, Docker build/run/test, Python code quality, flexibility/reuse potential

---

## Executive Summary

usitc-app is a well-structured HTS lookup service with clean separation between data ingestion, CLI, and MCP interfaces. The core functionality works. This audit identifies improvements across build pipeline, code organization, and extensibility that will make the project production-ready and reusable beyond its current single-use case.

---

## 1. CI Workflows

### Current State
Single workflow (`ci.yml`) builds Docker image, runs pytest, and verifies CLI help. Simple and functional.

### Findings

| Issue | Impact | Effort |
|-------|--------|--------|
| No linting or formatting enforcement | Inconsistent code style across contributors | Low |
| No test coverage reporting | Can't detect untested code drift | Low |
| No dependency vulnerability scanning | Silent exposure to CVEs | Low |
| No artifact/release management | No Docker image push, no versioning | Medium |
| No scheduled data refresh workflow | Tariff data goes stale silently | Medium |

### Recommendations
- Add `flake8` and/or `ruff` linting step
- Add `pytest-cov` with coverage threshold (e.g., 80%)
- Add `pip audit` for dependency scanning
- Consider scheduled workflow for `scripts/refresh.py`

---

## 2. Docker Build/Run/Test

### Current State
Simple `Dockerfile` using `python:3.12-slim`. No `.dockerignore`. Runs as root.

### Findings

| Issue | Impact |
|-------|--------|
| **No `.dockerignore`** — `.git`, `__pycache__`, test caches all included in build context | Slower builds, larger images |
| **Runs as root** — no unprivileged user created | Security anti-pattern for deployed containers |
| **No health check** — MCP server has no liveness probe | Can't detect hung containers |
| **No pinned base image digest** — `python:3.12-slim` floats | Potential reproducibility issues |

### Recommendations
- Add `.dockerignore` excluding `.git`, `__pycache__`, `.pytest_cache`, `data/`, `docs/`, `*.pyc`
- Add `RUN useradd -m appuser` and `USER appuser`
- Consider multi-stage build if image size becomes a concern

---

## 3. Python Code Quality

### 3a. Duplicated Database Logic (HIGH IMPACT)

Both `hts.py` and `mcp_server.py` contain nearly identical:
- `get_db()` functions (connect to SQLite, check existence)
- Row-to-dict formatting logic
- try/finally connection management patterns

This duplication means:
- Bug fixes must be applied in two places
- New interfaces (REST API, Datasette plugin, library consumers) would need a third copy
- DB path is hardcoded as `Path("data/hts.db")` in both files with no override mechanism

**Recommendation:** Extract a shared `hts_core.py` module with:
- Configurable DB path via `HTS_DB_PATH` environment variable
- Single `get_db()` function
- Core query functions (`search_entries`, `get_entry`, `list_chapter_entries`, `get_all_chapters`)
- Shared formatting logic

This is the single highest-leverage change for enabling reuse.

### 3b. Hardcoded Configuration

| Hardcoded Value | Location | Fix |
|----------------|----------|-----|
| `Path("data/hts.db")` | `hts.py:20`, `mcp_server.py:12` | `HTS_DB_PATH` env var |
| `https://hts.usitc.gov/reststop/...` | `ingest.py:52`, `refresh.py:22` | `HTS_API_BASE` env var |
| Search limit default `10` | `hts.py:48`, `mcp_server.py:23` | Fine as default, but document |

### 3c. Fragile Column Mapping

`hts.py:29` uses positional `zip()` against hardcoded column names:
```python
columns = ["id", "hts_code", "indent", "description", ...]
return dict(zip(columns, row))
```
If the SELECT query changes column order, this silently misaligns. Use `cursor.description` or named tuples instead.

### 3d. Ingest Performance

`scripts/ingest.py` fetches 99 chapters sequentially. Each HTTP request takes ~0.5-1s. Total: ~60-90 seconds.

Using `concurrent.futures.ThreadPoolExecutor` with 10 workers would reduce this to ~6-9 seconds — a 10x improvement that directly impacts developer experience and CI pipeline time.

### 3e. Unsafe Refresh

`scripts/refresh.py:83-84` deletes the database before re-ingesting:
```python
if db_path.exists():
    db_path.unlink()
```
If ingest subsequently fails (network error, API change), the database is gone with no backup. Should rename to `.db.backup` first and restore on failure.

### 3f. Unpinned Dependencies

`requirements.txt` has no version pins:
```
requests
mcp
typer
rich
pytest
```
This means `pip install` can pull breaking changes at any time. Pin all versions. Consider splitting into runtime vs dev dependencies.

### 3g. Missing Error Handling in MCP Tools

MCP server tools don't catch database errors. If the DB is locked, corrupted, or missing mid-session, the exception bubbles up unhandled. Each tool should return a JSON error object on failure, not raise.

---

## 4. Data Layer

### Current State
Clean normalized schema with `chapters` and `hts_entries` tables, proper indexes on `hts_code` and `description`.

### Findings

| Issue | Impact |
|-------|--------|
| No `loaded_at` timestamp | Can't tell when data was last refreshed |
| Description search uses `LIKE '%term%'` | Full table scan, no relevance ranking |
| No FTS5 index | Missed opportunity for fast, ranked search |
| Revision detection probes chapter 01 only | Changes in other chapters can be missed |
| `footnotes` stored as raw JSON string | Can't query or filter by footnote content |

### Recommendations
- Add `loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP` to both tables
- Create FTS5 virtual table for description search (significant search quality improvement)
- Consider multi-chapter probe in refresh script

---

## 5. Testing

### Current State
Good coverage: 50 CLI tests, 30 MCP tests, comprehensive fixtures covering edge cases (empty rates, long descriptions, special characters). All tests use in-memory SQLite fixture.

### Gaps

| Gap | Impact |
|-----|--------|
| No coverage measurement in CI | Can't enforce coverage thresholds |
| `scripts/ingest.py` has zero tests | Can't safely refactor ingest logic |
| `scripts/refresh.py` has zero tests | Revision detection is untested |
| No integration tests (ingest → query) | End-to-end path unverified |
| Unused `import tempfile` in conftest.py | Minor cleanup |

---

## 6. Flexibility & Reuse Potential

### Current Interfaces
1. **CLI** (`hts.py`) — terminal lookups
2. **MCP Server** (`mcp_server.py`) — AI agent tools

### Where Else This Could Be Used

| Interface | Description | Effort | Unlocked By |
|-----------|-------------|--------|-------------|
| **Datasette** | Web UI + JSON API for browsing tariff data | Medium | Already planned (see `docs/DATASETTE_DEPLOY_PLAN.md`) |
| **REST API** | FastAPI/Flask wrapper for programmatic access | Low | Core library extraction |
| **Python library** | `pip install usitc-hts` for import in other projects | Low | Core extraction + `pyproject.toml` |
| **GitHub Actions action** | Reusable action for tariff lookups in workflows | Medium | Core extraction |
| **Slack/Discord bot** | Tariff lookups in team chat | Low | Core extraction |
| **Jupyter notebooks** | Data analysis of tariff schedules | Low | Core extraction |
| **Webhook/event service** | Notify subscribers when tariff data changes | Medium | Refresh script + notification layer |
| **Bulk export** | CSV/Parquet/JSON export for data pipelines | Low | Core extraction |

**The common blocker is core library extraction.** Once query logic is decoupled from CLI/MCP handlers, any new interface is a thin wrapper.

### Recommended Package Structure
```
hts_core.py          # Shared DB + query logic (new)
hts.py               # CLI (thin wrapper)
mcp_server.py        # MCP (thin wrapper)
scripts/ingest.py    # Data loading
scripts/refresh.py   # Data update
```

---

## 7. Three High-Impact Opportunities

Based on this audit, these are the three changes with the highest leverage toward the overall goal of a flexible, production-ready HTS service:

### Opportunity 1: Extract Shared Core Library
**Why:** Eliminates code duplication, makes DB path configurable, and unblocks every future interface (Datasette, REST API, library, bots). This is the prerequisite for flexibility.

### Opportunity 2: CI + Docker Hardening
**Why:** Adds .dockerignore, pins dependencies, adds linting and coverage. Prevents regressions as the project grows and accepts contributions.

### Opportunity 3: Parallel Ingest + Safe Refresh
**Why:** 10x faster data loading improves developer experience and CI time. Safe refresh prevents data loss on failed re-ingests. Both are critical for production deployment.

---

## Appendix: File Inventory

| File | Lines | Purpose |
|------|-------|---------|
| `hts.py` | 239 | CLI entrypoint |
| `mcp_server.py` | 141 | MCP server |
| `scripts/ingest.py` | 177 | Data ingestion |
| `scripts/refresh.py` | 97 | Data refresh |
| `tests/conftest.py` | 299 | Test fixtures |
| `tests/test_cli.py` | 220 | CLI tests |
| `tests/test_mcp.py` | 144 | MCP tests |
| `.github/workflows/ci.yml` | 28 | CI pipeline |
| `Dockerfile` | 15 | Container build |
| `requirements.txt` | 5 | Dependencies |
