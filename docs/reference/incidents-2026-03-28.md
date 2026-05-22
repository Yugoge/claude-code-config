# Overnight Incident — 2026-03-28

> Full stories behind rules 1–7 in `~/.claude/CLAUDE.md`. The slimmed CLAUDE.md keeps only the one-line rule; this file keeps the reasoning.

---

## Rule 1 — Never weaken checks to "fix" failures

When a validation/check rejects output, the problem is the OUTPUT, not the
check. Fix the upstream code that produces bad output. NEVER: lower
thresholds, swallow exceptions, change error→warning, skip validation. If
the reference implementation passes the same check, the check is correct.

---

## Rule 2 — PM only prioritizes — PM never proposes solutions

PM ranks issues by severity and orders pipelines. PM does NOT suggest
"add component X", "rename Y to Z", or "change layout to W". Solutions are
BA's and Dev's job. Every time PM proposed a solution in overnight, it
was garbage.

---

## Rule 3 — Specialists report symptoms only — no root cause, no fix suggestions

Specialists observe and report what they see. They do NOT analyze why or
suggest how to fix. Root cause analysis is exclusively BA's job. When
architect diagnosed "threshold too strict" instead of "content too short",
the entire fix chain went wrong.

---

## Rule 4 — Always compare with reference implementation BEFORE fixing

When the user says "align with X", every fix must be validated against X's
behavior. The overnight session "fixed" height_ratio by lowering the
threshold to 0.40 while the reference produces 0.98. Nobody checked.

---

## Rule 5 — Output quality > no errors

QA passing means the output is HIGH QUALITY, not just "no exceptions". A
half-empty resume that doesn't crash is still a failed generation.

---

## Rule 6 — Never make "improvements" the user didn't ask for

Overnight added TipsBox to fill empty space (user had deliberately removed
it), renamed a template heading (nobody asked), added features. These are
regressions, not improvements. If the user didn't report it as broken,
don't change it.

---

## Rule 7 — Global agent files must be project-agnostic

Files in `~/.claude/agents/` and `~/.claude/commands/` are used across ALL
projects. Never put project-specific examples (applio, resume,
height_ratio) in global files. Use generic terms.
