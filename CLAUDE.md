# Global Claude Code Configuration

> Personal global settings for all projects
> Last updated: 2025-10-25

---

## 🎯 Core Principles

**IMPORTANT: Always follow these rules:**
- **Security First**: NEVER hardcode secrets, API keys, or passwords
- **Read Before Edit**: Always read files before modifying them
- **Clear Communication**: Provide file paths with line numbers (e.g., `src/index.ts:42`)
- **Parallel Execution**: Run independent tool calls in parallel
- **Use TodoWrite**: Track complex tasks with the TodoWrite tool

---

## 🚫 ABSOLUTE PROHIBITIONS - NEVER VIOLATE THESE

**CRITICAL: These actions are PERMANENTLY FORBIDDEN under ALL circumstances:**

### Docker & Process Management
- ❌ **NEVER restart Docker**: `systemctl restart docker` is FORBIDDEN
- ❌ **NEVER stop Docker**: `systemctl stop docker` is FORBIDDEN
- ❌ **NEVER modify Docker daemon config**: `/etc/docker/daemon.json` is READ-ONLY
- ❌ **NEVER stop/restart any "happy" containers**: `docker stop/restart happy-*` is FORBIDDEN
- ❌ **NEVER stop/restart any "claude" processes**: Any process with "claude" in name is PROTECTED
- ❌ **NEVER use generic commands to stop services**: Including but not limited to:
  - `killall`, `pkill`, `kill -9`
  - `systemctl stop/restart *` (any service)
  - `docker-compose down/restart`
  - `docker system prune -a`
  - Any command that could affect running services

### Configuration Files
- ❌ **NEVER modify settings.json**: ANY `.vscode/settings.json`, `settings.json`, or Claude Code settings
- ❌ **NEVER modify Claude configuration**: `.claude.json`, `.claude/*` config files (only CLAUDE.md is allowed)
- ❌ **NEVER add/modify VS Code settings**: Including workspace or user settings

### Enforcement
**If user requests ANY of the above actions:**
1. **REFUSE immediately** - Do NOT execute
2. **Explain the rule** - Reference this section
3. **Suggest alternatives** - If applicable

**This applies even if:**
- User says "optimize", "improve", "fix", "configure"
- User doesn't explicitly mention Docker but action would affect it
- Action seems beneficial or harmless
- It's part of a larger workflow

**NO EXCEPTIONS. NO WORKAROUNDS. NO JUSTIFICATIONS.**

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
