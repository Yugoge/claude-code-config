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

## 🌐 Advanced Web Search & Deep Navigation | 高级网络搜索与深度导航

### Deep Search Methodology | 深度搜索方法论

**CRITICAL RULE: When user requests finding official documents, guides, or deep website information, automatically use the Deep Search Strategy.**

**触发条件 | Trigger Conditions:**
- "找到官方文档" / "Find official documentation"
- "深度搜索网站" / "Deep search the website"
- "站内查找" / "Search within site"
- "下载 PDF/表单" / "Download PDF/forms"
- Any research task requiring 5+ sources

**可用命令 | Available Commands:**
- `/deep-search <domain> <goal>` - Site-specific deep exploration
- `/research-deep <topic>` - Multi-source research (15-20 searches)
- `/search-tree <question>` - MCTS-inspired path exploration
- `/reflect-search <goal>` - Iterative search with reflection
- `/site-navigate <url> <task>` - Intelligent site navigation

### Strategy Selection | 策略选择

**Simple queries (1-3 searches)**:
- Use WebSearch directly
- Example: "What is the capital of France?"

**Complex queries (5-10 searches)**:
- Use `/research-deep`
- Example: "AI chip market trends 2025"

**Site-specific searches**:
- Use `/deep-search <domain> <goal>`
- Example: Finding Korean visa application guide on hikorea.go.kr

**Multi-path problems**:
- Use `/search-tree`
- Example: "How to start an AI company?"

**Verification needed**:
- Use `/reflect-search`
- Example: Finding specific regulatory requirements

### Execution Patterns | 执行模式

**Pattern 1: Parallel Breadth-First**
```
Phase 1: 3-5 parallel WebSearch (broad topics)
Phase 2: Extract key URLs from all results
Phase 3: 5-10 parallel WebFetch (deep content)
Phase 4: Synthesize with Claude
```

**Pattern 2: Iterative Depth-First**
```
Loop (max 10 iterations):
  1. Search current topic
  2. Analyze results
  3. Extract next sub-topic
  4. If goal achieved: break
  5. Else: search sub-topic
```

**Pattern 3: Tree Exploration (MCTS-inspired)**
```
1. Generate 3-5 possible search paths
2. Evaluate each path (score 0-10)
3. Explore top 2 paths in parallel
4. Recurse on most promising branch
5. Max depth: 3 levels
```

### WebFetch Prompt Templates | 提示模板

**Template A: Navigation Extraction**
```
Extract all navigation menu items and links from this page.
For each item provide: Menu > Submenu > URL > Description
Focus on links related to: [GOAL]
Format as structured list or JSON.
```

**Template B: Document Discovery**
```
Scan this page for downloadable documents, guides, PDFs, or forms.
Extract: Title | Type | Download URL | Description | Updated Date
Prioritize official/authoritative sources.
Return as table or JSON array.
```

**Template C: Deep Content Analysis**
```
Analyze this [document/page] and extract:
1. Main sections and purposes
2. Key requirements or procedures
3. Important dates or deadlines
4. Contact information
5. Referenced sub-documents or related links
Organize by relevance to: [GOAL]
```

### Failure Recovery Strategies | 失败恢复策略

**Level 1: Alternative Domains**
```
If WebFetch blocked on domain.com:
→ Try subdomain (e.g., api.domain.com, www.domain.com)
→ Try related domains (e.g., visa.go.kr if hikorea.go.kr fails)
```

**Level 2: Search Mirrors**
```
WebSearch: "site:domain.com mirror"
WebSearch: "[organization] official alternative site"
```

**Level 3: Third-Party Sources**
```
WebSearch: "[topic] official PDF embassy consulate"
WebSearch: "[topic] .gov OR .edu official guide"
```

**Level 4: MCP Browser Tools**
```
If Playwright MCP installed:
→ Use browser automation to bypass restrictions
→ Handle JavaScript-rendered content
```

