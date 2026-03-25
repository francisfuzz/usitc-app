# Deployment Testing Guide

This guide walks through testing the scheduled HTS refresh and continuous deployment workflows after they're merged to `main`.

## Prerequisites

- Workflows merged to `main` branch
- `FLY_API_TOKEN` GitHub secret configured
- Access to GitHub Actions tab in the repository

## Test 1: Refresh Detection (No Real Data Changes)

**Goal:** Verify the refresh workflow runs and completes without false positives

**Steps:**

1. Navigate to **Actions** → **Refresh HTS Data** workflow
2. Click **"Run workflow"** dropdown
3. Keep default branch (`main`) selected
4. Click **"Run workflow"** button

**Expected result:**
- Workflow runs in ~1-2 minutes
- Builds Docker image
- Runs `scripts/refresh.py`
- Queries database for recent changes
- **No GitHub issue created** (no real HTS changes)
- Workflow status: ✅ **Success**

**What happened:**
- `refresh.py` checked USITC API, found no changes from last run
- No chapters updated their `last_changed_at` timestamp
- Workflow detected no recent changes, completed silently

---

## Test 2: Issue Creation (Force a Change)

**Goal:** Verify the workflow detects changes and creates a GitHub issue

**Steps:**

1. Start a Docker container with data volume mounted:
   ```bash
   docker run --rm -it -v "$(pwd)/data:/app/data" hts-local bash
   ```

2. Inside the container, open the database and update a chapter timestamp:
   ```bash
   python3 << 'EOF'
   import sqlite3
   from datetime import datetime, timedelta

   db = sqlite3.connect('/app/data/hts.db')

   # Update chapter 01's last_changed_at to 2 minutes ago
   two_mins_ago = (datetime.utcnow() - timedelta(minutes=2)).isoformat()
   db.execute(
     'UPDATE chapters SET last_changed_at = ? WHERE chapter_id = 1',
     (two_mins_ago,)
   )
   db.commit()
   db.close()
   print("Updated chapter 01 timestamp")
   EOF
   ```

3. Exit the container

4. Navigate to **Actions** → **Refresh HTS Data** workflow

5. Click **"Run workflow"** and run it

**Expected result:**
- Workflow runs
- Detects that chapter 01 has `last_changed_at` within the last 10 minutes
- **GitHub issue created** with title: `[HTS Data Update] Changes detected in HTS tariff data`
- Issue body includes:
  - Chapter 01 listed under "Changed Chapters"
  - Link to workflow run
  - Link to deployment workflow for approval
  - Mention of @francisfuzz
- Issue labels: `data-update`, `requires-review`
- Workflow status: ✅ **Success**

**How to verify:**
- Go to **Issues** tab in repository
- Find the new issue with `[HTS Data Update]` prefix
- Check that @francisfuzz is mentioned (should receive notification)

---

## Test 3: Deployment (Manual Approval)

**Goal:** Verify the deployment workflow runs and redeploys to Fly.io

**Prerequisites:**
- Test 2 completed (GitHub issue exists)

**Steps:**

1. Navigate to **Actions** → **Deploy Datasette** workflow

2. Click **"Run workflow"** dropdown

3. Keep default branch (`main`) selected

4. Click **"Run workflow"** button

**Expected result:**
- Workflow runs in ~3-5 minutes (Docker build + deployment)
- Steps complete:
  1. Checkout repository ✅
  2. Build Docker image ✅
  3. Enrich chapter titles (runs `scripts/chapter_titles.py`) ✅
  4. Rebuild FTS5 index (via `sqlite-utils`) ✅
  5. Deploy to Fly.io (using `FLY_API_TOKEN` secret) ✅
  6. Find and update issue with comment ✅
- Workflow status: ✅ **Success**
- Comment added to the test issue:
  - Shows deployment was triggered by @{your-username}
  - Includes link to workflow run
  - Confirmation: "Deployment completed successfully. Datasette redeployed at https://tariff-everywhere.fly.dev/"

