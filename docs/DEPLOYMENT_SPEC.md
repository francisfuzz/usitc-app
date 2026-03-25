# Continuous Deployment Specification

## Overview

Implement scheduled, change-aware continuous deployment to Fly.io. Every 6 hours (and on manual trigger), check for HTS data updates via `refresh.py`. If changes are detected, create a GitHub issue with detailed change metadata and notify @francisfuzz. Manual approval via `workflow_dispatch` triggers the actual Datasette redeploy.

## Problem Statement

Currently, the Datasette instance at https://tariff-everywhere.fly.dev/ must be manually redeployed after HTS data changes. There's no visibility into when data has changed, and the deployment process is entirely manual. This creates friction:
- Data updates are delayed waiting for manual redeploy
- No audit trail of what data changed when
- No notification when changes occur
- Risk of stale data in production

## Goals & Non-Goals

### Goals
1. Run `refresh.py` on a 6-hour schedule to detect HTS data changes
2. When changes are detected, create a GitHub issue with detailed metadata (chapters changed, content hashes, entry deltas)
3. Notify @francisfuzz of detected changes via GitHub issue mention
4. Support manual triggers via `workflow_dispatch` to run checks on-demand
5. Require explicit manual approval (via `workflow_dispatch`) before deploying
6. Maintain an auditable paper trail of all data changes and deployments
7. Authenticate to Fly.io securely using GitHub Secrets

### Non-Goals
- Automatic zero-touch deployment (manual approval required)
- Downtime-free deployments (simple redeploy is acceptable)
- Rollback automation (manual intervention if needed)
- Notifications for failed refresh runs (only successful runs with changes)
- Deployment on code changes (only on data changes)

## User Stories

### Story 1: Scheduled Data Monitoring
**As a** maintainer
**I want** the system to automatically check for HTS data changes every 6 hours
**So that** I'm not manually running `refresh.py` and can focus on other work

**Expected behavior:**
- Workflow triggers every 6 hours (cron: `0 */6 * * *`)
- Runs `scripts/refresh.py` inside Docker
- If no changes detected: workflow completes silently (no issue, no notification)
- If changes detected: proceeds to Story 2

---

### Story 2: Change Detection & Notification
**As a** maintainer
**I want** to be notified immediately when HTS data changes with detailed metadata
**So that** I can review what changed and approve deployment at a convenient time

**Expected behavior:**
- When `refresh.py` detects changes, a GitHub issue is created
- Issue title: `[HTS Data Update] Changes detected in X chapters`
- Issue body includes:
  - List of chapters with changes (chapter number → description)
  - Old vs. new content hash for each changed chapter
  - Total entries affected (if available)
  - Timestamp of detection
  - Link to the workflow run
- Issue mentions @francisfuzz so notification is sent
- Issue labels: `data-update`, `requires-review`
- Issue is opened in draft/backlog state (no auto-assignment)

---

### Story 3: Manual Approval & Deployment
**As a** maintainer
**I want** to trigger deployment only after reviewing change details
**So that** I have control and can defer deployments if needed

**Expected behavior:**
- A separate workflow is available with `workflow_dispatch` trigger
- Clicking the "Run workflow" button in Actions tab shows an optional input (e.g., "Approve deployment? yes/no")
- On approval, runs:
  1. `scripts/chapter_titles.py` to enrich chapter descriptions
  2. Rebuilds FTS5 index: `sqlite-utils enable-fts data/hts.db hts_entries description --fts5 --replace`
  3. Runs `datasette publish fly` to redeploy
- Workflow adds a comment to the most recent HTS data issue: "Deployment triggered by @francisfuzz"
- Workflow run is linked in the issue for audit trail

---

### Story 4: Manual Refresh Trigger
**As a** maintainer
**I want** to manually check for data changes outside the 6-hour schedule
**So that** I can respond to urgent updates or verify sync

**Expected behavior:**
- The scheduled refresh workflow accepts `workflow_dispatch` trigger
- Clicking "Run workflow" in Actions tab runs `refresh.py` immediately
- Same notification flow as scheduled runs (create issue if changes detected)

---

## Technical Requirements

### Workflows

#### Workflow 1: `refresh-hts-data.yml`
- **Trigger:** Cron (`0 */6 * * *`) + `workflow_dispatch`
- **Jobs:**
  - `detect-changes`:
    - Check out repo
    - Build Docker image (`docker build -t hts-local .`)
    - Mount data volume and run `scripts/refresh.py`
    - Parse output to determine if changes were detected
    - If changes detected: extract metadata (chapters, hashes, counts)
    - Create GitHub issue with detailed body
    - Mention @francisfuzz in issue body
    - Add labels: `data-update`, `requires-review`

