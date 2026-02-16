# Implement Iterative Bullet-Point Line Width Optimization

## Problem Summary

**Current Architecture Issue:**
- layout-optimizer agent optimizes entire HTML at once
- Can't accurately detect which specific bullet points are too long/short
- When optimization fails (height still 1.32 after claiming 1.0), no per-bullet feedback

**User Requirement (Updated):**
"我要的效果是generate自己使用脚本呢loop检测行数是否超，然后对于每一个行数超了的Bullet point都呼叫一个optimizer专门修复这一行（可以同时呼叫多个optimizer）"

Translation: In /generate workflow, use script to loop detect which bullet points exceed character limits, then call layout-optimizer to fix each one (can call multiple in parallel). Loop until all bullets are within range.

**Key Clarifications:**
- Loop = iterative step loop (if one pass doesn't fix all bullets, loop again)
- No new agent needed - reuse existing layout-optimizer
- Script detects and returns JSON list of problematic bullets
- Integrate at current optimizer step in /generate workflow

## Critical Files

- **~/.claude/commands/generate.md** - /generate workflow orchestrator (Step 9 modifications)
- **scripts/check_bullet_line_widths.py** - NEW script to detect problematic bullets
- **~/.claude/agents/layout-optimizer.md** - Agent that will be called per-bullet (already exists)

## Implementation Plan

### Part 1: Create Bullet Detection Script

Create `scripts/check_bullet_line_widths.py` to detect which bullet points exceed character limits.

**Script Specification:**

```python
#!/usr/bin/env python3
"""
Detect bullet points that exceed optimal character count ranges.

Usage:
    python3 scripts/check_bullet_line_widths.py <html_file> <template_name>

Input:
    - html_file: Path to HTML file to analyze
    - template_name: Template name (e.g., "kellogg") to calculate chars_per_line

Output JSON to stdout:
{
    "chars_per_line": 100.2,
    "single_line_range": [90, 100],
    "double_line_range": [190, 200],
    "problematic_bullets": [
        {
            "location": "experience.0.description.2",
            "content": "Led comprehensive hedge fund analysis...",
            "total_chars": 120,
            "issue": "too_long_for_single_too_short_for_double",
            "target_action": "shrink_to_single_or_expand_to_double"
        },
        {
            "location": "experience.1.description.4",
            "content": "Led analysis",
            "total_chars": 30,
            "issue": "too_short",
            "target_action": "expand_to_single"
        }
    ],
    "total_bullets_checked": 35,
    "problematic_count": 8
}

Exit codes:
    0: All bullets within range OR problematic bullets detected (check "problematic_count")
    1: Error (file not found, parsing failed, etc.)
"""
```

**Logic:**
1. Import `_extract_line_width_from_template()` from `scripts/utils.py`
2. Calculate chars_per_line for given template
3. Calculate single-line range: [0.9 * chars_per_line, 1.0 * chars_per_line]
4. Calculate double-line range: [1.9 * chars_per_line, 2.0 * chars_per_line]
5. Parse HTML to extract all bullet points (use BeautifulSoup)
6. For each bullet, count TOTAL characters in bullet text (strip HTML tags)
7. Check if total_chars falls within optimal ranges
8. If not, add to problematic_bullets list with classification:
   - `too_short`: < single_line_min (e.g., < 90)
   - `too_long_for_single_too_short_for_double`: > single_line_max AND < double_line_min (e.g., 100-190)
   - `too_long`: > double_line_max (e.g., > 200)
9. Return JSON with all problematic bullets and metadata

---

### Part 2: Modify /generate Workflow Step 9

Replace Step 9 "Smart Layout Optimization" in `.claude/commands/generate.md` with iterative bullet-point optimization loop.

**Current Step 9:**
- Lines 458-557 in generate.md
- Calls layout-optimizer once for entire HTML
- Loops up to 3 times based on page height check

**New Step 9 Architecture:**

```markdown
## Step 9: Smart Layout Optimization

This step uses an iterative bullet-point optimization loop:
1. Detect problematic bullet points using script
2. If found, call layout-optimizer in targeted mode for each problematic bullet (parallel)
3. Re-check all bullets after optimization
4. Loop until all bullets within range OR max 5 iterations reached

### 9a. Check resume page height

```bash
cd "${PROJECT_ROOT}" && source venv/bin/activate && python3 scripts/check_page_height.py "${RESUME_HTML_FILE}"
```

Output format:
```json
{
  "height_ratio": 1.15,
  "overstretched": true,
  "understretched": false,
  "target": "shrink"
}
```

### 9b. Iterative Bullet-Point Optimization Loop

**Loop initialization:**
```bash
CURRENT_HTML="${RESUME_HTML_FILE}"
ITERATION=0
MAX_ITERATIONS=5
```

**Loop condition:** While `ITERATION < MAX_ITERATIONS`:

#### Step 9b.1: Detect problematic bullets

```bash
cd "${PROJECT_ROOT}" && source venv/bin/activate && python3 scripts/check_bullet_line_widths.py "${CURRENT_HTML}" "${RESUME_TEMPLATE:-kellogg}" > /tmp/bullet_check_iter${ITERATION}.json
```

Parse output JSON and check `problematic_count`:

```bash
PROBLEMATIC_COUNT=$(jq -r '.problematic_count' /tmp/bullet_check_iter${ITERATION}.json)
```

If `PROBLEMATIC_COUNT == 0`: break loop (all bullets optimal)

#### Step 9b.2: Call layout-optimizer for each problematic bullet (PARALLEL)

Extract problematic bullets and invoke layout-optimizer agents IN PARALLEL:

```python
# Pseudo-code for orchestrator logic:
import json

with open(f'/tmp/bullet_check_iter{ITERATION}.json') as f:
    bullet_data = json.load(f)

problematic_bullets = bullet_data['problematic_bullets']

# Invoke up to 5 agents in parallel (batch if more)
batch_size = min(5, len(problematic_bullets))

for i, bullet in enumerate(problematic_bullets[:batch_size]):
    Task(
        subagent_type='layout-optimizer',
        description=f'Fix bullet {bullet["location"]}',
        prompt=f'''You are an expert layout optimizer for resume.

Your task: Optimize ONE specific bullet point to fit optimal character count range.

Input files:
- HTML content: {CURRENT_HTML}
- Critique file (for critical_info): {RESUME_CRITIQUE_FILE}

Target bullet:
- Location: {bullet['location']}
- Current content: {bullet['content']}
- Total characters: {bullet['total_chars']}
- Issue: {bullet['issue']}
- Target action: {bullet['target_action']}

Character limits (from template):
- Single-line range: {bullet_data['single_line_range'][0]}-{bullet_data['single_line_range'][1]} chars
- Double-line range: {bullet_data['double_line_range'][0]}-{bullet_data['double_line_range'][1]} chars

CRITICAL CONSTRAINTS:

1. PROTECTED CONTENT - Read critical_info from critique file, if target bullet is in critical_info DO NOT modify it (return "complete" immediately)

2. TARGET BULLET ONLY - Modify ONLY the bullet at location "{bullet['location']}", leave all other content unchanged

3. TOTAL CHARACTER COUNT:
   - Count TOTAL characters in entire bullet point string (len(bullet_text))
   - Do NOT count individual wrapped lines
   - Target: {bullet['target_action']}

   If "shrink_to_single_or_expand_to_double":
     - EITHER shrink to {bullet_data['single_line_range'][0]}-{bullet_data['single_line_range'][1]} chars
     - OR expand to {bullet_data['double_line_range'][0]}-{bullet_data['double_line_range'][1]} chars

   If "expand_to_single":
     - Expand to {bullet_data['single_line_range'][0]}-{bullet_data['single_line_range'][1]} chars

   If "shrink_to_single":
     - Shrink to {bullet_data['single_line_range'][0]}-{bullet_data['single_line_range'][1]} chars

4. PRESERVE MEANING:
   - Keep core achievement/responsibility
   - Maintain quantified metrics if present
   - Use concise, impactful wording

Output files:
- Optimized HTML: data/work/09_bullet_optimized_{bullet['location']}_iter{ITERATION}.html
- Report JSON: data/work/09_bullet_report_{bullet['location']}_iter{ITERATION}.json

Report JSON structure:
{{
  "location": "{bullet['location']}",
  "original_content": "...",
  "optimized_content": "...",
  "original_chars": {bullet['total_chars']},
  "optimized_chars": N,
  "action_taken": "shrink|expand",
  "critical_info_preserved": true
}}

After completing all tasks, return ONLY the word "complete".'''
    )
```

#### Step 9b.3: Merge optimized bullets back into HTML

After all agents return "complete", merge optimized bullets back into HTML:

```bash
# Pseudo-logic: Use a merge script
cd "${PROJECT_ROOT}" && source venv/bin/activate && python3 scripts/merge_bullet_optimizations.py \
  "${CURRENT_HTML}" \
  /tmp/bullet_check_iter${ITERATION}.json \
  data/work/09_bullet_optimized_*_iter${ITERATION}.html \
  data/work/09_merged_iter${ITERATION}.html
```

**Merge script logic:**
1. Read base HTML
2. Read each bullet optimization report to get location + optimized_content
3. Replace bullet at location with optimized_content in HTML
4. Write merged HTML to output file

#### Step 9b.4: Update loop variables

```bash
CURRENT_HTML="data/work/09_merged_iter${ITERATION}.html"
ITERATION=$((ITERATION + 1))
```

**Loop back to 9b.1**

### 9c. Final page height check

After loop completes (all bullets optimal OR max iterations):

```bash
cd "${PROJECT_ROOT}" && source venv/bin/activate && python3 scripts/check_page_height.py "${CURRENT_HTML}"
```

If height still not acceptable (0.90-1.02), invoke whole-page layout-optimizer as fallback:

```bash
# Same as old Step 9b logic - optimize entire page
```

Set `OPTIMIZED_HTML_FILE="${CURRENT_HTML}"` for next steps.

Mark this step as completed.
```

**Key Integration Points:**
- Step 9b replaces lines 478-548 in generate.md
- New loop structure: detect → optimize (parallel) → merge → repeat
- Max 5 iterations (configurable)
- Terminates when all bullets within range
- Fallback to whole-page optimizer if height still wrong after loop

---

### Part 3: Create Merge Script

Create `scripts/merge_bullet_optimizations.py` to merge individual bullet optimizations back into base HTML.

**Script Specification:**

```python
#!/usr/bin/env python3
"""
Merge individual bullet optimizations back into base HTML.

Usage:
    python3 scripts/merge_bullet_optimizations.py <base_html> <bullet_check_json> <output_html> <report_json_pattern>

Arguments:
    base_html: Original HTML file path
    bullet_check_json: JSON output from check_bullet_line_widths.py
    output_html: Path to write merged HTML
    report_json_pattern: Glob pattern for bullet report JSONs (e.g., "data/work/09_bullet_report_*_iter0.json")

Logic:
1. Parse base HTML with BeautifulSoup
2. Load bullet_check_json to get problematic bullet locations
3. For each location, find corresponding report JSON file
4. Load report JSON to get optimized_content
5. Find bullet in HTML DOM by location path (e.g., "experience.0.description.2")
6. Replace bullet text with optimized_content
7. Write merged HTML to output_html

Exit codes:
    0: Success
    1: Error (file not found, parsing failed, etc.)
"""
```

**Implementation notes:**
- Use BeautifulSoup to parse/modify HTML
- Location path format: "experience.0.description.2" maps to Experience section → first entry → description → third bullet
- Preserve all HTML structure, only replace bullet text content
- Handle missing report files gracefully (skip that bullet, log warning)

---

### Part 4: Update layout-optimizer.md Documentation

Based on exploration and planning, the following changes are needed to layout-optimizer.md:

---

#### **1. Section Title Change (Line 88)**

**Before:**
```markdown
### 2. Every Line Must Be Full
```

**After:**
```markdown
### 2. Every Bullet Point Must Be Full
```

---

#### **2. Core Requirements (Lines 90-106)**

**Replace entire section with clarified version:**

```markdown
**After optimization, every bullet point must:**
- Fill the available line width with its total character count
- Count TOTAL characters in entire bullet point (before automatic wrapping)
- No half-line whitespace (wasted space)
- Adjust wording to reach optimal character count ranges
- Match calculated character limits from template CSS

**CRITICAL COUNTING RULE**:
When checking bullet point length, count the TOTAL characters in the entire bullet point string, NOT individual visual lines after wrapping. A 120-character bullet point that wraps to two visual lines should be counted as "120 chars total", not "60 + 60 chars per line".

**CRITICAL: Calculate line-width dynamically before optimization:**

1. **Extract chars_per_line from template** (use `_extract_line_width_from_template()` function in scripts/utils.py):
   - Function parses CSS to calculate: container width, padding, font-size, column widths
   - Applies font-specific character width ratios (Times: 0.42, Arial: 0.51, Calibri: 0.49)
   - Returns precise chars_per_line capacity (e.g., 100.2 for kellogg template)

2. **Apply line-width constraints during optimization:**
   - Single-line bullets: **0.9x to 1.0x** chars_per_line (e.g., 90-100 total chars for 100 limit)
   - Double-line bullets: **1.9x to 2.0x** chars_per_line (e.g., 190-200 total chars for 100 limit)
   - Bullet points outside these ranges MUST be reworded to fit
   - NO hardcoded character limits - always use calculated value

   **Important**: Count TOTAL characters in the entire bullet point. A bullet point with 120 total characters that visually wraps to 2 lines should be counted as "120 chars", not "line 1: 60, line 2: 60".
```

---

#### **3. Enhanced Examples (Lines 109-119 - EXPAND)**

**Replace existing example section with:**

```markdown
**Example (assuming chars_per_line = 100):**

**HOW TO COUNT CHARACTERS:**

❌ **WRONG APPROACH** (counting visual lines after wrapping):
```
• Led comprehensive hedge fund analysis initiative working with strategists to
  process CFTC positioning data for clients
```
"Line 1 has 77 chars, line 2 has 43 chars, both are within range" - INCORRECT!

✅ **RIGHT APPROACH** (counting total bullet point length):
```
• Led comprehensive hedge fund analysis initiative working with strategists to process CFTC positioning data for clients
```
"Bullet point total: 120 chars, exceeds single-line limit (100), but doesn't reach double-line minimum (190)" - CORRECT! This means the bullet point needs rewording.

---

**BAD (too short, wastes space):**
```
• Led analysis initiative
```
Total: 30 chars (should be 90-100 for single line)

**BAD (too long, overflows without filling next line):**
```
• Led comprehensive hedge fund analysis initiative working with strategists to process CFTC positioning data for clients
```
Total: 120 chars (too long for single line 100, too short for double line 190-200)

**GOOD (fills single line optimally):**
```
• Led hedge fund analysis initiative, processing CFTC positioning data for institutional clients globally
```
Total: 98 chars (within single-line range 90-100) ✓

**GOOD (fills double line optimally):**
```
• Led comprehensive hedge fund analysis initiative, collaborating with 50+ strategists across Paris, Hong Kong, and London offices to process CFTC positioning data for institutional clients
```
Total: 195 chars (within double-line range 190-200) ✓
```

---

#### **4. Add New Clarification Section (After Line 119)**

**Insert new section:**

```markdown
---

### Understanding Character Counting vs Visual Wrapping

**CRITICAL DISTINCTION:**

1. **Character Counting** (what you do):
   - Count total characters in entire bullet point string: `len(bullet_text)`
   - Example: "This is a very long bullet point that will wrap to multiple lines when rendered in the PDF" = 95 characters TOTAL
   - This is what you check against chars_per_line ranges

2. **Visual Wrapping** (what browser/PDF does automatically):
   - Browser/PDF renderer automatically wraps text when it exceeds line width
   - Example: 95-character string wraps to 2 visual lines (maybe 60 + 35 chars)
   - You do NOT check this - it happens automatically after you count

**YOUR TASK**:
- Count TOTAL characters in bullet point
- Ensure total is in optimal range (0.9x-1.0x or 1.9x-2.0x chars_per_line)
- Browser handles wrapping automatically

**NOT YOUR TASK**:
- Count individual visual lines after wrapping
- Check if "line 1" and "line 2" separately are full
- Worry about where wrapping occurs

---
```

---

#### **5. Workflow Step Update (Lines 196-198)**

**Before:**
```markdown
5. **Ensure every line is full**
   - For all modified lines, adjust wording to fill the line
   - No half-line whitespace
```

**After:**
```markdown
5. **Ensure every bullet point is full**
   - For all modified bullet points, check TOTAL character count
   - Adjust wording to reach optimal ranges (0.9x-1.0x or 1.9x-2.0x chars_per_line)
   - No half-line whitespace (no bullet points that are too short)

   Remember: Count entire bullet point string length, not individual wrapped lines.
```

---

#### **6. Prompt Template - Constraint Section (Lines 241-247)**

**Before:**
```markdown
2. EVERY LINE MUST MATCH CALCULATED CHARACTER LIMITS:
   - Single-line bullets: 0.9x to 1.0x chars_per_line (e.g., 77-85 for 85 limit)
   - Double-line bullets: 1.9x to 2.0x chars_per_line (e.g., 162-170 for 85 limit)
   - Lines outside these ranges MUST be reworded to fit
   - NO bullet point should end with lots of whitespace
   - NO hardcoded character limits - always use calculated chars_per_line
   - Adjust wording to precisely fill the line width
```

**After:**
```markdown
2. EVERY BULLET POINT MUST MATCH CALCULATED CHARACTER LIMITS:
   - Single-line bullets: 0.9x to 1.0x chars_per_line (e.g., 90-100 total chars for 100 limit)
   - Double-line bullets: 1.9x to 2.0x chars_per_line (e.g., 190-200 total chars for 100 limit)
   - Bullet points outside these ranges MUST be reworded to fit
   - NO bullet point should end with lots of whitespace
   - NO hardcoded character limits - always use calculated chars_per_line
   - Adjust wording to reach optimal total character count

   **CHARACTER COUNTING METHOD**: Count TOTAL characters in entire bullet point string (e.g., len(bullet_text)). Do NOT count individual visual lines after wrapping. Example: A 120-character bullet that wraps to 2 visual lines = "120 total chars", not "60 + 60".
```

---

#### **7. Shrink Mode Instructions (Lines 257-260)**

**Before:**
```markdown
4. For EACH modified bullet, check character count:
   - If line is 0.9x-1.0x chars_per_line: single line is full ✓
   - If line is 1.9x-2.0x chars_per_line: double line is full ✓
   - If line is too short or too long: reword to fit optimal range
```

**After:**
```markdown
4. For EACH modified bullet, check TOTAL character count:
   - Count: total_chars = len(bullet_text_content)
   - If total_chars is 0.9x-1.0x chars_per_line: single-line bullet is full ✓
   - If total_chars is 1.9x-2.0x chars_per_line: double-line bullet is full ✓
   - If total_chars is outside these ranges: reword to fit optimal range
   - Do NOT count individual visual lines after wrapping
```

---

#### **8. Expand Mode Instructions (Lines 264-268)**

**Before:**
```markdown
1. Identify short or incomplete bullets
2. For EACH bullet, check if it fills the line (compare to chars_per_line ranges)
3. Add meaningful details (methodology, tools, metrics) to reach optimal ranges
4. Ensure additions are relevant and professional
5. Every line must be 0.9x-1.0x (single) or 1.9x-2.0x (double) chars_per_line
```

**After:**
```markdown
1. Identify short or incomplete bullets
2. For EACH bullet, check TOTAL character count against optimal ranges:
   - Count: total_chars = len(bullet_text_content)
   - Compare to: 0.9x-1.0x chars_per_line (single) or 1.9x-2.0x (double)
3. Add meaningful details (methodology, tools, metrics) to reach optimal ranges
4. Ensure additions are relevant and professional
5. Every bullet point must be 0.9x-1.0x (single) or 1.9x-2.0x (double) chars_per_line total
```

---

## Verification Plan

### Component Testing

**Test 1: check_bullet_line_widths.py script**
```bash
# Test with known HTML file
cd /root/application-assistant
source venv/bin/activate
python3 scripts/check_bullet_line_widths.py data/work/07a_resume_argyll-scott-orchestrade-developer_20260204.html kellogg

# Expected output:
# - chars_per_line: 100.2
# - single_line_range: [90, 100]
# - double_line_range: [190, 200]
# - List of problematic bullets with locations and character counts
```

**Test 2: merge_bullet_optimizations.py script**
```bash
# Create test bullet optimization report
# Run merge script
# Verify output HTML has replaced bullet content
```

**Test 3: layout-optimizer agent (single bullet mode)**
```bash
# Call agent with single bullet prompt
# Verify agent returns optimized content within target range
# Verify agent respects critical_info
```

### Integration Testing

**Test 4: End-to-end /generate workflow with 2-page resume**
```bash
/generate
# Use job: Orchestrade Developer (existing problematic resume)
# Expected:
# - Step 9 detects 8+ problematic bullets
# - Iteration 1: Agents optimize in parallel
# - Iteration 2: Re-check, some bullets may still need work
# - Iteration 3-5: Loop until all bullets optimal
# - Final PDF: 1 page, all bullets within 90-100 or 190-200 char ranges
# - Height ratio: 0.95-1.0
```

**Test 5: Resume with optimal bullets from start**
```bash
/generate
# Use job with well-formatted resume
# Expected:
# - Step 9 detects 0 problematic bullets
# - Loop terminates immediately (iteration 0)
# - No agent calls needed
# - Fast workflow completion
```

### Edge Cases

**Test 6: Bullet in critical_info is problematic**
- Expected: Agent skips bullet, returns "complete" immediately
- Other bullets still optimized

**Test 7: Max iterations reached with some bullets still problematic**
- Expected: Loop terminates at iteration 5
- Fallback to whole-page optimizer
- Best-effort result returned

**Test 8: All bullets too long (shrink scenario)**
- Expected: Agents shrink bullets to 90-100 range
- Overall page height reduces
- Content meaning preserved

**Test 9: All bullets too short (expand scenario)**
- Expected: Agents expand bullets to 90-100 range
- Page height increases
- Meaningful details added

---

## Summary

### Files to Create

1. **scripts/check_bullet_line_widths.py** (~150 lines)
   - Detect problematic bullets by counting TOTAL characters
   - Output JSON with locations, character counts, target actions
   - Uses `_extract_line_width_from_template()` from utils.py

2. **scripts/merge_bullet_optimizations.py** (~120 lines)
   - Merge individual bullet optimizations into base HTML
   - Parse HTML with BeautifulSoup
   - Replace bullet content at specified locations

### Files to Modify

1. **~/.claude/commands/generate.md** (Step 9, lines 458-557)
   - Replace single-pass layout optimization with iterative loop
   - Add bullet detection step (9b.1)
   - Add parallel agent invocation step (9b.2)
   - Add merge step (9b.3)
   - Add loop control (9b.4)
   - Keep fallback whole-page optimizer (9c)

2. **~/.claude/agents/layout-optimizer.md** (8 sections)
   - All "line" → "bullet point" in character count contexts (~15 lines)
   - Add explicit "TOTAL character count" instructions (~100 lines)
   - Add wrong vs right counting examples (section 3)
   - Add clarification section (new section after line 119)
   - Update workflow instructions (sections 5, 6, 7, 8)

### Architecture Benefits

**Why This Design:**
1. **Precision**: Script detects exact bullets that need fixing (no guessing)
2. **Parallelism**: Multiple bullets can be optimized simultaneously (faster)
3. **Iterative**: Loop ensures all bullets eventually reach optimal range
4. **Targeted**: Each agent focuses on one bullet (better results than whole-page optimization)
5. **Reusability**: Uses existing layout-optimizer agent (no new agent needed)
6. **Fallback**: If loop doesn't fix page height, fall back to whole-page optimizer

**Key Principles:**
- Count TOTAL characters in bullet point string, NOT individual visual lines after wrapping
- Script-based detection → Agent-based optimization → Script-based merging
- Loop until all bullets optimal OR max iterations
- Preserve critical_info at all costs
- Parallel agent invocation for speed (up to 5 agents at once)

### Implementation Estimate

**Time Breakdown:**
1. Create check_bullet_line_widths.py: ~2 hours (parse HTML, count chars, classify issues)
2. Create merge_bullet_optimizations.py: ~1.5 hours (BeautifulSoup manipulation)
3. Update generate.md Step 9: ~1 hour (replace workflow logic)
4. Update layout-optimizer.md: ~1 hour (terminology clarification)
5. Testing: ~2 hours (component + integration + edge cases)

**Total: ~7.5 hours**

**Complexity: Medium**
- Script logic straightforward (parse HTML, count chars)
- Workflow modification moderate (replace single-pass with loop)
- Agent prompt adjustment simple (clarify counting method)
- Testing critical (ensure loop terminates, bullets actually improve)

---

## Next Steps

After plan approval:
1. Implement check_bullet_line_widths.py script
2. Implement merge_bullet_optimizations.py script
3. Update generate.md Step 9 with iterative loop
4. Update layout-optimizer.md with clarified terminology
5. Test with existing 2-page resume (Orchestrade Developer job)
6. Verify end-to-end workflow produces 1-page resume with optimal bullet widths
