# Production Catastrophe Incident — 2026-04-04

> Full stories behind rules 8–13 in `~/.claude/CLAUDE.md`. The slimmed CLAUDE.md keeps only the one-line rule; this file keeps the reasoning.

---

## Rule 8 — NEVER npm install -g from dev/worktree/overnight environments

On 2026-04-04, a subagent ran `npm install -g packages/happy-cli` from an
overnight worktree. This replaced `/usr/lib/node_modules/happy` with a
symlink to the worktree (version 1.1.3). 6 hours later, another subagent
ran `happy --version`, triggering auto-upgrade version mismatch detection.
The production daemon was killed. ALL production sessions were destroyed.
The replacement daemon lived 1 second before systemd killed it. Session
recovery failed.

NEVER run `npm install -g` from any non-production path. The global binary
is shared by ALL daemons — changing it is a nuclear option. Only the user
may install the global CLI manually from `/root/happy`.

---

## Rule 9 — NEVER invoke the global happy CLI binary from agents

`/usr/bin/happy` is shared by all 3 daemons. Any invocation
(`happy --version`, `happy daemon status`, etc.) can trigger auto-upgrade
if the binary version doesn't match the running daemon. This killed
production on 2026-04-04.

To interact with dev daemon, use its HTTP control port or
`node <path>/dist/index.mjs` directly.

---

## Rule 10 — NEVER kill PIDs directly — use service controls

On 2026-04-04, killing dev session PIDs cascaded to production via session
recovery watcher. Use `systemctl restart happy-daemon-dev` or daemon HTTP
`/stop` endpoint, NEVER `kill <PID>`.

---

## Rule 11 — Subagent prompts must explicitly list what is FORBIDDEN

Every subagent prompt that touches infrastructure must include an explicit
"DO NOT" section. Listing only positive instructions is insufficient —
subagents will take unlisted destructive actions if not explicitly
forbidden. The 2026-04-04 incident happened because the dev subagent
prompt said "deploy CLI" without saying "DO NOT npm install -g".

---

## Rule 12 — E2E verification requires LIVE browser rendering (desktop + mobile)

Code review, bundle grep, and curl are NEVER sufficient for UI
verification. If content doesn't exist in the dev environment, subagents
MUST send messages via the UI to trigger it, then verify the rendered
result. This was violated by 10+ subagents across multiple sessions.

---

## Rule 13 — NEVER let a single subagent handle multiple tasks (no multitasking)

Each subagent invocation MUST handle exactly ONE issue/task/problem. The
orchestrator may launch multiple subagents in parallel for different
issues, but each individual subagent receives exactly one issue. This
applies to ALL subagent types: BA analyzes ONE issue, Dev implements ONE
fix, QA verifies ONE fix.

Bundling multiple issues into a single subagent prompt causes: (1) reduced
quality per issue, (2) unclear accountability when something fails,
(3) partial failures that are hard to retry. If you need to fix 5 issues,
launch 5 BA + 5 Dev + 5 QA subagents (potentially in parallel), NOT 1 BA +
1 Dev + 1 QA handling all 5.
