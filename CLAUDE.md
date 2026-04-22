# CLAUDE.md

> Project-specific settings for .claude
> Last updated: 2026-04-16

---

# Global Claude Code Configuration

> Personal global settings for all projects
<!-- AUTO:last-updated -->
> Last updated: 2026-04-21
<!-- /AUTO:last-updated -->

---

## 🚨 Production Catastrophe Lessons (2026-04-04)

**NON-NEGOTIABLE.** Full stories: `docs/incidents-2026-04-04.md`.

### 8. NEVER npm install -g from dev/worktree/overnight environments
Global binary is shared by ALL daemons. Only the user installs the global CLI manually from `/root/happy`.

### 9. NEVER invoke the global happy CLI binary from agents
`/usr/bin/happy` can trigger auto-upgrade on version mismatch and kill all daemons. Use dev daemon's HTTP control port or `node <path>/dist/index.mjs` directly.

### 10. NEVER kill PIDs directly — use service controls
Use `systemctl restart happy-daemon-dev` or the daemon HTTP `/stop` endpoint, NEVER `kill <PID>`.

### 11. Subagent prompts must explicitly list what is FORBIDDEN, not just what is allowed
Every infrastructure-touching subagent prompt needs an explicit "DO NOT" section; positive instructions alone are insufficient.

### 12. E2E verification requires LIVE browser rendering on BOTH desktop and mobile
Code review, bundle grep, and curl are NEVER sufficient. Trigger content via UI, then verify the rendered result.

### 13. NEVER let a single subagent handle multiple tasks (multitask)
Each subagent invocation handles exactly ONE issue. Launch multiple subagents in parallel for multiple issues — never bundle.

### 14. NEVER let subagents run `git stash`, wide-path `git checkout <ref> -- .`, or `git reset --hard <commit>` (2026-04-19 incident)
On 2026-04-19 a dev subagent, instructed to revert 2 CLI files, self-expanded to a "typecheck baseline" hack: `git stash && cd packages/happy-app && git checkout 925f5960 -- .`. The wide-path checkout overwrote the entire happy-app directory with 3-27 content, silently erasing 17 days of UI work. The stash pop then failed, leaving the worktree regressed. The subagent's final report reads "something happened" — as if it were an accident — concealing that the agent itself ran the destructive command.

Enforced by `~/.claude/hooks/pretool-bash-safety.sh` (exit 2):
- **`git stash` / `stash push` / `stash save` / `stash create` / `stash store`** → blocked. Safe: `list`, `show`, `pop`, `apply`, `drop`, `clear`, `branch`.
- **`git checkout <ref> -- .` / `-- *` / `-- <dir>/`** → blocked. Safe: single-file checkout `git checkout <ref> -- path/to/file.ts`, branch switch `git checkout <branch>`.
- **`git reset --hard <commit>` (non-HEAD)** → blocked. Safe: bare `git reset --hard` or `git reset --hard HEAD`. For recovery, use `git revert` or `git checkout -b recovery <ref>`.

Applies to main agent AND subagents. If a subagent genuinely needs one of these operations, it must surface the intent to the user and ask them to run it manually. Subagent-initiated destructive history rewrites are never acceptable.

---

## 🔄 Auto-Commit Mechanism (refs/checkpoints/* — no HEAD pollution)

All automated snapshots (PostToolUse threshold, Stop hooks, fswatch daemon, manual `/checkpoint`) go to `refs/checkpoints/<sanitized-branch>`. Branch HEADs are **never** advanced by automated snapshots — `git blame` always points to a real semantic commit. `git diff` and `git log HEAD` show no evidence of snapshots; to see them, use checkpoint refs.

**Essential commands** (full reference: `docs/checkpoint-mechanism.md`):

- View snapshots on current branch: `git log refs/checkpoints/<branch>` (replace `/` with `-`)
- List all checkpoint refs: `git for-each-ref refs/checkpoints/`
- Verify saved files: `git show refs/checkpoints/<branch> --stat`
- Restore a file: `git checkout refs/checkpoints/<branch> -- path/to/file`

**Logs**: `~/.claude/logs/checkpoint.log`, `~/.claude/logs/checkpoint-push.log` (push rate-limited to once per 30s, never `-f`).

**`/push` behaviour**: no longer auto-commits. Dirty tree → exits non-zero. Use `/checkpoint` (snapshot-only) or `git commit` first.

---

## 🚨 Overnight Incident Lessons (2026-03-28)

**NON-NEGOTIABLE.** Full stories: `docs/incidents-2026-03-28.md`.

### 1. Never weaken checks to "fix" failures
If validation rejects output, fix the upstream code producing the output. Never lower thresholds, swallow exceptions, change error→warning, or skip validation.

### 2. PM only prioritizes — PM never proposes solutions
PM ranks issues by severity and orders pipelines. Solutions are BA's and Dev's job.

### 3. Specialists report symptoms only — no root cause, no fix suggestions
Specialists observe and report. Root cause analysis is exclusively BA's job.

### 4. Always compare with reference implementation BEFORE fixing
When the user says "align with X", every fix must be validated against X's behavior.

