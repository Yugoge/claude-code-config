---
description: Deep website exploration with iterative search strategy
argument-hint: <domain> <search-goal>
disable-model-invocation: true
---

Execute deep search on **$1** to find: **$2**

## Strategy: Multi-Phase Iterative Search

### Phase 1: Parallel Discovery
Execute these searches **in parallel**:
- `site:$1 "$2"`
- `site:$1 "$2" filetype:pdf`
- `site:$1 "$2" official guide documentation manual`
- `"$2" site:$1 OR site:www.$1`

### Phase 2: Entry Point Analysis

⚠️ **CRITICAL**: WebFetch is DISABLED (timeout risk). Use Playwright MCP instead.

Use Playwright MCP to load the main homepage at $1, then extract:
- All links from the page, filtered to navigation menus and relevant sections
- Links related to "$2" (menu category, submenu name, complete URL, brief description)
- Search functionality / search box
- Document repository or download sections
- Sitemap or directory pages

### Phase 3: Breadth Exploration
From Phase 2 results, identify the top 3-5 most promising URLs.

Use Playwright MCP **in parallel** to explore each URL. For each URL, extract:
- Downloadable documents, guides, PDFs, or deep links related to "$2"
- Document title and type (PDF, DOC, etc.)
- Direct download URL or access link (href attribute)
- Description/summary from surrounding text
- Last-updated date if shown

### Phase 4: Depth Targeting
Based on Phase 3 findings, use Playwright MCP to load the most specific/relevant page and extract:
- Main content and key sections (article / main regions)
- Required steps or procedures (ordered or unordered lists)
- Important requirements or documents needed
- Contact information or support links
- Any referenced sub-pages or related documents (all hrefs)

### Phase 5: Fallback Recovery
If Playwright fails at any stage:

**Fallback A**: Search for alternative official sources
- `"$2" official mirror site`
- `"$2" embassy consulate official`
- `"$2" government portal`

**Fallback B**: Use subdomain/related domain search
- Search organization's other domains (e.g., visa.go.kr if hikorea.go.kr blocked)

**Fallback C**: Task agent for creative solutions
- Launch general-purpose agent to explore alternative paths

### Phase 6: Synthesis & Report
Compile all findings into a structured report covering: search goal, summary (searches executed, Playwright navigations, documents found), key findings with title/URL/type/status/summary, all discovered URLs, issues encountered, recommendations, and a search path log per phase.

## Critical Execution Rules
1. **Always use parallel tool calls** in Phase 1 and 3
2. **Never skip phases** - each builds on previous findings
3. **Track all visited URLs** to avoid loops
4. **Adapt dynamically** - if a phase fails, adjust strategy
5. **Provide detailed prompts** - simulate Grok's instruction-based approach
6. **Use TodoWrite** to track progress through phases
