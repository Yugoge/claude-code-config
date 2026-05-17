---
description: Intelligent site navigation simulating "click-through" exploration
argument-hint: <url> <task>
disable-model-invocation: true
---

Navigate **$1** to accomplish: **$2**

## Methodology: Simulated Navigation (Grok-style)

Simulate intelligent site navigation without actual browser interaction.

### Phase 1: Homepage Analysis

⚠️ **CRITICAL**: WebFetch is DISABLED (timeout risk). Use Playwright MCP instead.

Navigate to the starting URL ($1) using Playwright, then extract the page structure and analyze it to find information about "$2":
- Navigation menus and all visible links (anchor href values)
- Main content region (article / main / content body)
- Categories, sections, and the navigation tree
- Key links whose text or URL suggests they lead to "$2"
- Search functionality (search input, search box)
- Direct matches: content directly related to "$2"

For each relevant link, return:
- Link text
- Complete URL
- Estimated relevance to goal (High / Medium / Low)
- Why it might contain the target information

Organize the result by estimated relevance.

### Phase 2: Path Selection
From Phase 1 analysis, select the top 3 most promising links.

Selection criteria:
- Link text explicitly mentions keywords from $2
- URL structure suggests relevant content (e.g., /docs/, /guide/, /download/)
- Description indicates authoritative/official content

### Phase 3: Parallel Exploration
Navigate to the top 3 links **in parallel** using Playwright. For each link, search the page for information about "$2":
- If found: extract the complete information from the main content area, list any downloadable resources (PDFs, download links), and identify deeper links worth following.
- If not found: identify which links on this page might lead to "$2", and return the URLs of up to 3 most relevant next steps.

### Phase 4: Depth Navigation (if needed)
If Phase 3 found promising deeper links but not final target:
- Select the most promising next-level link
- Repeat navigation (max 5 total levels)
- Track path taken to avoid loops

### Phase 5: Alternative Strategies (if stuck)
If unable to find target after 3 levels:

**Strategy A**: Try site search
```
WebSearch: site:$1 "$2"
```

**Strategy B**: Look for sitemap
```
Navigate to $1/sitemap.xml or $1/sitemap.html using Playwright
```

**Strategy C**: Check common paths
```
Try: /docs/, /help/, /support/, /downloads/, /resources/
```

### Phase 6: Navigation Report
Write a structured report covering: target site and goal, navigation path per level (URL visited, what was found, link chosen and why), final result status (found/partially found/not found) with final content and URL, all URLs visited, dead ends encountered, alternative paths not taken, and recommendations.

## Execution Guidelines
1. **Depth limit: 5 levels** - prevents infinite navigation
2. **Parallel when possible**: Explore multiple promising paths at same time
3. **Track visited URLs**: Avoid revisiting same pages
4. **Prefer specificity**: Choose more specific links over general ones
5. **Look for patterns**: Official docs often in /docs/, /guide/, /help/
6. **Use TodoWrite**: Track navigation depth

## Navigation Heuristics
**High-value indicators in URLs**:
- /docs/, /documentation/
- /guide/, /tutorial/
- /download/, /files/
- /official/, /formal/
- /api/, /reference/

**High-value indicators in link text**:
- "Official guide"
- "Download"
- "Documentation"
- "How to"
- "Requirements"

## Best For
- Finding specific documents on complex government/corporate sites
- Navigating to deeply nested information
- When direct search doesn't reveal the target
- Understanding site structure and content organization
