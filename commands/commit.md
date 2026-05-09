---
description: Commit closed dev task to branch HEAD
disable-model-invocation: true
---

# /commit — v3 Semantic Manifest Commit

`/commit` is the only agent-authorized path, outside `/merge`, that advances
the current branch. V3 changes commit authority from the shared real index,
pre-staged files, and dev-report file lists to an agent-authored semantic intent
manifest containing patch bundles or hunks.

## Usage

```bash
/commit <task-id> -m "<session-summary>"
/commit --force -m "<session-summary>"
```

The user does not stage files, choose files, pick hunks, or provide a manifest
path. After user intent, the agent creates the semantic manifest automatically
from the completed session intent, writes it to the internal v3 manifest location,
and invokes `commit.sh`; manual selection questions are forbidden.
`commit.sh` auto-locates the agent artifact via `CLAUDE_COMMIT_MANIFEST`,
`/tmp/claude-commit-manifest-<sid>-<task-id>.json`, or
`docs/dev/commit-manifest-<task-id>.json`.

## V3 manifest contract

The manifest is JSON with `version: 3` (or `schema_version: "v3"`) and inline
patch content:

```json
{
  "version": 3,
  "task_id": "20260509-154133",
  "repo_root": "/path/to/repo",
  "base_commit": "<optional-base-sha>",
  "semantic_files": [
    {"path": "src/app.ts", "reason": "task-owned implementation change"}
  ],
  "patches": [
    {"patch": "diff --git ..."}
  ],
  "excluded_dirty": [
    {"path": "scratch.log", "reason": "debug output, not task intent"}
  ]
}
```

Accepted patch containers are top-level `patch`, `diff`, or `bundle` strings,
or arrays named `patches`, `patch_bundles`, or `hunks` whose entries contain
inline `patch`/`diff` text. `semantic_files` entries must be objects with a
path and semantic ownership rationale. `excluded_dirty` entries, when present,
must be objects with a path and exclusion rationale. External patch paths,
unexplained string-only file/exclusion entries, and Git binary patches fail
closed in this first slice.

## Commit algorithm

1. Validate closed-task admission first: PRIMARY `close-report-<task-id>.md`
   ending in `CLOSE: YES`, or SECONDARY completion + passing QA evidence.
2. Locate the agent-created v3 manifest from the internal path and write a
   temporary patch bundle.
3. Resolve the target repository from `manifest.repo_root`, `CLAUDE_PROJECT_DIR`,
   or the current working directory.
4. Record the real shared index fingerprint and user-visible staged-file list.
5. Create a temporary private index and seed it from the current branch tip.
6. Apply only manifest-declared patches to that private index.
7. Run a private-index diff check and create the commit object.
8. Fail closed if any manifest path is already staged in the shared index.
9. Advance `refs/heads/<branch>` with expected-parent compare-and-swap.
10. Reconcile only manifest paths in the shared index to the new commit so
    unrelated staged entries are preserved and no reverse manifest diff appears.
11. Verify the user-visible staged-file list matches the pre-commit list.
12. Create a local recovery ref and start a backup-only push to
    `refs/backups/claude/<branch>/<short-sha>`.
13. Write v3 audit JSON under `/root/.claude/logs/` and append
    `git-privilege-grants.log`.

The commit object is never built from `git diff --cached`, user staging, or
`dev-report.files_modified`. Dev reports remain closure/audit evidence only.

## Concurrency behavior

- Same-file disjoint hunks can commit sequentially: the later manifest is
  applied with three-way patch semantics against the new branch tip, then the
  branch advances by CAS. The wrapper updates only manifest paths in the shared
  index so unrelated staged entries remain staged and the manifest path does not
  appear as a staged reverse diff.
- If any manifest path is already staged before the v3 commit, the wrapper fails
  closed because another session owns staged content for that path.
- Overlapping hunks fail closed with a conflict/overlap message. The wrapper
  does not reset, clean, unstage, or otherwise destructively repair the worktree.
- If the branch moves between parent capture and CAS, the wrapper refuses the
  branch advance and asks the agent to retry against the new HEAD.

## Force mode

`--force` is still an irregular-path admission mode, but it no longer trusts
pre-staged files. It requires the same v3 manifest and private-index/CAS commit
path as closed-task mode, while skipping closure checks and recording
`task_id="__force__"` in audit output.

## Backup contract

Automatic post-commit backup is recovery-only. It pushes commit objects only to
namespaced recovery refs such as:

```text
refs/backups/claude/<branch>/<short-sha>
```

It must not publish `refs/heads/<branch>` in the background. Human branch
publication remains `/push`.

## Out of scope

- Per-session independent worktrees.
- Manual staging, manual file selection, or manual hunk selection.
- Dev-report file lists as commit content authority.
- Binary patch ownership in this first slice.
- Force/delete/ref-rewrite push flows.