**How to verify:**
1. Check the issue created in Test 2
2. Scroll to comments section
3. Verify the deployment comment is present
4. Visit https://tariff-everywhere.fly.dev/ in browser
5. Data should be present (same as before, since we only forced a detection, not actual new data)

---

## Test 4: Scheduled Runs

**Goal:** Verify the workflow runs automatically on the 6-hour schedule

**Steps:**

1. Note the current time (UTC)
2. Calculate the next :12 mark:
   - If now is 00:00-00:11 → next run is 00:12
   - If now is 00:13-05:59 → next run is 06:12
   - If now is 06:00-06:11 → next run is 06:12
   - (etc., every 6 hours)

3. Wait for the scheduled time
4. Refresh the **Actions** tab
5. Check **Refresh HTS Data** workflow

**Expected result:**
- Workflow automatically triggered at the scheduled :12 mark
- Runs without manual intervention
- If USITC has real HTS data changes → issue created
- If no changes → workflow completes silently
- Repeats every 6 hours (00:12, 06:12, 12:12, 18:12 UTC)

**How to verify:**
- GitHub Actions → Refresh HTS Data → Click on the run
- Check the "created_at" timestamp in the workflow details
- Should match one of the :12 UTC times

---

## Test 5: Real Data Changes (Eventual)

**Goal:** Verify the full workflow end-to-end with actual USITC data updates

**When:** This test happens naturally when USITC updates tariff data

**Expected behavior:**
1. Scheduled workflow runs at next :12 mark
2. `refresh.py` detects actual HTS changes (some chapters have different data)
3. Workflow creates GitHub issue with real chapter changes
4. @francisfuzz gets notified
5. Review the issue and decide whether to deploy
6. Click "Run workflow" on Deploy Datasette workflow
7. Live data is updated at https://tariff-everywhere.fly.dev/

---

## Debugging Failed Workflows

### Workflow failed with "FLY_API_TOKEN not found"
- **Cause:** Secret not configured
- **Fix:** Go to repo Settings → Secrets and variables → Actions, verify `FLY_API_TOKEN` exists

### Issue not created despite detected changes
- **Cause:** `actions/github-script` may be failing
- **Debug:**
  1. Click the failed workflow run
  2. Click the "Create issue for detected changes" step
  3. Review the full error logs
  4. Common issues: GitHub token permissions, malformed JSON in script

### Deployment failed with authentication error
- **Cause:** `FLY_API_TOKEN` expired or invalid
- **Fix:**
  1. Generate new token: `flyctl auth token`
  2. Update the GitHub secret
  3. Retry the deployment workflow

### Database locked error
- **Cause:** Another process is using `data/hts.db`
- **Debug:**
  1. Check if a previous `refresh.py` run is still in progress
  2. If container is hung: `docker ps` → `docker kill <container-id>`
  3. Retry the workflow

---

## Cleanup After Testing

After completing tests, you may want to:

1. **Close test issues:**
   - Find issues created during Test 2
   - Close them manually (they're test data)

2. **Reset chapter timestamps (optional):**
   ```bash
   docker run --rm -it -v "$(pwd)/data:/app/data" hts-local bash
   # Inside container:
   python3 << 'EOF'
   import sqlite3
   from datetime import datetime

   db = sqlite3.connect('/app/data/hts.db')
   # Reset a chapter's timestamp to now (no more "changes detected")
   db.execute(
     'UPDATE chapters SET last_changed_at = ? WHERE chapter_id = 1',
     (datetime.utcnow().isoformat(),)
   )
   db.commit()
   db.close()
   EOF
   ```

3. **Monitor first real scheduled run:**
   - Watch the Actions tab on the next :12 UTC mark
   - Verify it runs automatically without manual trigger

---

## Success Criteria

All tests pass when:
- ✅ Test 1: Refresh workflow runs, no false issues
- ✅ Test 2: Forced changes create issue with details and @francisfuzz mention
- ✅ Test 3: Deployment workflow runs, updates issue, deploys to Fly.io
- ✅ Test 4: Scheduled workflow runs automatically at :12 marks
- ✅ Test 5 (eventual): Real data changes trigger full workflow

Once all criteria met, the deployment system is production-ready.
