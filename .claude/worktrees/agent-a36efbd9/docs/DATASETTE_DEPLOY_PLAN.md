# Implementation Plan: Publish HTS Data with Datasette on Fly.io

> **Dry-run status:** Every step below has been validated locally on 2026-03-21. Gotchas discovered during dry-run are called out in **Gotcha** blocks.

## Goal

Ship a public, browsable Harmonized Tariff Schedule lookup at `usitc-hts.fly.dev` using [Datasette](https://datasette.io/) backed by the existing `data/hts.db` SQLite database. No one has published US HTS data on Datasette before — this would be a first.

## Why Datasette

- **Zero UI code** — search, filtering, facets, JSON API, CSV export all built-in
- **Direct SQLite** — points at our existing `hts.db` with no ETL or transformation
- **One-command deploy** — `datasette publish fly` handles Dockerfile, fly.toml, and deployment
- **Plugin ecosystem** — FTS5, custom CSS, authentication, CORS all available as plugins
- **Proven at scale** — used by journalists, governments, and data teams for datasets of similar size

## Architecture

```
┌──────────────┐       ┌─────────────────────────┐
│  Fly.io edge │──────▶│  Datasette container     │
│  (anycast)   │       │  ├─ datasette 0.65.2     │
└──────────────┘       │  ├─ python:3.11-slim      │
                       │  ├─ hts.db (8.8 MB w/FTS) │
                       │  ├─ metadata.json          │
                       │  └─ plugins                │
                       └─────────────────────────┘
```

- Single-container deployment on Fly.io free tier (256 MB RAM, shared CPU)
- Read-only SQLite — DB is served with `--immutable` (automatic via `publish fly`)
- DB bundled into the Docker image at build time (not a Fly Volume)
- Updates: rebuild and redeploy when HTS data changes

## Database Facts (verified)

| Fact | Value |
|------|-------|
| DB size (raw) | **7.7 MB** |
| DB size (with FTS5) | **8.8 MB** (+14% / 1.1 MB overhead) |
| `hts_entries` rows | **28,750** (not 134K — the CLAUDE.md estimate was wrong) |
| `chapters` rows | **99** |
| Existing indexes | `idx_hts_code` (exact lookup), `idx_description` (substring) |
| HTML in data | **1,535 descriptions** contain `<i>` tags (scientific names); **8 distinct `unit` values** contain `<sup>`, `<il>`, and inline `style` attributes |
| Empty values | 8,972 entries have empty-string `unit` (not NULL); 0 NULL descriptions |
| `chapters.description` | Useless — just "Chapter 01", "Chapter 02", etc. No real chapter titles |
| `footnotes` column | JSON strings, e.g. `[{"columns": ["general"], "marker": "1", "value": "See 9903.88.15", "type": "endnote"}]` |

## Implementation Steps

### Phase 1: Prepare the database for Datasette (local)

**Step 1: Enable FTS5 on `hts_entries`**

Datasette auto-detects FTS virtual tables and shows a search box.

```bash
pip install sqlite-utils
sqlite-utils enable-fts data/hts.db hts_entries description --fts5
```

This creates `hts_entries_fts` (plus `_data`, `_idx`, `_docsize`, `_config` helper tables). Datasette will automatically display a search box on the `hts_entries` table view.

> **Gotcha: FTS5 query syntax.** Multi-word queries like `copper wire` work as implicit AND in Datasette (each word must appear, but not necessarily adjacent). Phrase search requires quotes: `"copper wire"`. This matches Datasette's documented behavior — no action needed, but users may be surprised that `copper wire` matches entries where both words appear separately.

> **Gotcha: FTS5 only indexes `description`.** The `hts_code` column is NOT in the FTS index. Users who type a code like `7408.11` into the search box will get zero results. They need to use the column filter (`?hts_code=7408.11`) or the exact-match filter in the UI. Consider adding `hts_code` to the FTS index: `sqlite-utils enable-fts data/hts.db hts_entries description hts_code --fts5` — but test this, as codes with dots may tokenize unexpectedly.

**Step 2: Write `metadata.json`**

```json
{
  "title": "US Harmonized Tariff Schedule",
  "description": "Browse and search the full US HTS tariff classification data from hts.usitc.gov. Updated from the USITC public API.",
  "license": "Public Domain",
  "license_url": "https://www.usitc.gov/",
  "source": "US International Trade Commission",
  "source_url": "https://hts.usitc.gov/",
  "databases": {
    "hts": {
      "tables": {
        "hts_entries": {
          "label_column": "hts_code",
          "description_html": "Tariff line items with duty rates, units, and classification hierarchy. Search uses full-text search on the description column. To look up a specific HTS code, use the column filter rather than the search box.",
          "sortable_columns": ["hts_code", "chapter_id", "indent"],
          "facets": ["unit"]
        },
        "chapters": {
          "label_column": "number",
          "description_html": "HTS chapters 01-99."
        }
      }
    }
  }
}
```

> **Gotcha: `chapter_id` is a bad facet.** It has 99 distinct values. Datasette truncates facets at 30 values by default, so 69 chapters are hidden. Removed from facets. The `unit` facet is viable but note that empty-string units (8,972 entries) will show as a blank facet value.

> **Gotcha: `chapters.label_column` should be `number`, not `description`.** The `description` column is just "Chapter 01" etc. — the `number` column ("01", "02") is more useful as a foreign-key label since it's what users recognize.

> **Gotcha: Database name in metadata must be `hts`.** Datasette strips the `.db` extension from the filename, so `data/hts.db` becomes database name `hts`. The metadata key must match exactly. Verified this works.

**Step 3: (Optional) Handle HTML in data**

1,535 descriptions contain `<i>` tags for scientific names (e.g., `<i>Thunnus thynnus</i>`). Datasette **escapes** these by default — they render as visible `<i>` text, not italics. The `unit` column has `<sup>2</sup>` and `<il>` tags that also render as raw text.

Options (pick one during implementation):
- **Accept it** — functional but ugly for scientific names. Simplest path.
- **Strip HTML at ingest time** — modify `scripts/ingest.py` to strip tags before insert. Loses italic formatting but looks clean.
- **Use `datasette-render-html`** — plugin that renders HTML in specified columns. Most correct, but renders ALL HTML including any injection risk. Since this is government data, risk is low.

### Phase 2: Local verification

**Step 4: Install and test Datasette locally**

```bash
pip install datasette datasette-search-all sqlite-utils
# Enable FTS if not already done
sqlite-utils enable-fts data/hts.db hts_entries description --fts5
# Serve locally
datasette data/hts.db --metadata metadata.json --port 8321 --setting default_page_size 50
```

Verification checklist (all confirmed working in dry-run):
- [x] Homepage shows title "US Harmonized Tariff Schedule" with source link
- [x] Both tables (`hts_entries`, `chapters`) listed with descriptions
- [x] Full-text search box visible on `hts_entries` table view
- [x] FTS search works: `/hts/hts_entries?_search=titanium` returns results
- [x] `unit` facet renders on the left sidebar
- [x] JSON API works: `/hts/hts_entries.json?_search=titanium`
- [x] CSV export works from the table view (download link)
- [x] Code lookup works: `/hts/hts_entries?hts_code=0106.12.01.00`
- [x] `datasette-search-all` global search works at `/-/search?q=titanium`
- [x] Versions endpoint: `/-/versions.json` shows datasette 0.65.2

> **Gotcha: Immutable mode syntax.** For local testing in read-only mode, the flag is `datasette --immutable data/hts.db`, NOT `datasette data/hts.db -i` (which errors: "Option '-i' requires an argument"). The `publish fly` command uses immutable mode automatically, so this only matters for local testing.

### Phase 3: Deploy to Fly.io

**Step 5: Prerequisites**

```bash
# Install flyctl (required — publish will fail with clear error if missing)
curl -L https://fly.io/install.sh | sh
# Or on macOS:
brew install flyctl

flyctl auth login
# Or: flyctl auth signup (if no account)

# Install the publish plugin
pip install datasette-publish-fly
```

> **Gotcha: `flyctl` must be installed and authenticated BEFORE running `datasette publish fly`.** The plugin checks for flyctl immediately and exits with "Publishing to Fly requires flyctl to be installed and configured" if missing. However, `--generate-dir` works WITHOUT flyctl — useful for previewing the generated Dockerfile and fly.toml.

**Step 6: Dry-run the generated files (recommended before first deploy)**

```bash
datasette publish fly data/hts.db \
  --app="usitc-hts" \
  --metadata metadata.json \
  --install=datasette-search-all \
  --setting default_page_size 50 \
  --generate-dir /tmp/datasette-preview
```

Review the generated files:
- `Dockerfile` — uses `python:3.11.0-slim-bullseye`, installs datasette + plugins, runs `datasette serve --host 0.0.0.0 -i hts.db --cors`
- `fly.toml` — app name, internal port 8080, HTTP/HTTPS on 80/443
- `metadata.json` — copy of your metadata
- `hts.db` — copy of the database

> **Gotcha: DATASETTE_SECRET in Dockerfile.** The generated Dockerfile hardcodes a `DATASETTE_SECRET` as an ENV variable in plaintext. For a read-only public dataset this is low-risk (the secret is used for signed cookies), but for better practice, pass it via Fly secrets after deploy: `flyctl secrets set DATASETTE_SECRET=$(python3 -c "import secrets; print(secrets.token_hex())")`.

> **Gotcha: fly.toml uses legacy `[[services]]` format.** The generated `fly.toml` uses the older services syntax, not the newer `[http_service]` format. This still works with current flyctl but may trigger deprecation warnings. If it causes issues, edit the generated fly.toml before deploying.

**Step 7: Publish**

```bash
datasette publish fly data/hts.db \
  --app="usitc-hts" \
  --metadata metadata.json \
  --install=datasette-search-all \
  --setting default_page_size 50
```

This will:
- Build a Docker image (~50 MB compressed) with Datasette + DB + plugins
- Create a Fly app named `usitc-hts` (or update if it exists)
- Deploy to `usitc-hts.fly.dev`

> **Note:** Do NOT include `--install=datasette-cluster-map` — it's a map visualization plugin irrelevant to tariff data (no geographic coordinates in this dataset).

**Step 8: Verify the live deployment**

```bash
# Quick smoke tests
curl -s -o /dev/null -w "%{http_code}" https://usitc-hts.fly.dev/
curl -s "https://usitc-hts.fly.dev/hts/hts_entries.json?_search=titanium&_size=1" | python3 -m json.tool
curl -s "https://usitc-hts.fly.dev/hts/hts_entries.json?hts_code=0106.12.01.00" | python3 -m json.tool
```

Verify:
- Browse `https://usitc-hts.fly.dev/` — homepage with title and tables
- Search: `https://usitc-hts.fly.dev/hts/hts_entries?_search=titanium`
- JSON API: `https://usitc-hts.fly.dev/hts/hts_entries.json?_search=titanium`
- CSV export: `https://usitc-hts.fly.dev/hts/hts_entries.csv?_search=titanium`
- Code lookup: `https://usitc-hts.fly.dev/hts/hts_entries?hts_code=0106.12.01.00`
- Global search: `https://usitc-hts.fly.dev/-/search?q=titanium`

### Phase 4: Polish (post-launch, optional)

8. **Custom domain** — `flyctl certs add yourdomain.com` + CNAME to `usitc-hts.fly.dev`
9. **CORS headers** — already enabled by default (`--cors` is in the generated Dockerfile). For fine-grained control, add `datasette-cors` plugin.
10. **Automated updates** — GitHub Action that runs `scripts/refresh.py`, rebuilds FTS, and redeploys via `datasette publish fly`
11. **HTML cleanup** — decide whether to strip `<i>`/`<sup>` tags at ingest time or use `datasette-render-html`

## Recommended Datasette Plugins

| Plugin | Purpose | Include at launch? |
|--------|---------|-------------------|
| `datasette-search-all` | Global search box across all tables | **Yes** |
| `datasette-cors` | Fine-grained CORS headers for API consumers | No (basic CORS already enabled) |
| `datasette-render-html` | Render HTML in description/unit columns (scientific names) | Maybe (see Step 3) |
| `datasette-json-html` | Render JSON columns (footnotes) as formatted HTML | No (defer) |
| `datasette-block-robots` | Block search engine indexing if desired | No (defer) |

Removed from original plan:
- ~~`datasette-cluster-map`~~ — no geographic data in this dataset

## Cost

- **Fly.io free tier:** 3 shared-CPU VMs, 256 MB RAM each — more than sufficient for an 8.8 MB read-only DB
- **No egress charges** for moderate traffic
- **Total: $0/month** for a read-only, low-traffic SQLite app

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| DB too large for container image | DB is only 8.8 MB with FTS. Fly images support up to 1 GB. Non-issue. |
| FTS index bloats DB size | FTS5 added only 1.1 MB (14%). Non-issue. |
| Fly free tier gets sunset | Datasette also supports Cloudflare Workers (`datasette-publish-cloudflare`), Vercel, and Google Cloud Run. Migration is a one-liner. |
| HTS data goes stale | Phase 4 automation: GitHub Action runs refresh + redeploy on a schedule. |
| HTML tags render as raw text | 1,535 descriptions have `<i>` tags, 8 unit values have `<sup>`/`<il>` tags. Functional but ugly. See Step 3 options. |
| `chapter_id` facet is useless | 99 values, truncated at 30 by Datasette. Removed from facets in metadata. |
| DATASETTE_SECRET exposed in Dockerfile | Low risk for public read-only data. Override via `flyctl secrets set` for better hygiene. |
| fly.toml uses legacy format | Still works. Only edit if flyctl raises deprecation errors. |

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `metadata.json` | Create | Datasette configuration (titles, facets, descriptions) |
| `scripts/build_fts.py` | Create | Script to enable FTS5 on the database before deploy |
| `requirements.txt` | Modify | Add `datasette`, `datasette-search-all`, `datasette-publish-fly`, `sqlite-utils` |
| `.github/workflows/deploy.yml` | Create (Phase 4) | Automated refresh + redeploy |

## Quick Reference: Exact Commands

```bash
# Full setup from scratch (after data/hts.db exists from ingest)
pip install datasette datasette-search-all datasette-publish-fly sqlite-utils

# Enable FTS5
sqlite-utils enable-fts data/hts.db hts_entries description --fts5

# Local test
datasette data/hts.db --metadata metadata.json --port 8321 --setting default_page_size 50

# Preview generated deploy files (no flyctl needed)
datasette publish fly data/hts.db --app="usitc-hts" --metadata metadata.json \
  --install=datasette-search-all --setting default_page_size 50 \
  --generate-dir /tmp/datasette-preview

# Deploy (requires flyctl auth login)
datasette publish fly data/hts.db --app="usitc-hts" --metadata metadata.json \
  --install=datasette-search-all --setting default_page_size 50

# Set secret properly after deploy
flyctl secrets set DATASETTE_SECRET=$(python3 -c "import secrets; print(secrets.token_hex())") --app usitc-hts
```

## References

- [Datasette documentation](https://docs.datasette.io/en/stable/)
- [Datasette publish fly plugin](https://datasette.io/plugins/datasette-publish-fly) (current: v1.3.1)
- [Fly.io blog: Making Datasets Fly with Datasette](https://fly.io/blog/making-datasets-fly-with-datasette-and-fly/)
- [Datasette full-text search docs](https://docs.datasette.io/en/stable/full_text_search.html)
- [sqlite-utils enable-fts](https://sqlite-utils.datasette.io/en/stable/cli.html#enabling-full-text-search)
