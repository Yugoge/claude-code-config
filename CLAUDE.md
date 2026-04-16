# CLAUDE.md

> Project-specific settings for .claude
> Last updated: 2026-03-26

---

# Global Claude Code Configuration

> Personal global settings for all projects
<!-- AUTO:last-updated -->
> Last updated: 2026-04-16
<!-- /AUTO:last-updated -->

---

## 🚨 Production Catastrophe Lessons (2026-04-04)

**These rules were learned from a catastrophic incident that killed ALL production sessions. They are NON-NEGOTIABLE.**

### 8. NEVER npm install -g from dev/worktree/overnight environments
On 2026-04-04, a subagent ran `npm install -g packages/happy-cli` from an overnight worktree. This replaced `/usr/lib/node_modules/happy` with a symlink to the worktree (version 1.1.3). 6 hours later, another subagent ran `happy --version`, triggering auto-upgrade version mismatch detection. The production daemon was killed. ALL production sessions were destroyed. The replacement daemon lived 1 second before systemd killed it. Session recovery failed. NEVER run `npm install -g` from any non-production path. The global binary is shared by ALL daemons — changing it is a nuclear option. Only the user may install the global CLI manually from `/root/happy`.

### 9. NEVER invoke the global happy CLI binary from agents
`/usr/bin/happy` is shared by all 3 daemons. Any invocation (`happy --version`, `happy daemon status`, etc.) can trigger auto-upgrade if the binary version doesn't match the running daemon. This killed production on 2026-04-04. To interact with dev daemon, use its HTTP control port or `node <path>/dist/index.mjs` directly.

### 10. NEVER kill PIDs directly — use service controls
On 2026-04-04, killing dev session PIDs cascaded to production via session recovery watcher. Use `systemctl restart happy-daemon-dev` or daemon HTTP `/stop` endpoint, NEVER `kill <PID>`.

### 11. Subagent prompts must explicitly list what is FORBIDDEN, not just what is allowed
Every subagent prompt that touches infrastructure must include an explicit "DO NOT" section. Listing only positive instructions is insufficient — subagents will take unlisted destructive actions if not explicitly forbidden. The 2026-04-04 incident happened because the dev subagent prompt said "deploy CLI" without saying "DO NOT npm install -g".

### 12. E2E verification requires LIVE browser rendering on BOTH desktop and mobile
Code review, bundle grep, and curl are NEVER sufficient for UI verification. If content doesn't exist in the dev environment, subagents MUST send messages via the UI to trigger it, then verify the rendered result. This was violated by 10+ subagents across multiple sessions.

### 13. NEVER let a single subagent handle multiple tasks (multitask)
Each subagent invocation MUST handle exactly ONE issue/task/problem. The orchestrator may launch multiple subagents in parallel for different issues, but each individual subagent receives exactly one issue. This applies to ALL subagent types: BA analyzes ONE issue, Dev implements ONE fix, QA verifies ONE fix. Bundling multiple issues into a single subagent prompt causes: (1) reduced quality per issue, (2) unclear accountability when something fails, (3) partial failures that are hard to retry. If you need to fix 5 issues, launch 5 BA + 5 Dev + 5 QA subagents (potentially in parallel), NOT 1 BA + 1 Dev + 1 QA handling all 5.

---

## 🔄 Auto-Commit Mechanism

The development environment has an automatic checkpoint/commit system. When subagents make file changes, those changes may be auto-committed before the orchestrator can verify them via `git diff`. This means:

- `git diff` may show empty even though changes were successfully made
- Changes appear in recent `git log` as "checkpoint: Auto-save at ..." or "Auto-commit: ..." entries
- To verify subagent work, check `git log --oneline -5` and `git show <hash> --stat` instead of `git diff`
- Never assume "git diff is empty = nothing was done" — always check recent commits first

---

## 🚨 Overnight Incident Lessons (2026-03-28)

**These rules were learned from a catastrophic overnight session failure. They are NON-NEGOTIABLE.**

### 1. Never weaken checks to "fix" failures
When a validation/check rejects output, the problem is the OUTPUT, not the check. Fix the upstream code that produces bad output. NEVER: lower thresholds, swallow exceptions, change error→warning, skip validation. If the reference implementation passes the same check, the check is correct.

### 2. PM only prioritizes — PM never proposes solutions
PM ranks issues by severity and orders pipelines. PM does NOT suggest "add component X", "rename Y to Z", or "change layout to W". Solutions are BA's and Dev's job. Every time PM proposed a solution in overnight, it was garbage.

### 3. Specialists report symptoms only — no root cause, no fix suggestions
Specialists observe and report what they see. They do NOT analyze why or suggest how to fix. Root cause analysis is exclusively BA's job. When architect diagnosed "threshold too strict" instead of "content too short", the entire fix chain went wrong.