#### Workflow 2: `deploy-datasette.yml`
- **Trigger:** `workflow_dispatch` (manual only)
- **Jobs:**
  - `prepare-and-deploy`:
    - Check out repo
    - Build Docker image
    - Mount data volume
    - Run `scripts/chapter_titles.py`
    - Rebuild FTS: `sqlite-utils enable-fts data/hts.db hts_entries description --fts5 --replace`
    - Run `datasette publish fly data/hts.db --app="tariff-everywhere" --metadata metadata.json --install=datasette-search-all --install=datasette-render-html --setting default_page_size 50`
  - `update-issue` (optional):
    - Find the most recent open HTS data issue
    - Add comment: "Deployment triggered by @{actor} at {timestamp}"

### Secrets & Configuration

**Required GitHub Secrets:**
- `FLY_API_TOKEN` — Fly.io API token (created via `flyctl auth token`)
  - Must have permission to deploy to app `tariff-everywhere`
  - Should be stored at repo level, not organization level (least privilege)

**Environment variables (in workflows):**
- None required beyond what's in `requirements.txt` and `Dockerfile`

### Docker & Data

**Build:**
- Reuse existing `Dockerfile` (already supports Python, sqlite3, datasette, etc.)
- Mount `-v "$(pwd)/data:/app/data"` for persistence

**Data flow:**
- `refresh.py` updates `data/hts.db` in-place
- `chapter_titles.py` updates `chapters.description` with real titles
- FTS rebuild runs against existing DB
- `datasette publish fly` reads from local DB and pushes to Fly.io

### Credentials & Security

**Fly.io Token Generation:**
1. Run locally: `flyctl auth token` (requires `flyctl` CLI)
2. Copy output token
3. Store as GitHub secret `FLY_API_TOKEN` (repo settings → Secrets & variables → Actions)
4. Reference in workflow as `${{ secrets.FLY_API_TOKEN }}`

**GitHub Token:**
- Use default `GITHUB_TOKEN` provided by Actions for issue creation/commenting
- No additional secrets needed

## Data Model

### GitHub Issue (Change Notification)

**Metadata captured:**
```
Issue Title: [HTS Data Update] Changes detected in 3 chapters (2026-03-24T14:30Z)

Issue Body:
## Summary
Changes detected in HTS tariff data during scheduled refresh.

## Changed Chapters
- **Chapter 01** (Live Animals and Products): hash changed `abc123...` → `def456...`
- **Chapter 74** (Copper and Articles): hash changed `xyz789...` → `uvw012...`
- **Chapter 99** (Custom Code): hash changed `aaa111...` → `bbb222...`

## Details
- Total entries in database: 134,523
- Chapters affected: 3 of 99
- Detection timestamp: 2026-03-24T14:30:00Z
- Workflow run: [#42](https://github.com/francisfuzz/usitc-app/actions/runs/12345678)

## Next Steps
Review the changes above. When ready, click the "Run workflow" button in the [Deploy Datasette](https://github.com/francisfuzz/usitc-app/actions/workflows/deploy-datasette.yml) workflow to approve and deploy.

Labels: data-update, requires-review
Mentions: @francisfuzz
```

### Audit Trail

**Issue comments:**
```
Deployment triggered by @francisfuzz at 2026-03-24T15:00:00Z
Workflow run: [#43](https://github.com/francisfuzz/usitc-app/actions/runs/87654321)
Deployment completed successfully. Datasette redeployed at https://tariff-everywhere.fly.dev/
```

## API/Interface Contracts

### Workflow Inputs (deployment trigger)

**Name:** `deploy-datasette.yml`
**Dispatch input (optional):**
```yaml
inputs:
  approval:
    description: "Confirm deployment (yes/no)"
    required: false
    default: "yes"
```

### `refresh.py` Exit Behavior

**Current behavior (inferred from CLAUDE.md):**
- `refresh.py` hashes all 99 chapters in parallel
- Compares against stored hashes in `chapters` table
- If any chapter differs: re-ingests that chapter, updates `last_changed_at`
- Updates `last_checked_at` for all chapters

