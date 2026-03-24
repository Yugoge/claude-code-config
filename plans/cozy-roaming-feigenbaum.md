# Fix Session Recovery Script

## Context

After server reboot, Happy sessions are not restored. Two root causes:

1. **`save_session_state()`** uses `happy daemon list` which only returns sessions tracked in the daemon's in-memory map. Currently returns 0 sessions — the 2 running `claude` processes (PIDs 5125, 42177) are invisible to the daemon because they weren't spawned by the current daemon instance.

2. **`restore_online_sessions()`** queries `/v2/sessions/active` from the Happy server API, which returns nothing after reboot (20-min timeout marks all sessions `active: false`).

Additionally, only the `.happy` daemon is handled — the `.happy-jade` instance is ignored.

## Changes

### File: `/root/bin/happy-session-recovery.sh` (full rewrite)

#### A. Configuration (lines 1-8)

- Remove `HAPPY_SERVER_URL` and `ACCESS_KEY` — no longer query the server API
- Add `HAPPY_HOMES=("/root/.happy" "/root/.happy-jade")` for multi-instance support
- Keep `LOG_FILE=/var/log/happy-session-recovery.log`
- Add `SESSION_FILE="session_dirs.txt"` (filename within each HAPPY_HOME)

#### B. Remove unused functions

- Delete `get_server_sessions()` (lines 14-18)
- Delete `get_local_sessions()` (lines 21-26)

#### C. New helper: `scan_running_sessions()`

Discovers ALL running claude sessions via process scanning:
1. `pgrep -x claude` to find all claude PIDs
2. For each PID:
   - Skip if PPID is also a claude process (subagent)
   - Get cwd from `readlink /proc/$PID/cwd`
   - Compute project dir: `/root/.claude/projects/` + cwd with `/` → `-`
   - Find most recently modified `.jsonl` in that project dir (exclude subagents/)
   - Extract UUID from filename
3. Output: `claude_uuid:working_dir` per line

#### D. Rewrite `save_session_state()`

1. Call `scan_running_sessions()` to get all running sessions
2. Write results to `$HAPPY_HOME/session_dirs.txt` for each configured HAPPY_HOME
3. Format: `claude_uuid:working_dir` (one per line, with header comment)
4. Atomic write via `.tmp` + `mv`

Old format was `happy_cuid:working_dir`. New format uses Claude UUID because that's what `--resume` needs.

**Backward compat**: Old-format lines (CUID starting with `cmm`) will be detected and skipped during restore since no matching `.jsonl` file will be found.

#### E. Rewrite `restore_online_sessions()`

1. Wait up to 30s for at least one daemon to start (check `daemon.state.json` PID alive)
2. Read `session_dirs.txt` from all HAPPY_HOMEs, deduplicate by UUID
3. Call `scan_running_sessions()` to get already-running UUIDs
4. For each saved session NOT currently running:
   - Verify working directory exists
   - Verify `.jsonl` session file exists
   - `cd "$work_dir" && nohup happy --resume "$uuid" --happy-starting-mode remote --started-by daemon >> "$LOG_FILE" 2>&1 &`
   - Sleep 3s between launches
5. Log summary: total saved, already running, restored, skipped

#### F. Update `monitor_sessions()`

- Replace server-based check with: compare `session_dirs.txt` against `scan_running_sessions()`
- If a saved session stopped and its `.jsonl` was modified within last 24h, trigger restore for it

#### G. Update `check` command

- Show "Saved Sessions" from `session_dirs.txt`
- Show "Running Sessions" from process scan
- Show comparison (running/missing)

### File: `/etc/systemd/system/happy-daemon-jade.service`

Add session recovery hooks matching the default service:

```ini
ExecStartPre=/bin/bash -c '/root/bin/happy-session-recovery.sh save || true'
ExecStartPost=/bin/bash -c 'sleep 10 && /root/bin/happy-session-recovery.sh restore'
```

Note: Keep `Type=oneshot` with `RemainAfterExit=yes` — this works for the jade daemon which doesn't write a PID file.

### File: `/etc/systemd/system/happy-daemon.service`

No changes needed — already has the hooks. But verify it still works with the new script format.

## Verification

1. Run `./happy-session-recovery.sh save` — should detect the 2 currently running claude sessions and write them to session_dirs.txt
2. Run `./happy-session-recovery.sh check` — should show 2 saved sessions, 2 running, all matched
3. Verify both `/root/.happy/session_dirs.txt` and `/root/.happy-jade/session_dirs.txt` have correct content
4. Run `systemctl daemon-reload` after modifying the jade service file
