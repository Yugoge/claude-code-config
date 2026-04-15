# Plan: /usr/bin/happy-dev Binary + Docker Build Hook

## Context

The dev daemon systemd service was using `/usr/bin/happy` (production global binary), causing Bug #62's MCP fix to be ignored after every restart. We just fixed the systemd service to use `node /root/happy-dev/.../dist/index.mjs` directly, but the user wants a proper parallel binary mechanism — `/usr/bin/happy-dev` — matching how production uses `/usr/bin/happy`. Plus a docker build hook to prevent building dev images with production URLs.

## Task 1: Create `/usr/bin/happy-dev` global binary

**The infrastructure already exists.** `/root/happy-dev/packages/happy-cli/bin/happy-dev.mjs` is a wrapper that:
- Sets `HAPPY_HOME_DIR=$HOME/.happy-dev` and `HAPPY_VARIANT=dev`
- Adds `--no-warnings --no-deprecation` flags
- Imports `../dist/index.mjs` (resolves to `/root/happy-dev/.../dist/index.mjs` via symlink)

**Steps:**
1. Create symlink: `ln -s /root/happy-dev/packages/happy-cli/bin/happy-dev.mjs /usr/bin/happy-dev`
2. Verify: `ls -la /usr/bin/happy-dev` shows correct target
3. Verify: the relative `../dist/index.mjs` resolves to `/root/happy-dev/packages/happy-cli/dist/index.mjs`

**Architecture after fix:**
```
/usr/bin/happy     → /usr/lib/node_modules/happy-coder/bin/happy.mjs     → prod dist/index.mjs
/usr/bin/happy-dev → /root/happy-dev/packages/happy-cli/bin/happy-dev.mjs → dev dist/index.mjs
```

## Task 2: Update systemd service to use `/usr/bin/happy-dev`

**File:** `/etc/systemd/system/happy-daemon-dev.service`

Change:
```
ExecStart=/usr/bin/node --no-warnings --no-deprecation /root/happy-dev/packages/happy-cli/dist/index.mjs daemon start
ExecStop=/usr/bin/node --no-warnings --no-deprecation /root/happy-dev/packages/happy-cli/dist/index.mjs daemon stop
```
To:
```
ExecStart=/usr/bin/happy-dev daemon start
ExecStop=/usr/bin/happy-dev daemon stop
```

Note: `happy-dev.mjs` already handles `--no-warnings --no-deprecation` and `HAPPY_HOME_DIR`. Keep `HAPPY_SERVER_URL=http://localhost:3005` and `IS_SANDBOX=1` in the service Environment lines (the binary doesn't set these).

Then: `systemctl daemon-reload` (do NOT restart service)

## Task 3: Docker build hook (project-level only)

**New file:** `/dev/shm/dev-workspace/happy-dev/.claude/hooks/pretool-docker-dev-guard.sh`

Rule: If bash command contains `docker build` AND contains `api.life-ai.app` (without `api-dev`), BLOCK it.
- `HAPPY_SERVER_URL=https://api.life-ai.app` → BLOCKED (production URL for dev image)
- `HAPPY_SERVER_URL=https://api-dev.life-ai.app` → ALLOWED

**Register in:** `/dev/shm/dev-workspace/happy-dev/.claude/settings.json` under PreToolUse hooks, matcher "Bash".

## Task 4: Update hooks to reference `/usr/bin/happy-dev`

Update `pretool-bash-safety.sh` (project-level) to also block any attempt to overwrite or delete `/usr/bin/happy-dev`.

## Critical Files

| File | Action |
|------|--------|
| `/usr/bin/happy-dev` | Create (symlink) |
| `/etc/systemd/system/happy-daemon-dev.service` | Edit ExecStart/ExecStop |
| `/dev/shm/dev-workspace/happy-dev/.claude/hooks/pretool-docker-dev-guard.sh` | Create |
| `/dev/shm/dev-workspace/happy-dev/.claude/settings.json` | Edit (add Bash hook) |
| `/dev/shm/dev-workspace/happy-dev/.claude/hooks/pretool-bash-safety.sh` | Edit (protect /usr/bin/happy-dev) |

## Verification

1. `ls -la /usr/bin/happy-dev` → symlink to `/root/happy-dev/packages/happy-cli/bin/happy-dev.mjs`
2. `readlink -f /usr/bin/happy-dev` → `/root/happy-dev/packages/happy-cli/bin/happy-dev.mjs`
3. `grep ExecStart /etc/systemd/system/happy-daemon-dev.service` → `/usr/bin/happy-dev daemon start`
4. `systemctl show happy-daemon-dev --property=ExecStart` → confirms new binary loaded
5. Production services unchanged: `grep ExecStart /etc/systemd/system/happy-daemon.service` → `/usr/bin/happy`
6. Docker hook test: a bash command with `docker build ... api.life-ai.app` should be blocked
7. Next daemon restart: MCP title change should work
