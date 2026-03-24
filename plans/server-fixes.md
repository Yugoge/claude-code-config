# Server Fixes Plan

## Task 1: Add happy-restart to boot startup

**What**: Create a systemd service that runs `happy-session-recovery.sh restore` after all daemons are up on boot.

**Implementation**:
- Create `/etc/systemd/system/happy-boot-restore.service` — a oneshot service that runs after `happy-daemon.service` and `happy-daemon-jade.service`
- It waits for both daemons then calls `happy-session-recovery.sh restore`
- Enable with `systemctl enable happy-boot-restore`

**Note**: The existing `ExecStartPost` in each daemon service already calls restore, but it races (only waits for its own daemon). The boot service ensures both daemons are up before restoring.

Actually, on review: the existing post-start scripts already do this. The issue is that after server reboot, Docker containers need to start first (docker-compose `restart: always` handles this), then the daemon services start, then sessions restore. This is already set up. The missing piece is just ensuring the daemon services are enabled (they are: `happy-daemon.service` and `happy-daemon-jade.service` are both `enabled`).

**Revised**: Just verify/fix the existing boot chain. Both daemon services are already enabled. The `ExecStartPost` already runs restore. No new service needed unless the user wants an explicit `happy-restart.sh` call on boot.

Wait — user said "happy restart脚本". Let me check what `happy-restart.sh` does.

Actually the recovery script has a `restart` command that kills daemons, restarts them, and restores sessions. For boot, we just need the daemons to start (systemd handles this) and sessions to restore (ExecStartPost handles this). So the boot chain is already correct.

**Action**: Verify the existing boot chain works. If there's a gap, create a new oneshot service.

---

## Task 2: Fix jade sessions being restored to default daemon

**Root Cause**: `write_json_snapshot` saves `home_dir` from `scan_running_sessions`, but the `home_dir` field is often empty/null because:
1. Processes spawned by `daemon_spawn_session` (recovery script) don't set `HAPPY_HOME_DIR` env var properly — only passes it if found in daemon's `/proc/PID/environ`
2. The `pid_to_home` lookup in `scan_running_sessions` only works if the daemon is running and the PID is listed in its `/list` response

**Fix in `write_json_snapshot`**: When `home_dir` is empty, infer it from the working directory pattern:
- Sessions with `working_dir` containing `jade` or `knowledge-system-jade` → `/root/.happy-jade`
- This is fragile. Better: fix the root cause.

**Better fix**: In `daemon_spawn_session`, always pass `HAPPY_HOME_DIR` as env var to spawned processes:
```bash
# In daemon_spawn_session:
[ -n "$home" ] && [ "$home" != "/root/.happy" ] && spawn_env="$spawn_env HAPPY_HOME_DIR=$home"
```

Wait — `daemon_spawn_session` already reads `HAPPY_HOME_DIR` from daemon's environ. The issue is that **the recovery script itself spawns** via `nohup node ... &`, which inherits the recovery script's env (no HAPPY_HOME_DIR set), not the daemon's env.

**Real fix in `daemon_spawn_session`**: Always explicitly set `HAPPY_HOME_DIR=$home` for the spawned process:
```bash
# Line ~580 in happy-session-recovery.sh
spawn_env="HAPPY_HOME_DIR=$home"
# Then also add server URL from daemon
```

And also fix `scan_running_sessions` to use the `pid_to_home` mapping more reliably by always falling back to checking which daemon's port the PID was spawned by.

**Files to change**:
- `/root/bin/happy-session-recovery.sh`: Fix `daemon_spawn_session` to always set `HAPPY_HOME_DIR`

---

## Task 3: Dead sessions go offline immediately

**Root Cause**: When a child process exits, `onChildExited` in `run.ts:652` only removes it from tracking. No `session-end` event is emitted to the server. The server waits 20 min heartbeat timeout.

**Fix** (two-part):

### Part A: Daemon notifies server on child death
In `run.ts`, modify `onChildExited` to also emit `session-end` via the machine socket.

1. Add method to `ApiMachineClient`:
```typescript
// apiMachine.ts
notifySessionEnd(sessionId: string) {
    this.socket.emit('session-end', { sid: sessionId, time: Date.now() });
}
```

2. In `run.ts`, update `onChildExited`:
```typescript
const onChildExited = (pid: number) => {
    const session = pidToTrackedSession.get(pid);
    if (session?.happySessionId) {
        apiMachine.notifySessionEnd(session.happySessionId);
    }
    pidToTrackedSession.delete(pid);
};
```

### Part B: Reduce server timeout as safety net
In `timeout.ts`, reduce from 20 min to 2 min for sessions (keep 20 min for machines).

**Files to change**:
- `happy/packages/happy-cli/src/api/apiMachine.ts` — add `notifySessionEnd` method
- `happy/packages/happy-cli/src/daemon/run.ts` — update `onChildExited`
- `happy/packages/happy-server/sources/app/presence/timeout.ts` — reduce session timeout to 2 min

---

## Task 4: Consolidate Cloudflare tunnels

**Current state**:
- `cloudflared` — anonymous quick tunnel → `http://happy-server:3005`
- `cloudflared-lifeai` — named tunnel (token mode, host network)
- `leadership-web` needs to be served via the same named tunnel

**Plan**:
1. Remove the `cloudflared` (anonymous tunnel) container from docker-compose
2. The `cloudflared-lifeai` named tunnel's routing is configured in Cloudflare dashboard (token mode), not in docker-compose. It already routes to the right services.
3. Verify the named tunnel config covers: happy-server (API), happy-web, leadership-web

**Files to change**:
- `/root/deploy/docker-compose.yml` — remove `cloudflared` service

---

## Task 5: Disable unnecessary services (snapd, cups, avahi-daemon)

```bash
systemctl disable --now snapd snapd.socket snapd.apparmor snapd.seeded
systemctl disable --now cups cups-browsed cups.socket cups.path
systemctl disable --now avahi-daemon avahi-daemon.socket
```

---

## Task 6: Manually recover jade sessions now

Run `happy-session-recovery.sh restore` after fixing the jade routing bug, or manually recover each jade session with `--home /root/.happy-jade`.

---

## Execution Order

1. Fix `daemon_spawn_session` in recovery script (Task 2) — prevents jade sessions from going to wrong daemon
2. Add `notifySessionEnd` to daemon (Task 3A) — immediate offline on death
3. Reduce server timeout (Task 3B) — safety net
4. Remove anonymous cloudflared (Task 4)
5. Disable services (Task 5)
6. Manually recover sessions (Task 6)
7. Verify boot chain (Task 1) — create boot service if needed