**Level 5: Task Agent**
```
Launch general-purpose agent with creative problem-solving:
"Find alternative ways to access [goal] from [domain]"
```

### Performance Optimization | 性能优化

**Critical Rules:**
- ✅ **Always parallel** when searches are independent
- ✅ **Cache results** - avoid re-fetching same URL
- ✅ **Timeout control** - max 30s per WebFetch
- ✅ **Progress tracking** - use TodoWrite for multi-phase searches
- ✅ **Smart retries** - exponential backoff for failures

**Example Parallel Execution:**
```
BAD (sequential - 30 seconds total):
  result1 = WebFetch(url1)  # 10s
  result2 = WebFetch(url2)  # 10s
  result3 = WebFetch(url3)  # 10s

GOOD (parallel - 10 seconds total):
  [result1, result2, result3] = parallel(
    WebFetch(url1),
    WebFetch(url2),
    WebFetch(url3)
  )
```

### Integration with MCP Tools | MCP 工具集成

**Preference Order:**
1. **Static HTML pages**: Use WebFetch (fastest)
2. **Dynamic JavaScript**: Use Playwright MCP
3. **Anti-bot protection**: Use Browser MCP (logged-in session)
4. **Complex navigation**: Use custom deep-research MCP

**Auto-Detection:**
```
If WebFetch returns "<script>...</script>" heavy content:
  → Automatically retry with Playwright MCP

If response contains "403 Forbidden" or "Cloudflare":
  → Automatically use Browser MCP or search alternatives
```

---

## 💬 Interactive & Conversational Search | 交互式搜索

### Conversational Search Pattern | 对话式搜索模式

**5-Step Framework:**

**Step 1: Intent Clarification | 意图澄清**
```
User says: "帮我找韩国签证信息"

Claude responds:
"我理解您需要韩国签证信息。为了提供最准确的帮助,请告诉我:
1. 签证类型(旅游/商务/学生/工作)
2. 您的国籍
3. 具体需要的信息(申请流程/材料清单/费用/处理时间)

或者我可以先进行广泛搜索,找到所有类型的签证信息概览?"

Use <options> to offer choices.
```

**Step 2: Strategy Proposal | 策略提议**
```
Based on clarified intent, propose search strategy with <options>
```

**Step 3: Progressive Execution | 渐进执行**
```
Execute in phases, reporting progress every 2-3 steps
Use TodoWrite to track progress
```

**Step 4: Interactive Refinement | 交互优化**
```
After initial findings, ask if user wants to:
A) Continue deeper
B) Summarize current findings
C) Search specific aspect
```

**Step 5: Synthesis & Follow-up | 综合与跟进**
```
Deliver final report with follow-up options using <options>
```

### Reflection-Driven Search | 反思驱动搜索

**After each search iteration, reflect:**
```
Self-reflection questions:
1. Did this search bring me closer to the goal? Score: [1-10]
2. What critical info is still missing? - [List gaps]
3. Should I pivot strategy or go deeper? Decision: [PIVOT / DEEPEN / DONE]
4. Are there alternative paths worth exploring? Alternatives: [List if any]
```

**Auto-adjustment based on reflection:**
```
If score < 5 for 2 consecutive searches:
  → Pivot to alternative strategy
  → Ask user for clarification

If score ≥ 8:
  → Continue current path

If score = 10:
  → Goal achieved, synthesize results
```

### Quality Assurance | 质量保证

**Verification Checklist:**
- [ ] Are sources official/authoritative?
- [ ] Are URLs from the correct domain?
- [ ] Is information up-to-date (check dates)?
- [ ] Do findings actually answer the goal?
- [ ] Are there conflicting sources to reconcile?

**Citation Standards:**
```
Every claim should include:
- Source title
- URL (verified accessible)
- Publication/update date
- Excerpt or quote
- Confidence level (High/Medium/Low)
```

---

> 💡 **Tip**: Use `#` key to quickly add instructions to CLAUDE.md
> 💡 **提示**：使用 `#` 键快速添加指令到 CLAUDE.md
