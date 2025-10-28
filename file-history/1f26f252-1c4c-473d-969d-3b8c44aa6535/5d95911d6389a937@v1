# Global Claude Code Configuration
# 全局 Claude Code 配置

> Personal global settings for all projects | 个人全局设置，适用于所有项目
> Last updated: 2025-10-25

---

## 🎯 Core Principles | 核心原则

**IMPORTANT: Always follow these rules:**
- **Security First**: NEVER hardcode secrets, API keys, or passwords
- **Read Before Edit**: Always read files before modifying them
- **Clear Communication**: Provide file paths with line numbers (e.g., `src/index.ts:42`)
- **Parallel Execution**: Run independent tool calls in parallel
- **Use TodoWrite**: Track complex tasks with the TodoWrite tool

**重要：始终遵循以下规则：**
- **安全优先**：永远不要硬编码秘密、API密钥或密码
- **先读后改**：修改文件前务必先读取
- **清晰沟通**：提供文件路径和行号引用
- **并行执行**：并行运行独立的工具调用
- **使用TodoWrite**：用TodoWrite跟踪复杂任务

---

## 📝 Coding Style | 编码风格

### General | 通用
- Use 2 spaces for indentation (JavaScript/TypeScript/JSON)
- Use 4 spaces for Python
- Max line length: 100 characters
- Use meaningful variable names (avoid abbreviations)
- Comments explain "why", not "what"

### Language-Specific | 语言特定
**Python**: Follow PEP 8, use type hints, prefer f-strings
**JavaScript/TypeScript**: Use ES6+, prefer `const`, use TypeScript when possible
**Go**: Use `gofmt`, handle all errors explicitly
**Rust**: Use `rustfmt`, leverage the type system

---

## 🔒 Security Guidelines | 安全指南

**IMPORTANT: Security is non-negotiable**
1. Use environment variables for secrets (`.env` files)
2. Validate and sanitize ALL user input
3. Keep dependencies updated (run `npm audit`, `pip audit`)
4. Apply principle of least privilege
5. Never commit credentials to Git

---

## 🧪 Testing Strategy | 测试策略

**Test Pyramid:**
- 70% Unit tests (fast, isolated)
- 20% Integration tests (component interactions)
- 10% E2E tests (user scenarios)

**Key practices:**
- Tests must be deterministic and independent
- Follow AAA pattern: Arrange, Act, Assert
- Use descriptive test names

---

## 🛠️ Common Commands | 常用命令

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

## 🏗️ Project Structure Best Practices | 项目结构最佳实践

**IMPORTANT: Follow these patterns**
- Separate concerns (MVC, layered architecture)
- Use dependency injection for testability
- Keep functions small and focused (single responsibility)
- Avoid god objects and spaghetti code

---

## 📚 Documentation Standards | 文档标准

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

## ⚡ Performance Tips | 性能提示

- Profile before optimizing (measure first!)
- Use caching wisely
- Prefer async for I/O operations
- Avoid premature optimization

---

## 🔧 Claude Code Specific | Claude Code 专用

### Tool Usage
- **Prefer specialized tools**: Use Read/Write/Edit instead of bash `cat`/`echo`
- **Parallel execution**: Run independent tasks in parallel
- **TodoWrite**: Track multi-step tasks

### Communication
- Be concise and technical
- No emojis unless requested
- Accuracy over validation

---

## 🤖 MCP 工具自动激活规则 | MCP Auto-Activation Rules

### Context7 Mandatory Usage | Context7 强制使用

**CRITICAL RULE: Context7 is ALWAYS ACTIVE for ALL code-related queries.**

**You MUST automatically use Context7 MCP tools when:**
- I mention ANY library, framework, or package name (e.g., React, FastAPI, Next.js, MongoDB, etc.)
- I request code examples, implementations, or setup instructions
- I ask for configuration, installation, or usage help
- You need to verify current API documentation or best practices
- ANY code generation task involving external dependencies
- I ask "how to use X" or "show me X example"

**Mandatory Workflow:**
1. **Detect library/framework** → Automatically call `resolve-library-id` tool
2. **Get library ID** → Automatically call `get-library-docs` tool
3. **Use fetched docs** → Provide accurate, up-to-date code based on current documentation

**STRICT PROHIBITIONS:**
- ❌ **NEVER rely on training data** for library-specific code
- ❌ **NEVER generate code** without fetching Context7 docs first
- ❌ **NEVER wait** for me to say "use context7" - do it automatically
- ❌ **NEVER skip** Context7 lookup even if you think you know the answer

**Auto-Activation Examples:**
- "Create a Next.js app" → AUTO-USE Context7 for Next.js docs
- "Show me FastAPI authentication" → AUTO-USE Context7 for FastAPI docs
- "How do I use React hooks?" → AUTO-USE Context7 for React docs
- "MongoDB aggregation pipeline" → AUTO-USE Context7 for MongoDB docs

<mcp_auto_activation_rules>
  <rule_1>ALWAYS use Context7 for ANY library/framework documentation query</rule_1>
  <rule_2>Automatically invoke Context7 when generating code with external dependencies</rule_2>
  <rule_3>NEVER rely on training data for library-specific code - ALWAYS fetch current docs via Context7 FIRST</rule_3>
  <rule_4>Context7 lookup is MANDATORY, not optional - treat it as a required safety check</rule_4>
  <rule_5>Display these mcp_auto_activation_rules at the start of responses involving libraries to remind yourself</rule_5>
</mcp_auto_activation_rules>

**Why This Matters:**
- Libraries update frequently - training data becomes outdated
- Context7 provides version-specific, current documentation
- Prevents hallucinated APIs and deprecated code patterns
- Ensures best practices align with latest library versions

---

## 🌐 Advanced Web Search | 高级网络搜索

**For deep search and comprehensive research, use the `@deep-search` subagent:**
- Automatically activates for: official documents, site exploration, multi-source research (5+ sources)
- Available strategies: multi-phase site exploration, reflection-driven search, tree search (MCTS-inspired)
- Use slash commands: `/deep-search`, `/research-deep`, `/search-tree`, `/reflect-search`, `/site-navigate`
- See `~/.claude/commands/README.md` for detailed usage guide

**Simple queries (1-3 searches)**: Use WebSearch directly

---

> 💡 **Tip**: Use `#` key to quickly add instructions to CLAUDE.md
> 💡 **提示**：使用 `#` 键快速添加指令到 CLAUDE.md