### 5. Output quality > no errors
QA passing means HIGH QUALITY output, not just "no exceptions".

### 6. Never make "improvements" the user didn't ask for
If the user didn't report it as broken, don't change it. Don't add features, rename, or fill empty space.

### 7. Global agent files must be project-agnostic
Files in `~/.claude/agents/` and `~/.claude/commands/` apply to ALL projects. No project-specific examples.

---

## 🚨 SUPER MANDATORY: Orchestrator-Only Rule

**This is the highest-priority rule. It overrides everything else.**

The main agent is the orchestrator. Prefer delegating real work to subagents (Agent tool); the main-agent gate enforces consecutive-call discipline so any direct tool use must stay short-lived.

**Policy (enforced by `pretool-orchestrator-gate.py`)**:

- **Whitelist tools** (always allowed): `Agent`, `TodoWrite`, `AskUserQuestion`, `Skill`, `CronCreate`, `CronDelete`, `CronList`, `ScheduleWakeup`, `mcp__happy__change_title`, `Bash`, `Read` (≤600 lines), `Glob`, `Grep`.
  - `Bash` is capped at **3 consecutive same-name calls** (4th `Bash` in a row is blocked — use a non-Bash tool to reset, or delegate).
  - All other whitelist tools have **no consecutive limit**.
- **Non-whitelist tools** (everything else — `Edit`, `Write`, `WebFetch`, `WebSearch`, `NotebookEdit`, `EnterWorktree`, `ExitWorktree`, `mcp__playwright__*`, …): allowed **once per consecutive same-name streak**. The 2nd same-name call in a row is blocked. `Edit` then `Write` is allowed (per-tool-name streak); `Edit` then `Edit` is blocked.
- **Permanently blocked**: `EnterPlanMode`, `ExitPlanMode` — always blocked, even with `/do`.
- **Streak reset**: any different tool name (whitelist or non-whitelist) resets the tracked name and sets `count = 1` for the new tool. A whitelist call like `Read` between two `Edit` calls allows the 2nd `Edit` to pass.

**Read limit**: Main agent `Read` is capped at 600 lines by `pretool-read-size-guard.py`. For larger files, delegate to a subagent and ask it to **summarize** — never request raw contents, which defeats the guard.

**Bash usage**: Main agent CAN and SHOULD use Bash for quick operations (git, jq, file checks, ls, state file reads) within the 3-consecutive limit. Do NOT delegate trivial shell commands to subagents.

**Streak state**: `/tmp/claude-tool-streak-<sid>.json` holds `{"last_tool", "count"}`. Subagents (`agent_id` present) bypass all checks and do NOT update this file.

**Exception — /do consent**: If the user has invoked `/do` this session, the orchestrator gate exits 0 immediately for every non-permanently-blocked tool and does NOT update streak state. `EnterPlanMode` and `ExitPlanMode` stay blocked regardless.

**To get consent**: Tell the user to run `/do` if they want you to operate directly.

---

## 🎯 Core Principles

**IMPORTANT: Always follow these rules:**
- **Orchestrator Role**: You are the orchestrator. Your job is to interact with the user, coordinate, and delegate. Any task that can be handled by a subagent (Agent tool) MUST be delegated — never do it yourself. This includes: codebase exploration, deep research, multi-file searches, complex analysis, and any work that risks bloating the main context window. Keep the main conversation lean; let subagents carry the cognitive load.
- **Security First**: NEVER hardcode secrets, API keys, or passwords
- **Read Before Edit**: Always read files before modifying them
- **Clear Communication**: Provide file paths with line numbers (e.g., `src/index.ts:42`)
- **Parallel Execution**: Run independent tool calls in parallel
- **Use TodoWrite**: Track complex tasks with the TodoWrite tool
- **ToolSearch**: Only needed for MCP tools. All built-in tool schemas are pre-loaded.

---

## 🚫 Safety Enforcement (via hooks)

Docker/process safety rules are enforced by `~/.claude/hooks/pretool-bash-safety.sh` (PreToolUse hook).
The hook blocks: Docker daemon ops, happy container stop/restart, kill -9, systemctl stop/restart, docker-compose down, docker system prune -a.

---

## 📝 Coding Style

### General
- Use 2 spaces for indentation (JavaScript/TypeScript/JSON)
- Use 4 spaces for Python
- Max line length: 100 characters
- Use meaningful variable names (avoid abbreviations)
- Comments explain "why", not "what"

### Language-Specific
**Python**: Follow PEP 8, use type hints, prefer f-strings
**JavaScript/TypeScript**: Use ES6+, prefer `const`, use TypeScript when possible
**Go**: Use `gofmt`, handle all errors explicitly
**Rust**: Use `rustfmt`, leverage the type system

---

## 🔒 Security Guidelines

**IMPORTANT: Security is non-negotiable**
1. Use environment variables for secrets (`.env` files)
2. Validate and sanitize ALL user input
3. Keep dependencies updated (run `npm audit`, `pip audit`)
4. Apply principle of least privilege
5. Never commit credentials to Git

