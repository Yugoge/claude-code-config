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
/commit <task-id> --repo /path/to/repo --docs-dir /path/to/docs-root
/commit <task-id> --plan                          # A3 dry-run preview
/commit --force -m "<msg>" --manifest <path-to-manifest.json>
/commit --force-rescue -m "<msg>"                  # A2 stage-then-force
```

`-m` is optional for the normal closed-task path. When omitted, the wrapper
builds a Conventional-Commit-style message from the task artifacts and close
verdict. The user and agents do not prepare plan files, choose paths, or
hand-edit commit inputs.

**DOC-1: `--manifest <json>` is an OPTIONAL precision layer.** When omitted in
closed-task mode, the plan is derived from `<task-id>`'s dev-report. When
provided in closed-task or `--force` mode, the plan is derived from the manifest
instead, with the manifest's inline patch becoming the content authority.
Plain `--force -m "msg"` (no manifest, no pre-staged content) is still refused
because force mode has no patch source to draw from. Two legitimate routes
exist: (a) add `--manifest <path>` to use the manifest as the patch authority;
(b) pre-stage content with `git add` and use `--force-rescue` to draw the patch
from the staged delta (DOC-11).

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
- `incompatible_after`: optional non-negative integer (DOC-8 future-major
  schema negotiation; when present, `schema_version > incompatible_after`
  refuses with a specific error)
- `files`: list of repo-relative paths the patch declares it touches
- `semantic_files`: list of `{path, reason}` objects — `{reason}` is required
  for every entry (bare strings rejected per DOC-6 normalization)
- `binary_files`: OPTIONAL list of `{path, blob_sha, size, reason}` objects
  declaring binary blobs to stage via `git update-index --add --cacheinfo`
  after the text patch applies (DOC-4 revised — binary support landed)
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

## Binary patches (DOC-4 — revised)

Inline-patch binary content (`GIT binary patch` blocks inside `manifest.patch`)
remains REJECTED — the unified-diff text is for human-readable hunks only.
Full binary-file commit SUPPORT now lands via the OPTIONAL `manifest.binary_files[]`
schema field:

```json
"binary_files": [
  {
    "path": "assets/logo.png",
    "blob_sha": "1234567890abcdef1234567890abcdef12345678",
    "size": 4096,
    "reason": "logo asset added for splash screen"
  }
]
```

Workflow:

1. Operator pre-runs `git hash-object -w <file>` for each binary so the blob
   exists in the repo's object database.
2. Operator records `path`, `blob_sha` (40-hex lower), `size` (bytes), and
   `reason` in `manifest.binary_files[]`.
3. The wrapper validates the blob exists via `git cat-file -e <sha>` BEFORE
   staging, cross-checks declared `size` against `git cat-file -s <sha>`, and
   stages each entry via `git update-index --add --cacheinfo 100644,<sha>,<path>`
   against the PRIVATE index (the real shared index is never touched).
4. The audit JSON emits both `binary_files` (declared) and
   `binary_files_applied` (actually staged) so downstream forensics can audit
   binary content authority.

The M6 subset assertion expands to `applied_diff ⊆ (manifest.files ∪ manifest.binary_files.path)`
so binary-only paths legitimately appear in the post-apply name list. The
M6 rationale check honors `binary_files[].reason` so binary entries do not
need a duplicate `semantic_files[]` row.

## Schema future-major negotiation (DOC-8)

`manifest.incompatible_after` is an OPTIONAL non-negative integer signalling
the highest `schema_version` THIS wrapper understands. When the manifest
author publishes a NEWER manifest format that this wrapper cannot apply, they
set `schema_version` to the new value AND set `incompatible_after` to the
last wrapper-compatible version. If the running wrapper sees
`schema_version > incompatible_after`, it refuses with:

```
commit.sh: manifest.schema_version=<v> exceeds incompatible_after=<i>; this wrapper cannot apply
```

When `incompatible_after` is absent (current default for all manifests), no
check fires and behaviour is identical to pre-B2.

## CLI routing precedence (DOC-9)

`--repo <path>` and `--docs-dir <path>` are explicit CLI overrides for the
target repository and the docs-root used for artifact lookup. Resolution
priority, highest-first:

1. `--docs-dir <path>` (explicit; routes ONLY `DOCS_DIR_ROOT`)
2. `--repo <path>` (explicit; sets `DOCS_DIR_ROOT` to `<repo>` when
   `--docs-dir` is not also given; also routes manifest-mode repo resolution)
3. `$CLAUDE_DOCS_DIR` env var
4. `$CLAUDE_PROJECT_DIR` env var (back-compat)
5. cwd-toplevel (`git rev-parse --show-toplevel` from current working dir)
6. `pwd`
7. `/root` (legacy harness-root safety net)

Use `--repo /path/to/code-repo --docs-dir /path/to/docs-root` when the source
tree and the docs tree live in different repositories (the common cross-repo
asymmetry).

## `--plan` dry-run (DOC-10)

`--plan` is a side-effect-zero preview flag. When present, the wrapper:

- Parses argv, validates closure (for closed-task mode), builds the semantic
  plan (or manifest plan), validates path classification.
- Prints the resolved plan as a structured `PLAN: ... EXIT: dry-run` stdout
  block listing `task_id`, `mode`, `message_source`, `message_preview`,
  `patch_source`, `files_planned`, `binary_files_planned`, `manifest_active`,
  `repo_root`, `expected_parent`.
- Does NOT apply the patch, write the audit JSON, advance the branch, queue
  the backup ref, or mutate the real index.
- Verifies the post-run `staged_list_before == staged_list_after` invariant
  (refuses with exit 2 if violated).
- Exits 0 on success.

Use `--plan` to preview a manifest commit before landing it, or to validate
that the wrapper would route to the expected repo / target when crossed
flags interact (`--repo` + `--docs-dir` + `--manifest`).

## `--force-rescue` stage-then-force (DOC-11)

`--force-rescue` is the alias for `--force` that authorizes the
**stage-then-force** patch-source model:

```bash
# 1. Operator pre-stages content explicitly.
git add <files>
# 2. Wrapper reads the staged delta as the commit's content authority.
commit.sh --force-rescue -m "msg describing the staged delta"
```

Semantics:

- Wrapper refuses with `commit.sh: force-rescue requires pre-staged content
  via 'git add'` when `git diff --cached --name-only` is empty.
- Patch source = `git diff --cached --binary HEAD --`; no manifest required.
- Closure, task-id binding, and dev-report binding are SKIPPED (mirrors the
  `--force --manifest` policy — force mode does not bind task identity).
- All post-apply safety remains engaged: `real_index_fingerprint` before/after,
  `staged_files_before/after`, backup ref via `refs/backups/claude/...`,
  expected-parent CAS branch advance, and the four always-on layers.
- The audit emits `mode="force-rescue"` (DOC-12) so log filtering can
  distinguish from plain `--force` and `--force --manifest`.

`--force-rescue` and `--manifest` are mutually exclusive (the patch source must
come from exactly one authority — either the staged set or the manifest).

## `--force-rescue` audit field (DOC-12)

The audit JSON for `--force-rescue` invocations carries `"mode": "force-rescue"`
and `"engine": "force-rescue-commit"` (a dedicated engine label so log
filtering can distinguish stage-then-force commits from both the semantic
dev-report path `"semantic-commit"` and the manifest path `"manifest-commit"`).
Downstream log filtering can SELECT `mode == "force-rescue"` or
`engine == "force-rescue-commit"` to enumerate stage-then-force commits
without parsing the audit body.

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

- `applied_diff ⊆ (manifest.files ∪ manifest.binary_files[].path)` — extras
  refuse with a specific error naming the undeclared path. Binary entries
  appear in the post-apply diff via the `git update-index --add --cacheinfo`
  path described in DOC-4; their paths are unioned with `manifest.files` for
  the subset check.
- `applied_diff ⊆ (manifest.semantic_files[].path ∪ manifest.binary_files[].path)`
  — every applied path needs an ownership rationale. A `semantic_files[].reason`
  satisfies the rule for text patches; a `binary_files[].reason` satisfies the
  rule for binary entries (no duplicate `semantic_files[]` row needed).

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

## Recovery (DOC-13)

When the private-index apply chain fails mid-step, the wrapper preserves the
real shared index and the operator's dirty work. The recovery sequence:

1. **Which fingerprint guards fire**: the wrapper computes
   `real_index_fingerprint_before` immediately before reading the expected
   parent into the private index, and again after applying the patch chain.
   A mismatch refuses branch advance with `refusing branch advance` and
   discards the private index. The same fingerprint check fires AGAIN
   right before the expected-parent CAS so a concurrent shared-index
   mutation cannot slip in between apply and ref-update.

2. **Which backup ref to use**: every successful commit writes a backup-only
   recovery ref at `refs/backups/claude/<branch>/<head-short-prefix>` (or
   `refs/backups/claude/detached/<short>` when the branch name fails
   `git check-ref-format`). Push to remote (when configured) ALSO targets
   that ref. To inspect or recover from the backup:

   ```bash
   git show refs/backups/claude/<branch>/<short>
   git update-ref refs/heads/<branch> refs/backups/claude/<branch>/<short>
   ```

3. **How to recover without losing dirty work**: the wrapper NEVER modifies
   the real shared index during private-index preparation. If apply fails:
   - The temporary dir (private index, patch file, meta file) is removed.
   - The real shared index is untouched (verified by the fingerprint guard).
   - Operator's dirty / staged / unstaged work is preserved as-is.
   - Operator can re-stage or re-author the manifest and retry.

4. **Cleanup order on failure**: (a) discard the private index by removing
   the temp dir, (b) leave the real shared index untouched, (c) leave the
   branch ref untouched (CAS never executed), (d) leave the grant file in
   place (nonce-bound, single-use — operator can retry safely).

When the synchronous backup push fails under `CLAUDE_BACKUP_REMOTE_REQUIRED=1`,
the wrapper exits 2 AFTER the commit object has been created and the branch
has been advanced. Recovery: `git push <remote> refs/heads/<branch>` manually,
or inspect `${CLAUDE_LOG_DIR}/post-commit-auto-push.log` for the failure
reason and retry the push.

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
