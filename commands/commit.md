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

## Hash chain trailer (DOC-14)

Every closed-task or `--force` commit appends a hash-chain trailer paragraph
to the commit message body. Six audit tokens are emitted in task-flow order
(omitted when the corresponding artifact is absent on disk):

```
Ticket-SHA256: <64-hex>
Context-SHA256: <64-hex>
Dev-Report-SHA256: <64-hex>
QA-Report-SHA256: <64-hex>
Close-Report-SHA256: <64-hex>
Completion-SHA256: <64-hex>
```

Hash source: the raw bytes of each artifact file ON DISK at `git commit-tree`
time. The wrapper hashes the worktree file the agents authored, not the
tree-blob; this is the desired audit property — verifiers detect post-commit
tampering by reading the worktree file and rehashing.

**Verifier contract**: Verifiers MUST rehash the live artifact files on disk
(e.g., `sha256sum docs/dev/qa-report-<task-id>.json`), NOT the tree-blob (e.g.,
`git show <commit>:docs/dev/qa-report-<task-id>.json`). The two values diverge
when the worktree file is mutated after `git commit-tree`; the trailer always
reflects the file-on-disk-at-commit-tree-time bytes (per M1's hash source
contract, ticket §M1).

Format guarantees:

- The trailer paragraph is the FINAL paragraph of the message body, separated
  from preceding text by exactly ONE blank line.
- There are ZERO blank lines BETWEEN trailer entries.
- Token names use Title-Case-Hyphenated form per RFC-822 trailer conventions
  (`Ticket-SHA256`, `Context-SHA256`, `Dev-Report-SHA256`, `QA-Report-SHA256`,
  `Close-Report-SHA256`, `Completion-SHA256`).
- Values are 64-hex lowercase SHA-256 digests.

Idempotency: re-runs with an unchanged artifact set produce identical trailer
blocks. The wrapper pre-strips ALL pre-existing 6-audit-token lines from the
message body (canonical POSIX regex
`^(Ticket|Context|Dev-Report|QA-Report|Close-Report|Completion)-SHA256:[[:space:]]*`)
BEFORE invoking `git interpret-trailers --in-place --if-exists replace
--if-missing add`. The pre-strip + replace combination guarantees
exactly-one-per-token regardless of pre-existing duplicates.

Audit JSON mirror: the audit JSON's `artifact_sha256` field is a
`{<basename>: <digest>}` map that mirrors the trailer block byte-for-byte.
Cross-verification between trailers and audit JSON is possible without
parsing the commit message.

Missing artifacts: when an artifact does NOT exist on disk at commit-tree time,
the corresponding trailer is OMITTED (not zeroed); the `artifact_sha256` map
likewise omits the key.

Bridge mode (`--auto-bulk-bridge`): the bridge commit message is byte-identical
to the existing BLESSED_BRIDGE_RE format (no trailers, no blank-line separator).
The hash-chain trailer is a true no-op in bridge mode.

Operator override: `CLAUDE_COMMIT_SKIP_HASH_TRAILERS=1` disables trailer
emission entirely (the audit JSON still records `artifact_sha256` for
forensic value).

Known constraint: downstream tools that use
`git log --format=%(trailers:key=Ticket-SHA256)` rely on the trailer paragraph
being the FINAL paragraph of the message body. If a future operator pastes
prose AFTER the trailer block, git's trailer parser will not see the audit
trailers. This is a git-trailer constraint, not a defect of M1.

## Message-vs-evidence guard (DOC-15)

When the operator/agent supplies `-m "<message>"` for a closed-task commit
(`MESSAGE_SOURCE == "caller"`), the wrapper scans the FULL commit message
(subject + body) for verification-claim phrases and refuses the commit if
the claim is not backed by `qa-report-<task-id>.json`.

**Caller-only scope (OBJ-4)**: M2 fires ONLY on `MESSAGE_SOURCE == "caller"`.
Auto-generated messages from `auto-commit-message.sh` are deterministic and
cannot LLM-hallucinate; they are skipped with audit
`message_guard: "skipped (auto-message)"`. The guard's purpose is to catch
LLM-class hallucination in agent-authored `-m` strings, not deterministic
helper output.

Verification-claim regex set (tightened, anchored to QA/AC/tests context):

- `\b(QA|qa-report)\s*[:=-]?\s*PASS\b` (case-insensitive on `qa-report`)
- `\b(QA|qa-report)\s+verdict\s*[:=-]?\s*PASS\b`
- `\b(all|every)\s+(\d+\s+)?ACs?\s+(met|passed|satisfied)\b`
- `\bverified\s+(by|via|against|in)\s+(QA|qa-report|tests?|ACs?)\b`
- `\b(this\s+(change|commit|patch)|commit)\s+verifies\b[^.\n]*\b(QA|tests?|ACs?|PASS)\b`
- `\b(QA|qa-report)\s+(cleared|approved|signed[\s-]?off)\b`
- `\b(all\s+)?tests?\s+(are\s+)?(passed|passing|green|clear)\b`
- `\b(everything|all)\s+(looks?|tests?|checks?)\s+(good|passed|fine)\b`

