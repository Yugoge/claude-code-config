<!-- AUTO-GENERATED VIEW for architect | source: docs/dev/specs/spec-20260520-221059.md | extracted: 2026-05-21T00:00:00Z -->

# architect view of spec-20260520-221059

**Monolith**: docs/dev/specs/spec-20260520-221059.md
**Extraction**: content-block level (no section-level mapping)

---

## Role Mandate

> **Pipeline**: ba → dev → qa

# Spec: Unresolved issues backlog from session 88dfdcea — TOP 3 cluster stranded by scope hot-swap + post-session confession

**Pipeline**: ba → dev → qa
**Session**: spec-20260520-221059
**Created**: 2026-05-20T22:10:59Z

## Structural scope (per spec Section 5)

### Layer C — structural item

- **R6** — orphan commit `34210cc` (and now patterns of similar dumps) pollute history with cross-subsystem mega-commits. /dev preflight should block or baseline dirty/orphaned pre-cycle state; baseline ref recorded in final report.

### Layer D — cross-cycle structural pollution

- **D1** — 22 dirty files in working tree from concurrent cycles (`d1e94e` / `75463e-DH` / `085647-d1722b`) plus 1 in `/root` repo (`docs/dev/specs/spec-20260520-051938.md`). At least 3 separate dev cycles ran in recent days and never committed their artifacts.

### Layer E — architectural process gaps

- **E5** — This very spec output is at risk: `docs/dev/specs/spec-20260520-221059.md` lives on tmpfs (`/dev/shm/...`) under a `docs/` subtree with historical gitignore complications. Need to verify (a) it'll actually persist past next reboot, (b) it ships via git.
- **E10** — Session learnings are non-durable. This spec file is the only persistent record of these self-assessments. If file is lost (tmpfs cleared, gitignore matched, ghost cycle pollution), the entire reasoning chain across this session is lost. Need a more durable "session learnings log" architecture.
- **E16** — Conversation transcript not persisted to disk by /spec or anywhere else. The user-orchestrator dialogue across this session lives only in the REPL. If session ends, the reasoning chain is lost. /spec should optionally snapshot key turns into a session-companion file alongside the spec.

### Layer J — structural placement bugs

- **J7** — `agent-scores.json` IS tracked by git. Every score change is part of commit history, cluttering diffs of unrelated work. Move to a non-tracked log + summary tracked file, OR accept the clutter explicitly.

### Layer P — implicit architectural assumptions

- **P1** — `/dev/shm` is the same physical filesystem across session resumes. But it's tmpfs — server reboot or umount wipes the workspace including this spec file. The auto-commit `refs/checkpoints/master` is the only backstop, and J1 shows it's currently corrupted for some paths.
- **P2** — `agent-scores.json` persistence assumed reliable but lives on tmpfs (the whole repo). Score history could vanish on reboot. The score-event log proposed in R9 also lives on the same tmpfs.

### Layer Q — config/system architecture gaps

- **Q4** — `.gitignore` rationale is undocumented. Some `docs/` paths ship (`docs/dev/` re-enabled by d988d4a), others don't (`docs/reference/` blanket-ignored). No explanation of why. New deliverables can't predict which paths will ship.
- **Q6** — `agent-scores.json` IS tracked by git (J7). Every score change adds a diff line, cluttering commits. AND commits show score events from earlier sessions of OTHER agents — the file is a moving target.

