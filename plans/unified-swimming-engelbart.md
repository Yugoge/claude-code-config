# CLI Rebuild Recovery Plan

## Context

The globally installed happy-cli binary (`/usr/lib/node_modules/happy-coder/`) was contaminated on Mar 28 18:34 by a dev-overnight agent that rsynced worktree code into `/root/happy` and then built+installed from there. The binary contains `shouldHideParentToolCall` that only handles `"Task"` but not `"Agent"`, causing all Agent tool sidechain messages in new sessions to have mismatched IDs (Anthropic `toolu_01...` vs CUID2) that never link in the app reducer.

## Current State

| Daemon | Sessions | Status | Binary |
|--------|----------|--------|--------|
| default | 11 active | running (PID 3933790) | contaminated 0.14.0-0 |
| jade | 2 active | running (PID 49734) | contaminated 0.14.0-0 |
| dev | 2 active | running (PID 1339479) | contaminated 0.14.0-0 |
| **Total** | **15 sessions** | | |

**17 running Claude session processes** across all 3 daemons.

All 3 daemons use the SAME global binary. Version is `0.14.0-0` both in source and installed, so the daemon auto-upgrade heartbeat will NOT detect the change (it compares version strings, not binary content).

## Problem: Auto-Upgrade Won't Trigger

The daemon heartbeat at `run.ts:748-752` compares `package.json` version on disk vs `startedWithCliVersion`. Both are `0.14.0-0`, so even after rebuilding, the daemon won't auto-restart. **Manual daemon restart is required.**

## Recovery Plan

### Phase 1: Snapshot (before any changes)

```bash
# Save session snapshots for all 3 daemons
bash /root/bin/happy-session-recovery.sh save
HAPPY_HOME_DIR=/root/.happy-jade bash /root/bin/happy-session-recovery.sh save
HAPPY_HOME_DIR=/root/.happy-dev bash /root/bin/happy-session-recovery.sh save
```

### Phase 2: Rebuild CLI from clean source

```bash
cd /root/happy/packages/happy-cli && yarn build
cd /root/happy && npm install -g .

# Verify: shouldHideParentToolCall must NOT exist in the new binary
grep -c "shouldHideParentToolCall" /usr/lib/node_modules/happy-coder/dist/types-*.mjs
# Expected: 0

# Verify: sendExisting must exist
grep -c "sendExisting" /usr/lib/node_modules/happy-coder/dist/index-*.mjs
# Expected: > 0

# Verify: correct Task||Agent check
grep "Task.*Agent" /usr/lib/node_modules/happy-coder/dist/types-*.mjs | head -3
```

### Phase 3: Bump version to force auto-upgrade

Instead of manually restarting daemons (which kills all 17 sessions), bump the version in `package.json` to `0.14.0-1`. The daemon heartbeat will detect the mismatch and auto-restart, which automatically re-spawns all sessions with `--resume`.

```bash
# Bump version
cd /root/happy/packages/happy-cli
# Edit package.json: "version": "0.14.0-0" -> "0.14.0-1"
yarn build
cd /root/happy && npm install -g .
```

The daemon heartbeat checks every 60 seconds. Within 1-2 minutes, all 3 daemons will:
1. Detect version mismatch (`0.14.0-0` running vs `0.14.0-1` on disk)
2. Self-restart with new binary
3. Re-spawn all sessions via `--resume` from `session_dirs.txt`

**Risk**: This is the same mechanism that normally handles `npm install -g happy-coder@latest`. Sessions resume with full history via `--resume` + `sendExisting`.

### Phase 4: Verify recovery

```bash
# Wait ~2 minutes, then check
for svc in happy-daemon happy-daemon-jade happy-daemon-dev; do
  echo "=== $svc ==="
  systemctl is-active $svc
done

# Check daemon versions updated
cat /root/.happy/daemon.state.json | python3 -c "import sys,json; d=json.load(sys.stdin); print('DEFAULT ver:', d.get('startedWithCliVersion'))"
cat /root/.happy-jade/daemon.state.json | python3 -c "import sys,json; d=json.load(sys.stdin); print('JADE ver:', d.get('startedWithCliVersion'))"
cat /root/.happy-dev/daemon.state.json | python3 -c "import sys,json; d=json.load(sys.stdin); print('DEV ver:', d.get('startedWithCliVersion'))"

# Check no shouldHideParentToolCall in new binary
grep -c "shouldHideParentToolCall" /usr/lib/node_modules/happy-coder/dist/types-*.mjs
# Expected: 0

# Check sessions are back
ps aux | grep -E "index.*\.mjs.*claude" | grep -v grep | wc -l
```

### Phase 5: Update investigation doc + add safety hook

1. Update `/root/docs/SIDECHAIN-DISPLAY-BUG-INVESTIGATION.md` with fix applied timestamp
2. Add hook to block `rsync` and `cp` commands targeting `/root/happy/packages/` from non-happy paths (prevent future contamination)

### Phase 6: Log the full incident

Update investigation doc Section 10 with:
- Fix applied timestamp
- Verification results
- Note about existing broken sessions (created Mar 28 18:34 ~ fix date)

## Existing Broken Sessions

Sessions created between Mar 28 18:34 and the fix will have permanently mismatched IDs in the DB. Options:
1. **Accept it** — old data, diminishing relevance
2. **App-side fallback** — modify `reducerTracer.ts` to also check `envelope.ev.args?.sessionSubagent` when `toolCallToMessageId` lookup fails (requires dev web image rebuild)

## Critical Notes

- This session (`6088b4d4`) is one of the 11 default daemon sessions — it will be killed and resumed during Phase 3
- The `--resume` + `sendExisting` path works correctly (verified: `sendExisting` exists in current binary and production source)
- All 3 daemons (default, jade, dev) are affected identically — same global binary
