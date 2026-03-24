# Global Claude Code Configuration

> Personal global settings for all projects
<!-- AUTO:last-updated -->
> Last updated: 2026-03-24
<!-- /AUTO:last-updated -->

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
- No Chinese text anywhere in the app
- All user-facing strings in English

### Config: `frontend/tailwind.config.js`

---

## 🖥️ Server Infrastructure

**Hardware**: Hetzner vServer, 16 vCPU, 32GB RAM, 20GB Swap | Ubuntu Linux
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
- 双 Daemon：default (`/root/.happy/`) + jade (`/root/.happy-jade/`)

### Other Systemd Services
| Service | Port | Purpose |
|---------|------|---------|
| claudecodeui | 3001 | Claude Code Web UI (dev.life-ai.app via Cloudflare tunnel) |
| baton-host | 9966 | Remote clipboard bridge |

### Cloudflare Tunnels
- `life-ai.app` → happy-server (port 3000) + happy-web (8090)
- `dev.life-ai.app` → claudecodeui (port 3001)

### Docker Services (compose: `/root/deploy/docker-compose.yml`)
<!-- AUTO:docker-services -->
All 16 containers managed by single compose project, `restart: always`:
| Service | Container | Port | Notes |
|---------|-----------|------|-------|
| postgres | happy-postgres | internal | postgres:15-alpine |
| redis | happy-redis | internal | redis:7-alpine |
| minio | happy-minio | 9000→9000, 9001→9001 | minio/minio:latest |
| happy-server | happy-server | 3000→3005 | happy-server-happy-server; depends on postgres, redis, minio |
| cloudflared-lifeai | cloudflared-lifeai | host network | cloudflare/cloudflared:latest; depends on happy-server, happy-web, budget-web, applio-web |
| happy-web | happy-web | 8090→80 | happy-app:message-fixes; depends on happy-server |
| knowledge-web | knowledge-web | 8092→80 | nginx:alpine |
| budget-web | budget-web | 8093→80 | nginx:alpine |
| leadership-web | leadership-web | 8091→80 | nginx:alpine |
| travel-web | travel-web | 8094→80 | nginx:alpine |
| apply-web | apply-web | 8095→80 | nginx:alpine |
| applio-postgres | applio-postgres | internal | postgres:16-alpine |
| applio-redis | applio-redis | internal | redis:7-alpine |
| applio-api | applio-api | internal | applio-api:latest; depends on applio-postgres, applio-redis |
| applio-worker | applio-worker | internal | applio-api:latest; depends on applio-api |
| applio-web | applio-web | 8096→3000 | applio-web:latest; depends on applio-api |
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
- **commands**: 25 files
- **agents**: 21 files
- **hooks**: 23 files
- **scripts**: 22 files
<!-- /AUTO:claude-inventory -->

---

## 🛠️ Tool Reference

> All built-in tool schemas are pre-loaded (`ENABLE_TOOL_SEARCH=false`).
> ToolSearch is only needed for MCP tools.
