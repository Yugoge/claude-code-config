---
description: Multi-source deep research with 15-20 iterative searches
argument-hint: <research-topic>
disable-model-invocation: true
---

Perform deep research on: **$ARGUMENTS**

## Methodology: Iterative Multi-Source Research

This command replicates Perplexity Deep Research and Claude Web's methodology.

### Phase 1: Initial Broad Search
Execute broad search to understand the landscape:
- WebSearch: "$ARGUMENTS overview"
- WebSearch: "$ARGUMENTS latest 2024 2025"
- WebSearch: "$ARGUMENTS expert analysis"

### Phase 2: Extract Key Sub-Topics
Analyze Phase 1 results and identify 3-5 key sub-topics that need deeper investigation.

Example: If researching "AI chip market trends"
Sub-topics might be: "NVIDIA AI chips", "AI chip supply chain", "emerging AI chip companies", "AI chip regulations"

### Phase 3: Parallel Deep Dive (5-10 searches)
For each sub-topic from Phase 2, execute targeted searches **in parallel**:
- WebSearch each sub-topic with specific angle
- Prioritize: academic papers, industry reports, official data

### Phase 4: Source Content Extraction (parallel)
Identify the top 5-7 most authoritative URLs from all previous results.

⚠️ **CRITICAL**: WebFetch is DISABLED (timeout risk). Use Playwright MCP instead.

Use Playwright MCP **in parallel** to extract content. For each authoritative URL, capture the page main text and analyze it for:
- Facts, data, expert opinions, recent developments
- Publication date, author / organization
- Main arguments

**Fallback**: If Playwright unavailable, synthesize from WebSearch results only.

### Phase 5: Contradiction & Gap Analysis
Review all gathered information and identify:
- Conflicting viewpoints or data
- Information gaps that need additional searches
- Questions that remain unanswered

If significant gaps exist, execute 2-3 more targeted searches.

### Phase 6: Synthesis & Report Generation
Compile a comprehensive report covering: executive summary (2-3 paragraphs), main findings (5-7) each with evidence/sources/confidence, per-sub-topic detailed analysis, contrarian viewpoints, information gaps, full sources list with credibility, research metadata (searches/sources/time period), and recommendations.

## Execution Guidelines
1. **Total searches: 15-20** (adjust based on complexity)
2. **Use parallel calls** whenever possible
3. **Prioritize authoritative sources**: .gov, .edu, major publications
4. **Track sources**: Note every URL used
5. **Check dates**: Prioritize 2024-2025 information
6. **Verify facts**: Cross-reference claims across multiple sources
7. **Use TodoWrite**: Track progress through phases

## Quality Checks
- [ ] All major viewpoints represented?
- [ ] Data from multiple independent sources?
- [ ] Recent information (within 1 year)?
- [ ] Expert opinions included?
- [ ] Potential biases noted?