### 4. Always compare with reference implementation BEFORE fixing
When the user says "align with X", every fix must be validated against X's behavior. The overnight session "fixed" height_ratio by lowering the threshold to 0.40 while the reference produces 0.98. Nobody checked.

### 5. Output quality > no errors
QA passing means the output is HIGH QUALITY, not just "no exceptions". A half-empty resume that doesn't crash is still a failed generation.

### 6. Never make "improvements" the user didn't ask for
Overnight added TipsBox to fill empty space (user had deliberately removed it), renamed a template heading (nobody asked), added features. These are regressions, not improvements. If the user didn't report it as broken, don't change it.

### 7. Global agent files must be project-agnostic
Files in `~/.claude/agents/` and `~/.claude/commands/` are used across ALL projects. Never put project-specific examples (applio, resume, height_ratio) in global files. Use generic terms.

---

## 🚨 SUPER MANDATORY: Orchestrator-Only Rule

**This is the highest-priority rule. It overrides everything else.**

The main agent MUST NOT perform any direct operations. All work goes through subagents (Agent tool). No exceptions.

**Forbidden in main agent**: All tools not listed below (enforced by `pretool-orchestrator-gate.py`).

**Always allowed**: Agent, TodoWrite, AskUserQuestion, Skill, CronCreate, CronDelete, CronList, ScheduleWakeup, mcp__happy__change_title, Bash, Read (≤600 lines), Glob, Grep.

**Read limit**: Main agent Read is capped at 600 lines by `pretool-read-size-guard.py`. For larger files, delegate to a subagent. IMPORTANT: When delegating, instruct the subagent to **summarize** the file and return only the relevant findings — NEVER ask it to return the raw file contents, as that defeats the purpose of the size guard by flooding the main context window.

**Bash usage**: Main agent CAN and SHOULD use Bash for quick operations: git commands, jq queries, file checks, ls, state file reads. Do NOT delegate trivial shell commands to subagents.

**Permanently forbidden**: EnterPlanMode, ExitPlanMode — never use these, even with /do.

**Exception**: The user has invoked `/do` in this session, which grants consent for direct operations.

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

## 🎨 Applio Design System

**Project**: applio.life-ai.app | Next.js 14 + Tailwind CSS | `/root/applio/frontend/`

### Color Palette

**Mint Green (Primary — `brand-*`)**:
| Token | Hex | Usage |
|-------|-----|-------|
| brand-100 | `#D4F3ED` | Backgrounds, hover states |
| brand-200 | `#BCEAE0` | Light fills, badges |
| brand-300 | `#A3E4D7` | Primary accent (base mint green) |
| brand-400 | `#6DCFBF` | Interactive elements |
| brand-500 | `#3FB8A5` | Buttons, CTA |
| brand-600–900 | darker | Text on light, focus rings |

**Sky Blue (Secondary — `sky-*`)**:
| Token | Hex | Usage |
|-------|-----|-------|
| sky-100 | `#C2E0F6` | Info backgrounds |
| sky-200 | `#A3CFF0` | Light fills |
| sky-300 | `#85C1E9` | Secondary accent (base sky blue) |
| sky-400 | `#5AAAD8` | Links, interactive |
| sky-500 | `#2E8FC4` | Buttons, emphasis |
| sky-600–900 | darker | Text, focus rings |

### Glass-Morphism (Apple-inspired)

| Class | Usage | Effect |
|-------|-------|--------|
| `.glass` | NavBar, BottomTabBar | `bg-white/70 backdrop-blur-[12px]` + subtle border |
| `.glass-heavy` | Modals, dialogs | `bg-white/80 backdrop-blur-[20px]` + stronger shadow |
| `.glass-subtle` | Cards | `bg-white/90 backdrop-blur-[8px]` |
| `.glass-mint` | Mint-tinted surfaces | `bg-[#A3E4D7]/20` + 12px blur |
| `.glass-sky` | Sky-tinted surfaces | `bg-[#85C1E9]/20` + 12px blur |

**Rules**: Glass on chrome (nav, modals, cards). Flat on content (forms, text). Dark mode + `@supports` fallback included.

### Brand
- Always lowercase "applio" (never "Applio")
- No hardcoded Chinese strings in source code (use i18n `t()` keys instead)
- The app supports multiple locales (en, zh). NEVER delete locale files, NEVER remove the language switcher, NEVER narrow the Locale type.
- All DEFAULT user-facing strings should have English as fallback

### Config: `frontend/tailwind.config.js`

---

## 🖥️ Server Infrastructure

**Hardware**: ***REDACTED-HOST***, 16 vCPU, 32GB RAM, 20GB Swap | Ubuntu Linux
**Docs**: `docs/ARCHITECTURE.md`, `docs/HAPPY-ARCHITECTURE.md`, `docs/SERVER-SETUP.md`, `docs/DISK-ARCHITECTURE.md`

