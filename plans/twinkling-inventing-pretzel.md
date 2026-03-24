# Plan: Fix CL Agents — Story-Driven, Not Technical Listing

## Context

The cover letter pipeline produces output that reads like a resume with causal connectives — metric-heavy technical achievement lists disguised as narratives. The user has repeatedly requested story-driven CLs, but the agent instructions contain deep contradictions that make this impossible.

**Root Cause** (git analysis: commits 9e5c2ab → a5e7a62, Mar 10-11):
Iterative improvements added constraints that collectively force metrics as the ONLY way to demonstrate "specificity":
1. Specificity test says: "Replace 'significant gains' → the metric"
2. No third-party names rule removes framework names as depth signals
3. Technical term cap (3/paragraph) limits domain vocabulary
4. Designer's `metrics_focus` field amplifies quantification
5. No instruction distinguishing CL tone from resume tone

**Result**: Every paragraph becomes "When X problem existed, I built Y achieving Z% improvement" — a resume bullet with a subordinate clause.

---

## Fix Strategy: 3 Layers of Change

### Layer 1: Rewrite Specificity Test Across All Agents (Core Fix)

**Files**: All 5 CL agents

Replace the current Specificity test (Test #3) in the Engaging Story Rule. The current version:
```
"Significant gains" → the metric. "The system" → its name.
```

New version — specificity through **sensory/experiential detail**, not numbers:
```
3. **Specificity** — Is every noun grounded in lived experience?
   Replace generic phrases with concrete details the candidate actually saw, touched, or built.
   "The system" → its name. "Significant gains" → what changed in the team's daily reality.
   "Derivatives work" → the specific instrument.

   Specificity comes from DETAIL, not NUMBERS.
   - BAD: "reduced processing time by 60%"
   - GOOD: "what used to take the team until 7pm now finished before lunch"
   - BAD: "improved accuracy to 90%"
   - GOOD: "the model's forecasts became reliable enough that traders started trusting them for live decisions"

   Numbers belong in resumes. In a cover letter, show the HUMAN IMPACT.
```

**Exact locations to modify**:
- `cl-story-professional.md` line ~214
- `cl-story-project.md` line ~169
- (Propagate to education and skills if present)

### Layer 2: Add Explicit CL-vs-Resume Tone Distinction + Number Ban

**Files**: All 5 CL agents (add new section)

Add a new top-level rule block to each agent:

```markdown
### Cover Letter ≠ Resume (CRITICAL DISTINCTION)

A resume LISTS achievements with metrics. A cover letter TELLS A STORY about who you are.

**BANNED in cover letters**:
- Standalone percentages: "60%", "3.64 GPA", "99.9% uptime"
- Data scale flexing: "300K+ data points", "10M events/day"
- Business metrics as proof: "$2M savings", "15% efficiency gain"
- ANY number used as the primary evidence of competence

**REQUIRED instead**:
- What problem kept you up at night?
- What did you NOTICE that others missed?
- What did you CHOOSE to do differently, and why?
- What did that experience TEACH you about yourself?
- How did that shape how you think about [this role's domain]?

A reader should finish your CL thinking "I want to meet this person" — not "impressive metrics."
```

### Layer 3: Fix Designer's metrics_focus + Professional's "Weak metrics" Refinement

**File**: `cl-designer.md`
- Remove `metrics_focus` from section guidance schema
- Replace with `story_angle`: what narrative thread should this section pursue?
- Example: instead of `"metrics_focus": ["Accuracy improvements"]`, use `"story_angle": "What problem did this project solve and what did the candidate learn about approaching ambiguous data?"`

**File**: `cl-story-professional.md`
- Remove "Weak metrics → Strengthen quantification" from refinement patterns (line ~296)
- Replace with "Generic achievement → Deepen the story: what was the candidate's specific insight, choice, or learning?"

**File**: `cl-story-project.md`
- Remove "Performance metrics" from "What to emphasize for technical roles" (line ~245)
- Replace with "Problem-solving narrative: what was broken, what did you try, what surprised you?"

---

## Detailed File-by-File Changes

### 1. `cl-designer.md`
- Replace `metrics_focus` field with `story_angle` in section guidance schema
- Update the example JSON output to show `story_angle` instead of `metrics_focus`
- Add "Cover Letter ≠ Resume" rule to the designer's quality constraints

### 2. `cl-story-skills.md`
- Add "Cover Letter ≠ Resume" rule block
- Verify no metric-encouraging instructions exist

### 3. `cl-story-education.md`
- Add "Cover Letter ≠ Resume" rule block
- Already has good anti-enumeration rule (keep)
- Update Specificity test if present

### 4. `cl-story-project.md`
- Add "Cover Letter ≠ Resume" rule block
- Rewrite Specificity test (Test #3) — sensory detail not numbers
- Remove "Performance metrics" from technical role emphasis
- Update example paragraphs to be story-driven without numbers

### 5. `cl-story-professional.md`
- Add "Cover Letter ≠ Resume" rule block
- Rewrite Specificity test (Test #3) — sensory detail not numbers
- Remove "Weak metrics → Strengthen quantification" from refinement patterns
- Update example paragraphs to be story-driven without numbers
- Strengthen the "Motivation signal" rule with examples

---

## Examples of Before/After

**Before** (current output):
> To test whether factor models survived real frictions, I built a backtesting framework on 300K+ data points targeting momentum and value signals. When one segment's 3% annualized outperformance seemed too clean, I investigated rather than accepted, uncovering survivorship bias inflating returns by roughly 80 basis points.

**After** (target output):
> When my backtesting results looked too clean, I felt the itch that something was off. Rather than presenting polished numbers to my professor, I spent a week re-examining my data pipeline and discovered that survivorship bias had been quietly flattering every signal I tested. That moment of choosing skepticism over convenience shaped how I approach any model output today: the first question is always "what am I not seeing?"

---

## Verification

1. After modifying all 5 agent files, run the CL pipeline on an existing job to produce a new CL
2. Check the output for:
   - Zero standalone numbers/percentages/metrics
   - Each paragraph tells a genuine story with personal insight
   - Reader feels they know the PERSON, not just their achievements
   - Causal arc structure is preserved (challenge → insight → consequence)
   - Company-specific angle is present without metrics
3. Compare word count stays within 280-315 target
