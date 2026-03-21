# Implementation Plan: Publish HTS Data with Datasette on Fly.io

## Goal

Ship a public, browsable Harmonized Tariff Schedule lookup at `<app-name>.fly.dev` using [Datasette](https://datasette.io/) backed by the existing `data/hts.db` SQLite database. No one has published US HTS data on Datasette before — this would be a first.

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
│  (anycast)   │       │  ├─ datasette (Python)   │
└──────────────┘       │  ├─ hts.db (read-only)   │
                       │  ├─ metadata.json         │
                       │  └─ plugins/templates     │
                       └─────────────────────────┘
```

- Single-container deployment on Fly.io free tier (256 MB RAM, shared CPU)
- Read-only SQLite — no write path, no replication needed
- DB bundled into the Docker image at build time (not a Fly Volume)
- Updates: rebuild and redeploy when HTS data changes

## Implementation Steps

### Phase 1: Prepare the database for Datasette (local)

1. **Enable FTS5 on `hts_entries`** — Datasette auto-detects FTS tables and shows a search box.
   ```bash
   pip install sqlite-utils
   sqlite-utils enable-fts data/hts.db hts_entries description --fts5
   ```
   This creates a virtual table `hts_entries_fts` that Datasette will pick up automatically.

2. **Write `metadata.json`** — controls titles, descriptions, and column display.
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
             "description_html": "Tariff line items with duty rates, units, and classification hierarchy.",
             "sortable_columns": ["hts_code", "chapter_id", "indent"],
             "facets": ["chapter_id", "unit"]
           },
           "chapters": {
             "label_column": "description",
             "description_html": "HTS chapters 01-99 with entry counts."
           }
         }
       }
     }
   }
   ```

3. **Optional: Add a custom CSS template** for branding (can be deferred post-launch).

### Phase 2: Local verification

4. **Install Datasette locally and test:**
   ```bash
   pip install datasette datasette-search-all
   datasette data/hts.db --metadata metadata.json --open
   ```
   Verify:
   - Homepage shows both tables with descriptions
   - Full-text search works on `hts_entries` (search box visible)
   - Facets for `chapter_id` and `unit` render correctly
   - JSON API works: `/-/versions.json`, `/hts/hts_entries.json?_search=copper`
   - CSV export works from the table view

### Phase 3: Deploy to Fly.io

5. **Install the Fly.io publish plugin:**
   ```bash
   pip install datasette-publish-fly
   flyctl auth login
   ```

6. **Publish:**
   ```bash
   datasette publish fly data/hts.db \
     --app="usitc-hts" \
     --metadata metadata.json \
     --install=datasette-search-all \
     --install=datasette-cluster-map \
     --setting default_page_size 50
   ```
   This will:
   - Build a Docker image with Datasette + the DB + plugins
   - Create a Fly app named `usitc-hts`
   - Deploy to `usitc-hts.fly.dev`

7. **Verify the live deployment:**
   - Browse `https://usitc-hts.fly.dev/`
   - Test search: `https://usitc-hts.fly.dev/hts/hts_entries?_search=copper+wire`
   - Test JSON API: `https://usitc-hts.fly.dev/hts/hts_entries.json?_search=copper+wire`
   - Test code lookup: `https://usitc-hts.fly.dev/hts/hts_entries?hts_code=7408.11.30`

### Phase 4: Polish (post-launch, optional)

8. **Custom domain** — point a subdomain via Fly.io certs + CNAME
9. **CORS headers** — enable via `datasette-cors` plugin if the JSON API will be consumed by frontends
10. **Caching** — add `datasette-block-robots` (if desired) and Fly.io edge caching headers
11. **Automated updates** — GitHub Action that runs `scripts/refresh.py`, rebuilds FTS, and redeploys via `datasette publish fly`

## Recommended Datasette Plugins

| Plugin | Purpose |
|--------|---------|
| `datasette-search-all` | Global search box across all tables |
| `datasette-cluster-map` | (optional) Map view if geo data is added later |
| `datasette-cors` | CORS headers for API consumers |
| `datasette-block-robots` | Block search engine indexing if desired |
| `datasette-json-html` | Render JSON columns (footnotes) as formatted HTML |

## Cost

- **Fly.io free tier:** 3 shared-CPU VMs, 256 MB RAM each — more than sufficient
- **No egress charges** for moderate traffic
- **Total: $0/month** for a read-only, low-traffic SQLite app

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| DB too large for container image | Current DB is ~20-50 MB — well within limits. Fly images support up to 1 GB. |
| FTS index bloats DB size | FTS5 adds ~10-20% overhead. Still well under limits. |
| Fly free tier gets sunset | Datasette also supports Cloudflare Workers (`datasette-publish-cloudflare`), Vercel, and Google Cloud Run. Migration is a one-liner. |
| HTS data goes stale | Phase 4 automation: GitHub Action runs refresh + redeploy on a schedule. |

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `metadata.json` | Create | Datasette configuration (titles, facets, descriptions) |
| `scripts/build_fts.py` | Create | Script to enable FTS5 on the database before deploy |
| `Makefile` or `justfile` | Create (optional) | Convenience targets: `make serve`, `make deploy` |
| `requirements.txt` | Modify | Add `datasette`, `datasette-search-all`, `datasette-publish-fly`, `sqlite-utils` |
| `.github/workflows/deploy.yml` | Create (Phase 4) | Automated refresh + redeploy |

## References

- [Datasette documentation](https://docs.datasette.io/en/stable/)
- [Datasette publish fly plugin](https://datasette.io/plugins/datasette-publish-fly) (current: v1.3.1)
- [Fly.io blog: Making Datasets Fly with Datasette](https://fly.io/blog/making-datasets-fly-with-datasette-and-fly/)
- [Datasette full-text search docs](https://docs.datasette.io/en/stable/full_text_search.html)
- [sqlite-utils enable-fts](https://sqlite-utils.datasette.io/en/stable/cli.html#enabling-full-text-search)
