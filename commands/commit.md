---
description: Commit closed dev task to branch HEAD
disable-model-invocation: true
---

# /commit — Automatic Semantic Commit

`/commit <task-id>` is the human-triggered wrapper for a closed development
cycle. The wrapper derives an internal semantic plan from same-task artifacts and
live repository state, commits only task-owned changes through a private index,
and preserves unrelated work.

## Usage

```bash
/commit <task-id>
/commit <task-id> -m "optional semantic summary"
/commit <task-id> --manifest <path-to-manifest.json>
/commit --force -m "<msg>" --manifest <path-to-manifest.json>
```

`-m` is optional for the normal closed-task path. When omitted, the wrapper
builds a Conventional-Commit-style message from the task artifacts and close
verdict. The user and agents do not prepare plan files, choose paths, or
hand-edit commit inputs.

**DOC-1: `--manifest <json>` is an OPTIONAL precision layer.** When omitted in
closed-task mode, the plan is derived from `<task-id>`'s dev-report. When
provided in closed-task or `--force` mode, the plan is derived from the manifest
instead, with the manifest's inline patch becoming the content authority.
Force-mode WITHOUT `--manifest` is currently out of scope — the wrapper refuses
plain `--force -m "msg"` because force mode has no patch source to draw from;
add `--manifest` to use the irregular-path escape hatch.

## Inputs the wrapper reads

For the supplied `<task-id>`, the wrapper resolves `docs/dev/` using the
project-local-first lookup and reads same-task artifacts when present:

1. `close-report-<task-id>.md`
2. `dev-report-<task-id>.json`
3. `qa-report-<task-id>.json`
4. `completion-<task-id>.md`
5. `context-<task-id>.json`
6. `ticket-<task-id>.md` or legacy BA spec

Those artifacts are evidence only; commit content is derived from the target
repository's current dirty state and task ownership signals in the artifacts.

## Manifest schema (DOC-2)

When `--manifest <path>` is supplied, the manifest JSON MUST declare:

- `schema_name`: string literal `"commit-manifest"`
- `schema_version`: integer `3` (string aliases such as `"v3"` or
  `"commit-intent-v3"` are rejected with a specific error naming the field)
- `schema_minor`: optional integer (defaults to `0`)
- `files`: list of repo-relative paths the patch declares it touches
- `semantic_files`: list of `{path, reason}` objects — `{reason}` is required
  for every entry (bare strings rejected per DOC-6 normalization)
- `patch`: non-empty inline unified-diff string (no external patch path)
- `base_commit`: optional 40-char SHA; if present must equal the current
  resolved branch HEAD
- `task_id`: optional string; when present in closed-task mode it must equal
  the wrapper's `<task-id>` argument
- `repo_root`: recorded in audit but ignored for repo resolution (DOC-6
  rationale-only; path B per-session worktree is the spatial boundary)

Example:

```json
{
  "schema_name": "commit-manifest",
  "schema_version": 3,
  "schema_minor": 0,
  "task_id": "20260510-191533",
  "base_commit": "109c700637824dd11a0f160c84ef042f7fc49005",
  "files": ["hooks/commit.sh", "commands/commit.md"],
  "semantic_files": [
    {"path": "hooks/commit.sh", "reason": "restore manifest seam"},
    {"path": "commands/commit.md", "reason": "DOC-1..DOC-7 co-update"}
  ],
  "patch": "diff --git a/hooks/commit.sh b/hooks/commit.sh\n..."
}
```

## Task-id binding rules (DOC-3)

In closed-task mode with `--manifest`:

- If `manifest.task_id` is present, it MUST equal the wrapper-arg `<task-id>`;
  mismatch refuses the commit.
- The dev-report `task_id` binding rule (cross-checked when the dev-report is
  present and parseable) continues to apply alongside the manifest binding.
- Force mode (`--force --manifest`) does NOT bind `task_id` — see DOC-1 and
  the `is_other_session` rule below.

When `--force --manifest` is used:

- If `manifest.task_id` is present, cross-task `docs/dev/<task-id>` artifacts
  in the applied patch are refused (`is_other_session` enforced).
- If `manifest.task_id` is absent, the `is_other_session` filter is SKIPPED
  for this path (without a bound task identity, the filter would
  mis-classify all `docs/dev/` artifacts).