Legitimate prose like `"I PASS this baton on"`, `"verified the schema in code
review"`, and `"PASSWORD validation"` do NOT match.

Decision matrix (on first regex match):

| `qa.status` | Outcome |
|---|---|
| `"pass"` | ACCEPT; audit `message_guard: "applied (claim matches)"` |
| `"warning"` + same-paragraph `(warning|minor)` qualifier | ACCEPT; same audit value |
| `"warning"` without proximity qualifier | REFUSE |
| `"fail"` | REFUSE |
| qa-report file missing | REFUSE with sentinel `__absent__` |
| qa-report file unparseable JSON | REFUSE with sentinel `__invalid__` |
| `.qa.status` key missing | REFUSE with sentinel `__absent__` |
| `.qa.status` not in {pass,warning,fail} | REFUSE with sentinel `__unknown__` |

Refusal message: `commit.sh: -m message claims verification (<matched
substring>) but qa-report.qa.status is "<actual or sentinel>"`. Refusal is
stderr + exit 2 ONLY; NO audit JSON is written on refusal.

Mode skip matrix (evaluation order, MANDATORY top-down):

1. `--auto-bulk-bridge` → `skipped (bridge)`
2. `--force` (no manifest, no rescue) → `skipped (force)`
3. `--force-rescue` → `skipped (force-rescue)`
4. `--force --manifest` → `skipped (force-manifest)`
5. `CLAUDE_COMMIT_SKIP_MESSAGE_GUARD=1` → `skipped (env)`
6. `MESSAGE_SOURCE == "auto"` → `skipped (auto-message)`
7. Otherwise → guard ACTIVE.

Audit `message_guard` enumeration is EXACTLY:
`{ "skipped (force)", "skipped (force-rescue)", "skipped (force-manifest)",
"skipped (bridge)", "skipped (env)", "skipped (auto-message)",
"applied (no claim found)", "applied (claim matches)" }`. NO `"refused"` value
exists; refusal exits 2 before the audit JSON site.

## Conventional Commits type lint (DOC-16)

The wrapper enforces a Conventional Commits whitelist on the first line of
every commit message that goes through the closed-task or `--force` path
(MESSAGE_SOURCE ∈ {caller, auto} — universal CC discipline).

Subject-line regex (case-sensitive on the type token, per CC spec):

```
^(feat|fix|refactor|docs|test|chore|build|ci|perf|style|revert)(\([^)]+\))?(!)?:\s+\S.*$
```

Allowed: scope `(name)` (e.g., `feat(commit)`), breaking-change `!` marker
(e.g., `refactor(commit)!:`), longer descriptions. Whitelist is INTENTIONALLY
narrow; community types `wip / merge / release / hotfix / deps / security` map
to existing tokens via scope (`chore(deps):`, `fix(security):`,
`chore(release):`, `fix:` for hotfix).

**Helper sanitization clause (B2 propagation; iter-2 codex round 3)**:
`scripts/auto-commit-message.sh` sanitizes the derived scope at `:115-121`
via `scope = re.sub(r'[^A-Za-z0-9_-]', '', stem.replace('_', '-'))[:24] or
'task'` so that helper-emitted subjects always pass M3 even for unusual
filenames (e.g., basenames containing `)`, `(`, `.`, whitespace). Empty-
post-sanitization falls through to `'task'` via Python truthiness. Future
helper edits MUST preserve this contract — any future ctype/scope derivation
change must keep ctype in the whitelist and the scope character set
`[A-Za-z0-9_-]`.

Merge-subject note: git auto-generated subjects of the form `Merge branch
'<name>'`, `Merge tag '<name>'`, and `Merge pull request #N from ...` are
NOT CC-format and are intentionally NOT exempted from M3. Operators landing
a merge through `commit.sh --force` MUST either reformat the subject to
`chore(merge): <description>` OR set `CLAUDE_COMMIT_SKIP_TYPE_LINT=1`. The
wrapper does not invoke `git merge` directly today; this constraint affects
operators using `commit.sh --force -m '<merge-subject>'` after a manual merge.

Version-bump note: subjects like `bump: 1.2.3` are NOT CC-format. Operators
must use the CC-mapped form `chore(deps): bump foo to 1.2.3` (or similar
scope mapping appropriate to the change) OR set
`CLAUDE_COMMIT_SKIP_TYPE_LINT=1`.

Revert subject limitation (known constraint): `git revert <commit>` produces
the default subject `Revert "<original subject>"`, which does NOT match the
CC whitelist. Operators wanting an audit-trail revert MUST use the CC-form
`revert: <description>` subject manually, or use `--force -m "revert: ..."`.
This is NOT a defect of this lint; it is a documented constraint.

