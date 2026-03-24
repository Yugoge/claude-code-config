# Plan: Restore docker-compose.yml + Fix Session Recovery Pipeline

## Context

`/root/happy-server` was deleted, taking `docker-compose.yml` with it. Docker containers
are still running but unmanaged. The session recovery infrastructure also has 3 bugs
that prevent Claude processes from auto-restarting after server restart.

**What `protectActiveSessions()` does** (server-side, already working):
- Extends DB `lastActiveAt` +20 min on shutdown → sessions stay "active" in DB during restart

**What's broken** (local recovery side):
1. `happy-session-recovery.sh` fallback `work_dir` points to deleted `/root/happy-server`
2. `happy-daemon.service` ExecStartPre/Post reference wrong path for the recovery script
   (silently fail due to `|| true` — save/restore hooks never actually run)

Note: `HAPPY_SERVER_URL=http://localhost:3000` is correct — docker inspect confirms
host port 3000 maps to container port 3005.

The `happy-session-monitor.service` already provides a watchdog (polls server every 5 min,
calls `happy --resume` for missing sessions). Fixing the bugs above is sufficient.

## Complete Recovery Flow (after fixes)

```
Server shutdown → protectActiveSessions() extends lastActiveAt +20min (DB protected)
Server restarts (Docker, ~1-2 min)
Within 5 min → happy-session-monitor polls GET /v2/sessions/active on localhost:3005
             → finds sessions still active (within 20-min window)
             → compares with locally running Claude processes
             → calls `happy claude --resume <session_id>` for each missing one
             → Claude reconnects to server, loads agentState from DB, resumes
```

## Files to Modify

### 1. NEW `/root/deploy/docker-compose.yml`

Reconstruct from currently running containers via `docker inspect`.
Expected services: `happy-server`, `postgres`, `redis`, `minio`, `cloudflared`.

Critical: `happy-server` service must include build section:
```yaml
build:
  context: /root/happy
  dockerfile: Dockerfile.server-slim
image: happy-server-happy-server
container_name: happy-server
```

### 2. `/root/bin/happy-session-recovery.sh`

**Line 88** — Fix fallback working directory (deleted path):
```diff
- work_dir="/root/happy-server"  # 默认目录
+ work_dir="/root"  # 默认目录
```

### 3. `/etc/systemd/system/happy-daemon.service`

Both hooks reference `/root/happy-session-recovery.sh` but the file is at
`/root/bin/happy-session-recovery.sh`.

**Line 15**:
```diff
- ExecStartPre=/bin/bash -c '/root/happy-session-recovery.sh save || true'
+ ExecStartPre=/bin/bash -c '/root/bin/happy-session-recovery.sh save || true'
```

**Line 22**:
```diff
- ExecStartPost=/bin/bash -c 'sleep 10 && /root/happy-session-recovery.sh restore'
+ ExecStartPost=/bin/bash -c 'sleep 10 && /root/bin/happy-session-recovery.sh restore'
```

After editing:
```bash
systemctl daemon-reload
```

## Verification

```bash
# 1. Confirm docker compose works from new location
cd /root/deploy && docker compose ps

# 2. Confirm monitor is hitting correct URL
journalctl -u happy-session-monitor.service --since "5 min ago"

# 3. Manually test recovery script
/root/bin/happy-session-recovery.sh check

# 4. Confirm daemon hooks now call correct path
systemctl cat happy-daemon.service | grep ExecStart
```