## Binary patches (DOC-4)

The manifest path REJECTS binary patches at parse time (anchored line match
`^GIT binary patch$`). Full binary-file commit SUPPORT is deferred to a
separate cycle; this slice rejects the patch and returns exit 2 with a
specific error.

## Operator escape hatch (DOC-5)

`CLAUDE_COMMIT_MANIFEST_DISABLED=1` set in the environment AND `--manifest`
specified on the same invocation → wrapper fails closed at argv-parse with
the exact error:

```
commit.sh: manifest path disabled by operator (CLAUDE_COMMIT_MANIFEST_DISABLED=1)
```

The env var does NOT gate the closed-task dev-report path (i.e., `/commit
<task-id>` without `--manifest` still succeeds under
`CLAUDE_COMMIT_MANIFEST_DISABLED=1`). It also does NOT gate the 4 always-on
safety layers (`disable-model-invocation: true` here, the inline-env literal
rejection in privilege-guard, bulk-commit-detector, and grant emission).

## `manifest.files` is rationale only (DOC-6)

`manifest.files` is a DECLARATION list — it states which files the manifest
author intends to commit. The actual content authority is the post-apply
private-index diff. The wrapper asserts:

- `applied_diff ⊆ manifest.files` (extras refuse with a specific error
  naming the undeclared path); and
- `applied_diff ⊆ manifest.semantic_files` (existing dev-report-path rule
  reused — every applied path needs a `semantic_files[].reason`).

If the patch modifies fewer paths than `manifest.files` declares, the audit
records the actually-applied subset and the commit succeeds (sub-set is the
normal case, e.g., the manifest pre-declares 5 paths but only 3 had hunks).

## Behavior summary

1. Parse `<task-id>` and echo `TASK-ID: <task-id>`.
2. Require closure evidence: PRIMARY close-report with a recognized `CLOSE: YES`
   verdict, or SECONDARY completion plus passing QA evidence.
3. Treat `CLOSE: NO` as authoritative and fail closed.
4. Build an internal semantic plan that classifies dirty candidates as
   `task_owned`, `unrelated`, `garbage/generated`, `other_session`, or
   `ambiguous_overlap`. When `--manifest` is supplied, the plan instead comes
   from the manifest's inline patch (hardened per DOC-2 + DOC-6).
5. Include only `task_owned` changes. Preserve unrelated and other-session work.
6. Refuse ambiguous ownership, mixed planned-path overlap, detached HEAD, empty
   plan, cross-repo ambiguity, or conflict.
7. Seed a private index from the expected parent and apply only planned patches.
8. Verify the real shared index did not mutate during private-index preparation.
9. Create the commit object from the private-index tree.
10. Advance the branch with expected-parent compare-and-swap.
11. Reconcile only planned paths in the shared index and verify staged-file list
    preservation.
12. Write audit JSON/log records and a backup-only recovery ref under
    `refs/backups/claude/...`. Manifest-mode audit emits `engine="manifest-commit"`
    plus `schema_name`, `schema_version` (integer), `schema_minor`,
    `manifest_path`, `manifest_sha256`, and related descriptors; the pre-fe9c0f2
    legacy magic-string version field is no longer emitted.

## Safety contract

- Direct low-level commits remain blocked in agent context; use this wrapper.
- The shared index is never the content authority for closed-task commits.
- The wrapper refuses planned paths that are already staged by another session.
- The branch moves only through expected-parent CAS.
- Automatic recovery uses backup-only refs and never background-publishes
  `refs/heads/<branch>`.
- `--auto-bulk-bridge` remains a separate end-of-cycle path with its fixed
  `auto-bulk: end-of-cycle commit for <branch>` message. `--auto-bulk-bridge`
  and `--manifest` are mutually exclusive (bridge mode's content authority is
  the pre-staged shared index; a manifest patch source would conflict).

## Exit codes

| Exit | Meaning |
|------|---------|
| 0    | Commit created and backup ref queued |
| 1    | Underlying git operation failed unexpectedly |
| 2    | Closure, ownership, overlap, conflict, manifest schema/hygiene, or safety refusal |

## Related

- `/close` writes the machine-readable `CLOSE:` verdict consumed here.
- `/push` publishes committed branch tips only; it does not create commits.