**Required for workflow:**
- Exit code `0` on success (regardless of changes detected)
- Stdout/stderr logged by GitHub Actions (no special parsing needed)
- Check SQL query to determine if `last_changed_at` was updated in this run:
  ```sql
  SELECT COUNT(*) FROM chapters WHERE last_changed_at > (NOW() - INTERVAL '5 minutes')
  ```

### `datasette publish fly` Contract

**Current command:**
```bash
datasette publish fly data/hts.db \
  --app="tariff-everywhere" \
  --metadata metadata.json \
  --install=datasette-search-all \
  --install=datasette-render-html \
  --setting default_page_size 50
```

**Required environment:**
- `FLY_API_TOKEN` set in environment
- `flyctl` CLI available in Docker image (currently installed via `requirements.txt` + `Dockerfile`)
- No interactive prompts (fully automated)

## Edge Cases & Error Handling

### Case 1: No changes detected
- Workflow completes silently
- No issue created
- No notification sent
- Next scheduled run in 6 hours

### Case 2: `refresh.py` fails
- Workflow logs error to stdout/stderr
- No issue created (workflow fails)
- User can review in Actions tab and trigger manual retry
- **Mitigation:** Add error step that sends Slack notification (optional future enhancement)

### Case 3: Multiple overlapping scheduled runs
- GitHub Actions queues them; second run starts after first completes
- Both use the same `data/hts.db`; no race conditions expected (SQLite is single-writer)
- If both detect changes, two issues created (acceptable; maintainer reviews both)

### Case 4: Deployment fails
- Workflow logs error
- Issue remains open (manual intervention required)
- User retries via `workflow_dispatch` or investigates Fly.io logs
- Comment added to issue: "Deployment failed. See workflow run [#N](link)"

### Case 5: GitHub token expires or is revoked
- Issue creation fails
- Workflow fails
- `GITHUB_TOKEN` is auto-refreshed by Actions (no manual intervention needed)

### Case 6: Fly.io token expires
- `datasette publish fly` fails with auth error
- Workflow fails
- User must generate new token and update `FLY_API_TOKEN` secret
- Retry via `workflow_dispatch`

### Case 7: Manual deployment without recent changes
- Workflow runs `datasette publish fly` on stale DB
- Redeploys the same data (no-op for Fly.io)
- Acceptable; useful for config/plugin updates independent of data

## Success Metrics

1. **Uptime:** Workflows run successfully ≥99% of scheduled intervals
2. **Detection latency:** Changes detected within 6 hours of USITC update
3. **Notification latency:** Issue created within 2 minutes of detection
4. **Approval turnaround:** Average time from notification to deployment approval <4 hours
5. **Audit trail:** All change detection and deployment events logged in issues + workflow runs
6. **Zero manual steps:** No manual `refresh.py` or `datasette publish fly` commands needed (after initial setup)

## Open Questions

1. Should failed refresh runs create an issue, or log silently? (Spec assumes silent; can add notification if needed)
2. Should the deployment workflow include a pre-deployment validation step (e.g., test that Datasette starts)? (Spec assumes simple redeploy; can add checks)
3. Should old HTS data issues be auto-closed when new ones are created? (Spec assumes manual closure; can add auto-close step)
4. Should deployment be skipped if the most recent commit is a bot (e.g., Dependabot) change? (Spec assumes all deployments are valid; can add filters)

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Stale Fly.io token | Deployment fails silently | Set token expiry reminder; use short-lived tokens if possible |
| GitHub API rate limits | Issue creation fails | Unlikely at this scale; monitor Actions logs |
| USITC API outage | `refresh.py` fails | Workflow logs error; maintainer retries manually |
| Database corruption | Broken DB deployed | Add pre-deploy validation; test Datasette startup |
| Accidental manual deploy | Stale data goes live | Issue created with change details; reviewer catches before approving |
| Multiple overlapping deploys | Race condition | GitHub Actions serializes workflow runs by default |
| Notification spam | Maintainer overwhelmed | Batch-notify only if >5 chapters change (future enhancement) |

## Implementation Plan

1. **Secrets setup:** Generate Fly.io token, store as `FLY_API_TOKEN` GitHub secret
2. **Workflow 1:** Create `.github/workflows/refresh-hts-data.yml` with 6-hour cron + manual trigger
3. **Workflow 2:** Create `.github/workflows/deploy-datasette.yml` with manual trigger only
4. **Testing:** Run workflows manually in staging to verify issue creation, deployment, and error handling
5. **Merge:** PR → code review → merge to `main`
6. **Monitoring:** Watch Actions tab for first few scheduled runs; adjust cron if needed