### Disk Layout
- System disk `/dev/sda1` (610G): ALL active data — OS, /root, Docker, swap
- `/root` directly on sda1 (no bind mount)
- Docker: default `/var/lib/docker` (on sda1, no data-root in daemon.json)
- Swap: `/swapfile` (on sda1)
- No external volumes (sdb removed 2026-03-21)
- swappiness=1 (`/etc/sysctl.conf` + `/etc/sysctl.d/99-performance.conf`)

### Happy 三层架构
```
happy-app (浏览器/手机 React Native) ←WS→ happy-server (Fastify+PG) ←WS→ happy-cli (Daemon+CLI+Claude)
```
- 所有数据客户端加密后传输，服务器只存加密 blob
- 密钥体系：Ed25519签名 + Curve25519加密 + AES-256对称，详见 `docs/HAPPY-ARCHITECTURE.md` §3
- 四 Daemon：default (`/root/.happy/`) + jade (`/root/.happy-jade/`) + dev (`/root/.happy-dev/`) + qijie (`/root/.happy-qijie/`)

### Other Systemd Services
| Service | Port | Purpose |
|---------|------|---------|
| claudecodeui | 3001 | Claude Code Web UI (dev.life-ai.app via Cloudflare tunnel) |
| baton-host | 9966 | Remote clipboard bridge |

### Cloudflare Tunnels
- `life-ai.app` → happy-server (port 3000) + happy-web (8090)
- `dev.life-ai.app` → happy-web-dev (port 8097)

### Web Auth Pages (Browser Login)
| Account | URL | Password |
|---------|-----|----------|
| Default | `https://life-ai.app/auth/default` | `***REDACTED***` |
| Jade | `https://life-ai.app/auth/jade` | `***REDACTED***` |
| Qijie | `https://life-ai.app/auth/qijie` | `***REDACTED***` |
| Dev | `https://dev.life-ai.app/auth/dev` | `***REDACTED***` |
Files: `/root/deploy/auth-pages/{default,jade,qijie,dev}/index.html`

### Docker Services (compose: `/root/deploy/docker-compose.yml`)
<!-- AUTO:docker-services -->
All 22 containers managed by single compose project, `restart: always`:
| Service | Container | Port | Notes |
|---------|-----------|------|-------|
| postgres | happy-postgres | internal | postgres:15-alpine |
| redis | happy-redis | internal | redis:7-alpine |
| minio | happy-minio | 9000→9000, 9001→9001 | minio/minio:latest |
| happy-server | happy-server | 3000→3005 | happy-server-happy-server; depends on postgres, redis, minio |
| cloudflared-lifeai | cloudflared-lifeai | host network | cloudflare/cloudflared:latest; depends on happy-server, happy-web, budget-web, applio-web |
| happy-web | happy-web | 8090→80 | happy-app:message-fixes; depends on happy-server |
| postgres-dev | happy-postgres-dev | internal | postgres:15-alpine |
| redis-dev | happy-redis-dev | internal | redis:7-alpine |
| happy-server-dev | happy-server-dev | 3005→3005 | happy-server-dev:latest; depends on postgres-dev, redis-dev, minio |
| happy-web-dev | happy-web-dev | 8097→80 | happy-app:dev; depends on happy-server-dev |
| knowledge-web | knowledge-web | 8092→80 | nginx:alpine |
| budget-web | budget-web | 8093→80 | nginx:alpine |
| leadership-web | leadership-web | 8091→80 | nginx:alpine |
| travel-web | travel-web | 8094→80 | nginx:alpine |
| apply-web | apply-web | 8095→80 | nginx:alpine |
| applio-postgres | applio-postgres | internal | postgres:16-alpine |
| applio-redis | applio-redis | internal | redis:7-alpine |
| applio-api | applio-api | internal | applio-api:latest; depends on applio-postgres, applio-redis |
| applio-worker | applio-worker | internal | applio-api:latest; depends on applio-api |
| applio-beat | applio-beat | internal | applio-api:latest; depends on applio-api |
| applio-web | applio-web | 8096→3000 | applio-web:latest; depends on applio-api |
| ib-gateway | ib-gateway | 127.0.0.1→4001→4003, 127.0.0.1→4002→4004, 127.0.0.1→5900→5900 | ghcr.io/gnzsnz/ib-gateway:stable |
<!-- /AUTO:docker-services -->

### Systemd Services (non-Docker)
<!-- AUTO:systemd-services -->
| Service | Status | Purpose |
|---------|--------|---------|
| happy-daemon | enabled | |
| happy-daemon-jade | enabled | |
| happy-session-watcher | enabled | |
| hapi-hub | unknown | |
| hapi-runner | unknown | |
| hapi-restore | unknown | |
| hapi-session-watcher | unknown | |
<!-- /AUTO:systemd-services -->

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
