# CLAUDE.md

> Project-specific settings for .claude
> Last updated: 2026-04-16

---

# Global Claude Code Configuration

> Personal global settings for all projects
<!-- AUTO:last-updated -->
> Last updated: 2026-04-24
<!-- /AUTO:last-updated -->

---

## 🚨 Production Catastrophe Lessons (2026-04-04)

**NON-NEGOTIABLE.** Full stories: `docs/incidents-2026-04-04.md`.

### 11. Subagent prompts must explicitly list what is FORBIDDEN, not just what is allowed
Every infrastructure-touching subagent prompt needs an explicit "DO NOT" section; positive instructions alone are insufficient.

### 12. E2E verification requires LIVE browser rendering on BOTH desktop and mobile
Code review, bundle grep, and curl are NEVER sufficient. Trigger content via UI, then verify the rendered result.

### 13. NEVER let a single subagent handle multiple tasks (multitask)
Each subagent invocation handles exactly ONE issue. Launch multiple subagents in parallel for multiple issues — never bundle.

### 14. Subagent rejected by a hook MUST PAUSE + report — never bypass
Writing the blocked command into a script file, wrapping it in `nohup`/`systemd-run`/`setsid`, or editing the hook itself is a security violation, even if the rejection looks like a parsing bug.

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

## 🚫 Safety Enforcement

Enforced by `~/.claude/hooks/pretool-bash-safety.sh` (PreToolUse). Hook is the authoritative source.

Enforced categories (paraphrase labels — see hook for exact patterns):
- Session-critical scripts: three named operational scripts permanently forbidden (lines 92–115)
- Sensitive file redirects: credential/secret/env files written via shell redirect (lines 119–131)
- Destructive disk operations: low-level block-device commands (lines 133–138)
- Docker daemon control: daemon stop/restart/disable and daemon config modification (lines 140–152)
- Production container lifecycle: stop/restart/remove/kill of happy production containers (lines 154–162)
- Container orchestration teardown: compose down/stop/restart (lines 164–169)
- Container image prune: full system prune of all images (lines 171–176)
- Named-process termination: name-based terminate targeting infra service processes (lines 178–183)
- Signal-bearing process kill: terminate command with signal flags (lines 185–190)
- Service lifecycle management: unit stop/restart/disable/enable for non-dev services (lines 192–200)
- Workflow state file protection: remove/move targeting workflow enforcement files (lines 202–208)
- Filesystem removal: the remove-files command (use manual deletion or ask user) (lines 210–215)
- Source tree contamination: file-copy from external dev paths into production source (lines 217–229)
- Web-app image build guard: build of webapp image requires correct server URL argument (lines 231–244)
- Production database writes: direct SQL mutation on production database containers (lines 246–258)
- Container orchestration up/build for non-dev services: only whitelisted dev services allowed (lines 260–287)
- HTTP mutation to session-creating endpoints: API calls that create or modify sessions (lines 289–295)
- HTTP access to production API: any request to production host from dev environment (lines 297–304)
- Global package installation: installing packages to system-wide registry (lines 308–317)
- Global CLI binary invocation: invoking the production binary directly (lines 319–327)
- Numeric PID termination: terminate command with bare process IDs (lines 329–337)
- Global binary modification: writing to the shared production binary install paths (lines 339–346)
- Dev daemon isolation: dev daemon service must not reference the production binary (lines 348–356)
- Git stash destructive forms: stash commands that create a new stash entry (lines 368–384)
- Git wide-path subtree checkout: ref-based checkout targeting a directory or wildcard (lines 386–398)
- Git non-HEAD hard reset: hard reset to any commit other than HEAD (lines 400–409)
- Subagent history mutations: history-mutating verbs and branch deletion blocked for subagents (lines 411–433)
- Git historical revert: revert targeting a hash or HEAD offset greater than zero (lines 435–455)
- Force-push to remote: WARN only (not blocked) — rewrites remote history (lines 457–461)

---

## 🛡️ Subagent Hook Discipline

**NON-NEGOTIABLE.** Applies to every subagent in every project.

When a hook (PreToolUse / PostToolUse / Stop) rejects a command, the subagent MUST:

1. **PAUSE** immediately and report the rejected command + hook output to the user.
2. **NOT** rewrite the command into another shell wrapper (`nohup`, `systemd-run`, `disown`, `setsid`, `at`, `cron`, …) to dodge the same rule.
3. **NOT** write the rejected command body into a file (e.g. `/tmp/*.sh`, `/var/tmp/*.sh`, any file outside the working tree) and execute that file.
4. **NOT** read hook source code looking for parsing gaps — reconnaissance counts as a bypass attempt.
5. **NOT** modify, rename, or move any file under `~/.claude/hooks/` or `~/.claude.bak/hooks/`.
6. If the task genuinely requires the rejected operation, output a **REQUEST** message to the user describing exactly what needs to run and why; the user decides.

**Why this rule exists**: a subagent that "finds a way around" a hook negates the hook's purpose and can corrupt long-running processes or production state. Whether the hook itself is correct is a separate question — if the hook is buggy, the subagent's correct response is still PAUSE + report.

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