No first-line length cap. CC's recommended 72-char subject limit is out of
scope for this lint.

Refusal message: `commit.sh: first-line type does not match Conventional
Commits whitelist (feat|fix|refactor|docs|test|chore|build|ci|perf|style|
revert); got: <first 80 chars of subject>`. Refusal is stderr + exit 2 ONLY;
NO audit JSON is written on refusal.

Mode skip matrix:

- `--auto-bulk-bridge` → `skipped (bridge)` (bridge subject is the hard-
  coded `auto-bulk: end-of-cycle commit for <branch>` which is intentionally
  NOT CC-format)
- `CLAUDE_COMMIT_SKIP_TYPE_LINT=1` → `skipped (env)`
- All other modes including `--force`, `--force-rescue`, `--force --manifest`,
  closed-task with caller -m, AND closed-task with auto-generated message
  → lint APPLIES

Audit `type_lint` enumeration is EXACTLY:
`{ "skipped (bridge)", "skipped (env)", "applied (accepted <type>)" }`.
NO `"refused"` value exists (refusal exits 2 before audit). NO
`"skipped (auto-message)"` value exists (M3 always applies when not bridge /
not env-disabled — universal CC discipline catches future helper regression).

## Audit log persistent location (DOC-17)

Audit JSON files (one per commit) land under `CLAUDE_LOG_DIR`, with the
following resolution and validation:

**Default**: `CLAUDE_LOG_DIR=/var/lib/claude/commit-audit`. This path is
FHS-conformant (`/var/lib/<service>` is the canonical location for variable
persistent state owned by a system service), filesystem-agnostic across
operator setups (every modern Linux has `/var/lib/`), and survives reboot
(non-tmpfs). The legacy `${CLAUDE_HOME}/logs` default has been retired —
in this environment `/root/.claude` is a symlink into `/dev/shm/...` which
is tmpfs and loses audit data on reboot.

**Operator override**: `CLAUDE_LOG_DIR=<any path>` is honored verbatim
provided the path passes the preflight (`readlink -f` resolves to a
non-tmpfs filesystem AND a `mkdir -p` + write-probe succeeds).

**Preflight runs PRE-COMMIT-TREE**: the directory validation runs INSIDE
`run_private_index_commit` BEFORE `git commit-tree`. A bad
`CLAUDE_LOG_DIR` (tmpfs without opt-in, mkdir failure, write-probe failure)
exits 2 BEFORE any commit object is created. This covers all 6 invocation
paths in the single chokepoint: closed-task PRIMARY (dev-report plan),
closed-task SECONDARY (qa-report fallback), closed-task `--manifest`,
plain `--force`, `--force-rescue`, `--force --manifest`. Bridge mode does
NOT call `run_private_index_commit` and is exempt by construction.

**tmpfs refusal**: when `readlink -f $CLAUDE_LOG_DIR` resolves to a tmpfs
filesystem AND `CLAUDE_AUDIT_PERSIST_DISABLED` is NOT `"1"`, the wrapper
exits 2 with stderr `commit.sh: refusing — CLAUDE_LOG_DIR resolves to
tmpfs (<resolved-path>); set CLAUDE_LOG_DIR=<persistent-path> or export
CLAUDE_AUDIT_PERSIST_DISABLED=1 to acknowledge loss-on-reboot`.

**Operator-acknowledged tmpfs**: `CLAUDE_AUDIT_PERSIST_DISABLED=1` allows a
tmpfs-resolving `CLAUDE_LOG_DIR`; the audit JSON itself records
`"audit_persist": "disabled (operator-acknowledged)"` so forensic readers
know loss-on-reboot was explicit.

**mkdir / write-probe failure**: when `/var/lib/claude/commit-audit/` (or
the operator-supplied path) cannot be created OR cannot be written (read-
only mount, SELinux denial, permission denied, etc.), the wrapper exits 2
with stderr `commit.sh: cannot create or write audit-log directory
<resolved-path> (<errno-string>); set CLAUDE_LOG_DIR=<writable-persistent-
path>`. NO silent fallback to tmpfs.

**Mode 700**: the audit-log directory is created via `mkdir -p -m 700` so
grant/audit data is not world-readable.

**Container caveat (F7)**: S1's guarantee is non-tmpfs filesystem at commit
time; long-term retention is an operator concern — operators running in
containers or with custom systemd-tmpfiles policies SHOULD bind-mount
`/var/lib/claude/commit-audit` to a host volume or set
`CLAUDE_LOG_DIR=<external-persistent-path>`. `df -T` may report a non-
tmpfs overlay filesystem yet the directory is wiped on container
replacement; the wrapper cannot detect this and explicitly does not try.

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