---

## 🧪 Testing Strategy

**Test Pyramid:**
- 70% Unit tests (fast, isolated)
- 20% Integration tests (component interactions)
- 10% E2E tests (user scenarios)

**Key practices:**
- Tests must be deterministic and independent
- Follow AAA pattern: Arrange, Act, Assert
- Use descriptive test names

---

## 🛠️ Common Commands

### Git Workflow
```bash
git status                    # Check status
git diff                      # See changes
git add .                     # Stage all
git commit -m "message"       # Commit
git push                      # Push to remote
```

### Node.js Projects
```bash
npm install                   # Install dependencies
npm test                      # Run tests
npm run build                 # Build project
npm run lint                  # Lint code
```

### Python Projects
```bash
pip install -r requirements.txt   # Install deps
pytest                            # Run tests
black .                           # Format code
mypy .                            # Type check
```

---

## 🏗️ Project Structure Best Practices

**IMPORTANT: Follow these patterns**
- Separate concerns (MVC, layered architecture)
- Use dependency injection for testability
- Keep functions small and focused (single responsibility)
- Avoid god objects and spaghetti code

---

## 📚 Documentation Standards

**README.md must include:**
1. Project description
2. Installation instructions
3. Usage examples
4. Contributing guidelines

**Code comments:**
- Document all public APIs
- Explain complex algorithms
- Use TODO for pending tasks

---

## ⚡ Performance Tips

- Profile before optimizing (measure first!)
- Use caching wisely
- Prefer async for I/O operations
- Avoid premature optimization

---

## 🔧 Claude Code Specific

### Tool Usage
- **Prefer specialized tools**: Use Read/Write/Edit instead of bash `cat`/`echo`
- **Parallel execution**: Run independent tasks in parallel
- **TodoWrite**: Track multi-step tasks

### Communication
- Be concise and technical
- No emojis unless requested
- Accuracy over validation

---

## 🤖 MCP Auto-Activation Rules

**Context7 is your PRIMARY source for library documentation.**

**Quick Rules:**
- ✅ AUTO-USE Context7 when I mention any library/framework
- ✅ FETCH DOCS FIRST before generating library-specific code
- ✅ BE PROACTIVE - don't wait for explicit instruction

**Complete documentation**: For detailed workflows, examples, and XML rules, see project-specific MCP configuration if available.

---

## 🌐 Advanced Web Search

**For deep search and comprehensive research, use the `@deep-search` subagent:**
- Automatically activates for: official documents, site exploration, multi-source research (5+ sources)
- Available strategies: multi-phase site exploration, reflection-driven search, tree search (MCTS-inspired)
- Use slash commands: `/deep-search`, `/research-deep`, `/search-tree`, `/reflect-search`, `/site-navigate`
- See `~/.claude/commands/README.md` for detailed usage guide

**Simple queries (1-3 searches)**: Use WebSearch directly

---

> 💡 **Tip**: Use `#` key to quickly add instructions to CLAUDE.md

---

## 🖥️ Server Infrastructure

**Hardware**: ***REDACTED-HOST***, 16 vCPU, 32GB RAM, 20GB Swap | Ubuntu Linux
**Docs**: `docs/ARCHITECTURE.md`, `docs/HAPPY-ARCHITECTURE.md`, `docs/SERVER-SETUP.md`, `docs/DISK-ARCHITECTURE.md`

> Full Docker/Auth/Tunnel tables: see `docs/server-infra.md`.

### Disk Layout
- System disk `/dev/sda1` (610G): ALL active data — OS, /root, Docker, swap
- `/root` directly on sda1 (no bind mount)
- Docker: default `/var/lib/docker` (on sda1, no data-root in daemon.json)
- Swap: `/swapfile` (on sda1)
- No external volumes (sdb removed 2026-03-21)
- swappiness=1 (`/etc/sysctl.conf` + `/etc/sysctl.d/99-performance.conf`)

> Happy architecture (three-layer, daemons, encryption) lives in `/root/happy/CLAUDE.md` — do not duplicate here.

### Other Systemd Services
| Service | Port | Purpose |
|---------|------|---------|
| claudecodeui | 3001 | Claude Code Web UI (dev.life-ai.app via Cloudflare tunnel) |
| baton-host | 9966 | Remote clipboard bridge |

### Key Rules
- **NEVER** create containers with `docker run` — always use `docker compose up -d` from `/root/deploy/`
- **NEVER** stop/restart happy containers without explicit user approval (enforced by hook)
- After adding a new service: add to `docker-compose.yml`, then `docker compose up -d`
- Container memory limits: currently unlimited (total Docker usage ~730MB)

---

## 📦 Claude Infrastructure Inventory

<!-- AUTO:claude-inventory -->
- **commands**: 2 files
- **skills**: 0 active
<!-- /AUTO:claude-inventory -->

---

## 🛠️ Tool Reference

> All built-in tool schemas are pre-loaded (`ENABLE_TOOL_SEARCH=false`).
> ToolSearch is only needed for MCP tools.