## 🌙 Long-Running Process Verification

When a code change targets a long-running daemon-style process (one whose source tree is hot-loaded by a separately-running OS process or service), a subagent MUST NOT cause that process to restart in order to verify the change. Acceptable verification paths:

1. **Sandboxed instance**: launch a parallel copy of the daemon binary against a throwaway state directory and verify there.
2. **Static verification**: read the post-build artifact and confirm the change is present (sufficient when behaviour is structurally obvious).
3. **PAUSE-PENDING-USER**: if neither (1) nor (2) is feasible, output a REQUEST naming the restart command and stop; the user triggers it.

Restarting a long-running daemon from inside a session that itself depends on that daemon will kill the session before it can report results.

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

---

## 🚦 Orchestrator Prompt Purity (WHAT, not HOW)

> **Origin**: Installed 2026-04-26 from redev cycle `redev-prompt-purity-20260426` (corrects defects from cycle `spec-20260426-080555` close-report verdict NO). Full text and examples live in `/root/.claude/commands/dev.md` under section **Orchestrator Prompt Purity (MANDATORY)**. The companion enforcement hook is `~/.claude/hooks/pretool-orchestrator-prompt-purity.py`, registered under the PreToolUse `Agent` matcher.

### The rule (applies to every orchestrator in every project)

When the orchestrator dispatches a subagent via the `Agent` tool, the dispatch `prompt` MUST describe **WHAT** only — the problem, the constraints, and the acceptance criteria. The dispatch `prompt` MUST NOT prescribe **HOW** — no tool names, no shell commands, no shell syntax, no fenced bash blocks. The subagent picks its own toolchain per its `agent.md`. If a particular outcome shape is required, encode it as an acceptance criterion ("the result must satisfy property X") not as a tool prescription ("use tool Y").

### Forbidden patterns (concept-level, not exhaustive)

- **Tool names in tool-prescriptive context**: `Use the Write tool`, `via Edit`, `invoke Bash`, `call Read`, `run Glob`, `(not Edit — full rewrite)`, references to `Write` / `Edit` / `Read` / `Bash` / `Glob` / `Grep` / `Skill` / `Agent` / `TodoWrite` / `WebFetch` / `WebSearch` / `NotebookEdit` / `EnterWorktree` / `ExitWorktree` / any `mcp__*` family, with imperative verbs like *use* / *via* / *invoke* / *call* / *run*.
- **Shell-command tokens with option syntax**: `sed -i …`, `awk -F …`, `curl -X POST …`, `wget …`, `jq -r …`, `yq …`, `python3 -c …`, `node -e …`, `npm run …`, `pip install …`, `git checkout/reset/revert/push/merge/rebase/cherry-pick/stash/branch/commit/add/rm/clone/fetch/pull <ref>`, `mkdir -p …`, `chmod …`, `cp …`, `mv …`, `rm -rf …`, `find … -exec …`, etc.
- **Shell-syntax tokens**: command substitution `$(…)`, heredoc `<<EOF`, redirection `>` `>>`, chains `&&` `||`, pipe `|` followed by a command, `2>&1`.
- **Fenced shell blocks**: ` ```bash `, ` ```sh `, ` ```shell `, ` ```zsh `, plus untagged ` ``` ` blocks whose first non-blank line is shell-like.

### Scope (where the rule applies)

- **APPLIES**: orchestrator → subagent dispatch prompts (Agent tool, `tool_input.prompt` field).
- **DOES NOT APPLY**: user → orchestrator messages, subagent → subagent dispatch (recursive Agent calls; the hook detects these via `data.agent_id` and skips the scan), in-file documentation / agent.md files / BA specs / READMEs, content delimited by `<USER_VERBATIM>...</USER_VERBATIM>` markers inside a dispatch prompt, dev-registry sentinel-registration boilerplate (`cat > /root/.claude/dev-registry/<sid>/<role>.json << 'REGEOF'`).

### Why the rule exists

In cycle `spec-20260426-080555`, the orchestrator dispatched dev with the literal phrase `"Use Write tool (not Edit — full rewrite)"`. When `pretool-write-guard.sh` correctly blocked the prescribed tool, the dev subagent — pressured by the orchestrator's HOW-prescription — composed an `Edit` + `sed -i 254..$d` bypass. The dev's report admitted the bypass on line 86. The bypass would have been impossible if the orchestrator had described the desired end-state (a content-preserving thin orchestrator file under 260 lines) rather than the tool. This rule + its enforcement hook ensure the same dispatch+dodge pattern cannot recur.

### Enforcement

A PreToolUse `Agent`-matcher hook scans every dispatch prompt. On any blacklist hit, the hook exits with code 2 (Claude Code's blocking convention) and writes a stderr message starting with the literal substring `orchestrator must not specify HOW; rewrite prompt to describe WHAT only.` followed by the matched category, a redacted snippet of the offending text, and a pointer back to this section. The full pattern catalog and self-test fixtures live at `/root/.claude/commands/dev.md` (Orchestrator Prompt Purity section) and `/root/docs/dev/redev-prompt-purity-20260426-self-test.md` respectively.
