---
description: Multi-source deep research with 15-20 iterative searches
argument-hint: <research-topic>
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

Use Playwright MCP **in parallel** to extract content:
```
For each authoritative URL:
1. Navigate using mcp__playwright__navigate
2. Extract using mcp__playwright__evaluate with script:
   "document.body.innerText"
3. Analyze for: facts, data, expert opinions, recent developments
4. Include: publication date, author/organization, main arguments
```

**Fallback**: If Playwright unavailable, synthesize from WebSearch results only.

### Phase 5: Contradiction & Gap Analysis
Review all gathered information and identify:
- Conflicting viewpoints or data
- Information gaps that need additional searches
- Questions that remain unanswered

If significant gaps exist, execute 2-3 more targeted searches.

### Phase 6: Synthesis & Report Generation
Compile comprehensive research report:

```markdown
## Deep Research Report: $ARGUMENTS

### Executive Summary
[2-3 paragraph synthesis of key findings]

### Main Findings
1. **[Key Finding 1]**
   - Evidence: [...]
   - Sources: [URL1, URL2]
   - Confidence: High/Medium/Low

2. **[Key Finding 2]**
   - Evidence: [...]
   - Sources: [URL3, URL4]
   - Confidence: High/Medium/Low

[Continue for 5-7 key findings]

### Detailed Analysis
#### [Sub-topic 1]
[Detailed analysis with citations]

#### [Sub-topic 2]
[Detailed analysis with citations]

### Contrarian Viewpoints
[List alternative perspectives or criticisms found]

### Information Gaps
[What remains unclear or needs more research]

### Sources Used
1. [Title] - [URL] - [Date] - [Credibility: High/Medium/Low]
2. [...]

### Research Metadata
- Total searches: [N]
- Sources analyzed: [N]
- Time period covered: [...]
- Last updated: [Date]

### Recommendations
[Actionable insights or next steps based on findings]
```

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
