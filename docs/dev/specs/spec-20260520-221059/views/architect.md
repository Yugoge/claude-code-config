<!-- AUTO-GENERATED VIEW for architect | source: docs/dev/specs/spec-20260520-221059.md | extracted: 2026-05-21T00:00:00Z -->

# architect view of spec-20260520-221059

**Monolith**: docs/dev/specs/spec-20260520-221059.md
**Extraction**: content-block level (no section-level mapping)

---

# Spec: Unresolved issues backlog from session 88dfdcea — TOP 3 cluster stranded by scope hot-swap + post-session confession

**Pipeline**: ba → dev → qa
**Session**: spec-20260520-221059
**Created**: 2026-05-20T22:10:59Z

## Section 5: User's Acceptance Criterion

> 将你说的问题全部保存为新的spec

### Layer C — 17-item meta-assessment of cycle 20260519-161035, the OTHER 9 always-known deferred items

- **R6** — orphan commit `34210cc` (and now patterns of similar dumps) pollute history with cross-subsystem mega-commits. /dev preflight should block or baseline dirty/orphaned pre-cycle state; baseline ref recorded in final report.

### Layer D — minor residual debt from THIS session's own deliverables and cross-cycle pollution

- **D1** — 22 dirty files in working tree from concurrent cycles (`d1e94e` / `75463e-DH` / `085647-d1722b`) plus 1 in `/root` repo (`docs/dev/specs/spec-20260520-051938.md`). At least 3 separate dev cycles ran in recent days and never committed their artifacts.
- **D3** — `docs/reference/tmp-cleanup-convention.md` (L3 deliverable from cycle 161035) is still gitignored. AC8 verified existence on local disk; fresh clones get nothing. Add a `.gitignore` exception OR move file to a non-ignored path.
- **D4** — `/tmp/update-FgI2V5.md` and `/tmp/update-wflOHq.md` lingering temp `/spec-continue --temp` files. They have no consumers after their respective /commit runs; will be swept by tmp-cleanup at >7d but currently occupying tmpfs.
- **D5** — Duplicate sibling file `docs/dev/prompt-inspector-report-20260519-211515-redev9items.json` left over from the write-guard workaround pattern (write to sibling → cp over canonical). Should be deduplicated.

### Layer E — orchestrator-process gaps (meta-level, beyond specific tool fixes)

- **E5** — This very spec output is at risk: `docs/dev/specs/spec-20260520-221059.md` lives on tmpfs (`/dev/shm/...`) under a `docs/` subtree with historical gitignore complications. Need to verify (a) it'll actually persist past next reboot, (b) it ships via git.
- **E10** — Session learnings are non-durable. This spec file is the only persistent record of these self-assessments. If file is lost (tmpfs cleared, gitignore matched, ghost cycle pollution), the entire reasoning chain across this session is lost. Need a more durable "session learnings log" architecture.
- **E16** — Conversation transcript not persisted to disk by /spec or anywhere else. The user-orchestrator dialogue across this session lives only in the REPL. If session ends, the reasoning chain is lost. /spec should optionally snapshot key turns into a session-companion file alongside the spec.

### Layer J — known-but-uncommunicated production bugs

- **J3** — L2 cleanup script `/usr/local/sbin/tmp-cleanup.sh` is in NO repo. If host filesystem is wiped or reinstalled, 12KB of cleanup logic vanishes. R2's install-manifest IS the fix, but the urgent failure mode is real today. The script needs a mirror in-repo at `scripts/install/` even before R2's automated gate lands.
- **J7** — `agent-scores.json` IS tracked by git. Every score change is part of commit history, cluttering diffs of unrelated work. Move to a non-tracked log + summary tracked file, OR accept the clutter explicitly.

### Layer P — implicit architectural assumptions

- **P1** — `/dev/shm` is the same physical filesystem across session resumes. But it's tmpfs — server reboot or umount wipes the workspace including this spec file. The auto-commit `refs/checkpoints/master` is the only backstop, and J1 shows it's currently corrupted for some paths.
- **P2** — `agent-scores.json` persistence assumed reliable but lives on tmpfs (the whole repo). Score history could vanish on reboot. The score-event log proposed in R9 also lives on the same tmpfs.

### Layer Q — hook/policy/config system gaps

- **Q4** — `.gitignore` rationale is undocumented. Some `docs/` paths ship (`docs/dev/` re-enabled by d988d4a), others don't (`docs/reference/` blanket-ignored). No explanation of why. New deliverables can't predict which paths will ship.
- **Q6** — `agent-scores.json` IS tracked by git (J7). Every score change adds a diff line, cluttering commits. AND commits show score events from earlier sessions of OTHER agents — the file is a moving target.

### Layer M — preferences and memory that ought to be durable

- **M3** — Multiple "ghost cycle" task-id slot collisions are now known: `20260519-211515` had 3 scopes; `spec-20260518-225715` mascot scoring also adopted the same slot for D+H. **How many MORE task-id slots have undiscovered ghost pollution?** No systematic survey done.
- **M4** — The 10-item retrospective from cycle 175339 (source of the 9-item shipped scope) — the orchestrator never verified `qa-output-retrospective-classification-20260519-175339.json` ACTUALLY contains 10 items. Could be more. Could be miscategorized. Trust-but-verify never applied to the retrospective source.

### Layer U — meta-observations on this very accumulation

- **U3** — This spec file IS the durable record of all of the above. If THIS spec is lost (gitignore, ghost pollution, reboot, /spec misconfig), this entire reasoning cascade is gone. Recursive concern: the artifact preserving the "fragility of artifacts" lessons is itself fragile.

## Scope and constraints inherited (binding)

- DO NOT modify shipped artifacts already on `origin/master` (commits `6cd997b`, `34210cc`, `8d74e83`, `d988d4a`, `6d28883`, `28a1e85`, `23184c9`, `97585ca`, `4d9f9f5`)
- DO NOT modify frozen continuation spec `docs/dev/specs/spec-20260520-044700.md`
- Future cycles addressing these issues MUST land deliverables at non-gitignored paths (do not repeat the L3 mistake)
- All new scripts use `#!/usr/bin/env bash` or `#!/usr/bin/env python3`; chmod +x
- Lifecycle log location (when R9 lands) MUST be `logs/lifecycle.jsonl` (in-repo; add `.gitignore` exception if `logs/` is currently ignored)

