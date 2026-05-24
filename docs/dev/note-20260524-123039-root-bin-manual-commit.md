# Manual Commit Instructions: /root/bin/happy-session-recovery.sh

**Task-ID**: 20260524-123039
**Created**: 2026-05-24
**Reason**: Hook permanently blocks agent bash commands containing `happy-session-recovery`. The script at `/root/bin/happy-session-recovery.sh` cannot be committed by the agent. The user must run the git commands below from a real TTY.

---

## Script Location

- **Exact script path**: `/root/bin/happy-session-recovery.sh`
- **Repo root**: `/root`

---

## Manual Git Commands

Run the following from a real TTY (not via agent) after applying the three code changes below:

```
cd /root
git add bin/happy-session-recovery.sh
git commit -m "fix(recovery): tombstone-timing + snapshot-persistence + MemoryMax defaults (manual: agent-blocked)"
```

---

## Three Code Changes to Apply

The following three gaps were identified in `docs/dev/close-report-20260524-101700.md`. Apply each change manually to `/root/bin/happy-session-recovery.sh` before committing.

### GAP 1: Tombstone timing (immediate write on loss detection)
**Problem**: Tombstones written only after 5-min stability window → 5-min resurrection window if daemon restarts.

**Fix** — at the point where `loss_observe_mode` transitions to 1 (~line 833), immediately write tombstones for the removed UUIDs:
```bash
elif [ "$nr" -gt 0 ]; then
    loss_observe_mode=1
    loss_stable_count=0
    log "Session loss detected ($nr removed); observing for 5 minutes, auto-restore disabled"
    # ADD: immediate tombstones for removed UUIDs
    for removed_uuid in "${removed_uuids[@]}"; do
        write_tombstone "$removed_uuid" "$(get_home_for_uuid "$removed_uuid")" "immediate_loss_observed"
    done
```

### GAP 2: Snapshot persistence delay (60s window)
**Problem**: After daemon tracking confirmed, session_dirs.txt waits up to 60s (next watcher cycle). Crash in that window loses the session.

**Fix** — after `wait_for_daemon_tracking` returns 0, immediately append home to session_dirs.txt:
```bash
if wait_for_daemon_tracking "$home" "$child_pid" "$session_id" "$flavor"; then
    log "Daemon tracking confirmed for $session_id at $home (pid=$child_pid)"
    # ADD: immediate persistence
    echo "$home" >> "${HAPPY_SESSION_DIRS_FILE:-/root/.happy/session_dirs.txt}"
    sort -u "${HAPPY_SESSION_DIRS_FILE:-/root/.happy/session_dirs.txt}" -o "${HAPPY_SESSION_DIRS_FILE:-/root/.happy/session_dirs.txt}"
```

### GAP 3: MemoryMax defaults (still infinity)
**Problem**: Lines 1418-1420 default to `infinity`. No OOM protection.

**Fix**:
```bash
# FROM:
local recovery_memory_max="${HAPPY_RECOVERY_MEMORY_MAX:-infinity}"
local recovery_memory_high="${HAPPY_RECOVERY_MEMORY_HIGH:-infinity}"
local recovery_memory_swap_max="${HAPPY_RECOVERY_MEMORY_SWAP_MAX:-infinity}"

# TO:
local recovery_memory_max="${HAPPY_RECOVERY_MEMORY_MAX:-4G}"
local recovery_memory_high="${HAPPY_RECOVERY_MEMORY_HIGH:-3G}"
local recovery_memory_swap_max="${HAPPY_RECOVERY_MEMORY_SWAP_MAX:-2G}"
```

Backup: `/root/bin/happy-session-recovery.sh.bak-tombstone-snapshot-memory-20260524T120409Z`

---

## /close Todo State Confirmation (AC3)

**Workflow file**: `.claude/workflow-c216ded5-b7e1-4432-b79f-a6a2042971fe.json`

**Confirmed**: The `command` field in that file equals `"redev"` (not `"close"`). This confirms the prior stuck `/close` state for session `c216ded5-b7e1-4432-b79f-a6a2042971fe` was replaced by the `/redev` invocation. The `/close` stuck state is resolved.

The file also shows `"todo_acknowledged": true` and all workflow steps through Step 7 completed, with Step 8 (`Delegate to dev subagent`) in progress — consistent with the current active `/redev` cycle.
