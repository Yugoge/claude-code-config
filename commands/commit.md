---
description: Commit closed dev task to branch HEAD
disable-model-invocation: true
---

# /commit — Closed Dev Task Commit

One-shot commit for a single closed dev task, scoped to that task's `dev-report.files_modified` set, gated through the always-on privilege-guard via a single-use grant manifest.

This is the ONLY agent-authorized path that advances branch HEAD outside of `/merge`.

## Usage

```
/commit <task-id> -m "<session-summary>"       # closed-task commit (-m REQUIRED)
/commit --force -m "<session-summary>"          # irregular-path escape hatch (-m REQUIRED)
```

**Example (closed-task)**: `/commit dev-20260425-145411 -m "fix(api): tighten timeout calculation per latency p95"`
**Example (--force)**: `/commit --force -m "docs(notes): add foo notes — hand-written single-file"`

The `<task-id>` argument is the same identifier used by `/dev`, `/qa`, `/close`, etc. It locates closure evidence in `docs/dev/` and the dev-report whose `files_modified` defines the staging set.

The `-m "<session-summary>"` flag is the orchestrator's way to pass a meaningful commit message describing what the user/agent accomplished in this conversation. Per redev6 P-MSG (M-MSG-1, M-MSG-2), `-m` is REQUIRED in both closed-task and `--force` modes; the auto-derived `commit(<task-id>): <H1>` boilerplate from earlier cycles is REMOVED. Per-mode semantics are documented under "-m flag (commit message)" below. Bridge mode (overnight per-cycle, see "Bridge mode" below) is the sole exception: the wrapper auto-generates the BLESSED message and `-m` is FORBIDDEN there.

The `--force` and `--auto-bulk-bridge` flags are mutually exclusive; passing both → exit 2 with usage.

## Task-id resolution

Resolve the **task-id** the same way `/close` does (see `commands/close.md:32-39` for the reference pattern — `/commit` mirrors it for documentation parity per AC-INFER-5). The task-id is the SAME identifier used by the source `/dev` (or `/redev`) cycle (e.g. `dev-20260425-145411`, `redev3-p1p2-20260426`) — NOT a fresh `date +%Y%m%d-%H%M%S` at /commit invocation time. Using a fresh timestamp would break the artifact chain (`close-report-<task-id>.md`, `dev-report-<task-id>.json`) that closure detection and grant emission depend on.

Resolve in this priority order:

- **If `$ARGUMENTS` is non-empty**: treat it as the task-id directly (or as an explicit task-id-bearing token). The orchestrator passes it through unchanged. This is the explicit-form path — backwards-compatible with every `/commit <task-id>` invocation.
- **Else (no argument)**: the orchestrator invoking /commit MUST already know this conversation's dev artifacts from context (it just ran `/dev` or `/redev` in the same session). It identifies the active dev cycle's task-id from visible artifact filenames in the transcript (`ticket-<task-id>.md` (or legacy `ba-spec-<task-id>.md`), `dev-report-<task-id>.json`, `close-report-<task-id>.md`) and embeds the resolved task-id directly into Implementation's bash invocation, NOT a literal empty string. There is NO filesystem scan and NO default-to-newest.
- **Else (neither resolves) AND no closure artifacts visible AND user clearly wants a commit anyway**: this is the irregular path. The orchestrator should invoke `bash ~/.claude/hooks/commit.sh --force -m "<session-summary>"` instead — see "Force mode (escape hatch)" below. The orchestrator MUST NOT silently fall through to closed-task mode with a fabricated task-id.
- **Else (no task-id resolvable AND no clear user intent for irregular commit)**: exit non-zero with: `No task-id resolved. Either run /commit within a conversation that just completed /dev or /redev, pass /commit <task-id>, or use /commit --force -m "<session-summary>" for irregular-path commits.`

If the orchestrator cannot identify the task-id from context AND `$ARGUMENTS` is empty AND the user has not asked for an irregular commit, /commit MUST exit with the error message above. /commit MUST NOT default to `date +%Y%m%d-%H%M%S` and MUST NOT invoke `commit.sh` with an empty positional argument — resolution failure is signaled at the orchestrator/slash-command layer, not at the wrapper layer (the wrapper's empty-arg guard remains as defense-in-depth, but it should never be reached under correct orchestrator behavior).

## Scheme 6 mechanism

See `/root/docs/scheme6.md` for the unified env-var + grant-manifest + privilege-guard validation + literal-substring rejection + single-use unlink protocol.

`/commit`-specific bindings: env-var `CLAUDE_COMMIT_COMMAND_ACTIVE=1`; grant path `/tmp/claude-commit-grant-<sid>-<nonce>.json`; manifest fields `{nonce, sid, task_id, allowed_files, expected_message_sha256, created_at, ppid}` (per spec-20260424-233926 §5.2.4 R4.3 + close-report-20260425-push-commit-debate.md §1-2). The guard admits the commit only when `sha256(message) == grant.expected_message_sha256` AND `set(git diff --cached --name-only) == set(grant.allowed_files)`. The `/merge` blessed-bridge regex (`^auto-bulk: end-of-cycle commit for `) is the only other admit path on the commit surface.

## Closed-task detection

Ordered, **fail-closed**:

1. **PRIMARY**: `docs/dev/close-report-<task-id>.md` exists AND its last non-empty line matches `^CLOSE:\s*YES\b` (allows both `CLOSE: YES` standalone and `CLOSE: YES — narrative`).
2. **SECONDARY** (only if no close-report exists): `docs/dev/completion-<task-id>.md` exists AND `docs/dev/qa-report-<task-id>.json` exists AND its `qa.status` field equals `"pass"`.
3. If neither holds, the wrapper exits non-zero with `task not closed: no close-report or completion+qa-pass evidence for <task-id>`.

**P-CLOSEHONOR (close-report verdict is binding)**: when a `close-report-<task-id>.md` exists, its verdict is authoritative. SECONDARY is only consulted when no close-report exists at all (legacy/no-close cycles).

- `CLOSE: YES` → PRIMARY admits the commit (existing behavior).
- `CLOSE: NO` → wrapper exits 2 with `task closed with verdict NO; cannot commit until /close passes`. SECONDARY is **not** consulted — this prevents the prior back-door where a deliberate negative /close verdict could be bypassed by SECONDARY fallthrough. To recover, run `/close` again after the corrective dev cycle so it produces a new close-report ending `CLOSE: YES`.
- Malformed close-report (last non-empty line is neither `CLOSE: YES` nor `CLOSE: NO`) → wrapper exits 2 with `close-report exists for <task-id> but verdict is unrecognized; expected CLOSE: YES or CLOSE: NO`. Fail-closed; SECONDARY is **not** consulted.

The closure check is **necessary but not sufficient** — even if forged, the bulk-commit-detector (`pretool-bulk-commit-detector.py`) remains an independent gate that blocks the b5d447e shape (3+ subsystem prefixes + sync.* subject) regardless.

## Defense-in-depth

See `/root/docs/scheme6.md` for the unified defense-in-depth contract (env-var, single-use grant, literal-substring rejection, downstream bulk-commit-detector, `disable-model-invocation: true` AV-5 mitigation).

## Implementation

This slash command is a thin shim over `~/.claude/hooks/commit.sh`. The orchestrator invoking `/commit` MUST already know this conversation's dev artifacts from context (per Task-id resolution rules above) AND MUST author a meaningful session-summary message based on the actual conversation (per "Orchestrator duty: write a real session summary" below). Per redev6 P-MSG, `-m "<session-summary>"` is REQUIRED in both closed-task and `--force` modes.

For closed-task mode, the orchestrator embeds the resolved task-id and a non-empty session-summary `-m` directly into:

```bash
bash ~/.claude/hooks/commit.sh <resolved-task-id> -m "<session-summary>"
```

For the irregular path (no closure ceremony), the orchestrator invokes:

```bash
bash ~/.claude/hooks/commit.sh --force -m "<session-summary>"
```

NO filesystem scan, NO default-to-newest, NO literal empty-string pass-through, NO empty/missing `-m`. If the task-id cannot be resolved (no `$ARGUMENTS`, no identifiable /dev or /redev cycle in conversation context) AND the user has not requested an irregular commit, exit with the error message defined in Task-id resolution; do NOT invoke `commit.sh` at all. If a session summary cannot be authored (the orchestrator has no context to summarize), `/commit` is the wrong command — closure ceremony exists precisely so the orchestrator has something to summarize.

The orchestrator MUST construct the session-summary message itself based on the active conversation's dev artifacts (file diffs, completion-md, close-report, qa-report). Forbidden placeholders include — but are not limited to — `WIP`, `update`, `chore: misc`, `commit`, the bare task-id, or the literal `<H1>` of the closure document. The wrapper does NOT auto-derive a fallback in either closed-task or `--force` mode — empty/missing `-m` exits 2 with `commit message required (-m); agent must summarize session intent`.

The script handles mode dispatch, closure detection (closed-task only), dev-report parsing (closed-task only), grant emission (all modes), narrow staging, the blessed `git commit`, and audit-log writes. The wrapper itself requires an explicit positional task-id for closed-task mode (its empty-arg guard remains as defense-in-depth) and an explicit non-empty `-m` for closed-task and `--force` modes — this slash-command layer is responsible for ensuring the wrapper is called with real, resolved values. See `pretool-git-privilege-guard.py` Scheme 6 manifest-validation logic for the receiving end.

## Bridge mode (overnight integration)

For `/dev-overnight` per-cycle commits, `commit.sh` accepts a second invocation form:

```
bash ~/.claude/hooks/commit.sh --auto-bulk-bridge <branch>
```

This is **not** a user-facing entry point — normal users should always use `/commit <task-id>`. Bridge mode exists so `/dev-overnight` cycles can land HEAD commits without producing a per-cycle close-report (which would not be meaningful for bulk multi-issue cycles).

What bridge mode does differently:

- Skips closure detection entirely (no PRIMARY/SECONDARY check; no close-report or completion+qa-pass evidence required).
- Reads the pre-staged file set via `git diff --cached --name-only` (caller is responsible for `git add` before invoking).
- Emits commit message `auto-bulk: end-of-cycle commit for <branch>` — this format matches `BLESSED_BRIDGE_RE` in `pretool-git-privilege-guard.py:92`, so the privilege-guard's existing early-return continues to admit the commit (preserving in-flight overnight compatibility; AC-P3-4 in `ba-spec-20260426-redev3.md`).
- STILL emits a Scheme 6 grant manifest (`allowed_files` + `expected_message_sha256` + `branch`); the privilege-guard observes this manifest and warns on staged-set / hash drift (observation-only this cycle; AC-P3-2). See `/root/docs/scheme6.md` for the unified manifest contract.
- Audit-log entries carry `mode=auto-bulk-bridge branch=<branch>` so post-hoc forensics can distinguish bridge-mode commits from closed-task commits.

Bridge mode and closed-task mode are mutually exclusive — `commit.sh` parses `$1` to decide which flow runs and exits early once it returns.

## Force mode (escape hatch)

For the irregular path — hand-written single-file commits, spec-only commits, manual recovery commits — the wrapper accepts a third invocation form:

```
bash ~/.claude/hooks/commit.sh --force -m "<session-summary>"
```

This is the orchestrator's escape hatch when there is no closure ceremony to lean on (no `close-report-<task-id>.md`, no `completion-<task-id>.md`, no `qa-report-<task-id>.json`, no `dev-report-<task-id>.json`). The user explicitly accepts responsibility for the commit; the wrapper does NOT pretend ceremony exists.

What `--force` does differently from closed-task mode:

- **Skips closure detection entirely** — no PRIMARY (close-report) or SECONDARY (completion + qa-report + dev-report) checks run.
- **Skips task-id resolution** — no `<task-id>` argument is required or accepted (the audit-log task_id field carries the literal sentinel `__force__`).
- **Skips dev-report parsing** — `allowed_files` is taken directly from `git diff --cached --name-only` (the caller's pre-staged set).
- **Skips cross-repo filter (P-CROSSREPO)** — staged set is used as-is; the staging step has already established the file is reachable from the current repo.
- **Skips P-CLOSEHONOR** — even a `close-report-<id>.md` whose last line says `CLOSE: NO` does not block `--force` (no task-id is consulted, so the close-report is never read).
- **Skips P-H1 / P-TASKID / P-NESTED** — no closure-evidence chain is walked.
- **Empty staged set rejects** — exits 2 with `commit.sh --force: no files staged; run 'git add' first`.

What `--force` keeps (all four always-on security layers — see `/root/docs/scheme6.md`): `disable-model-invocation: true` (AV-5), inline-env literal-substring rejection, `pretool-bulk-commit-detector.py` (AC-FORCE-3 — `--force` does NOT bypass the b5d447e-shape downstream gate), and the per-call grant manifest. `--force`-specific manifest fields: `mode=force`, `task_id="__force__"`, `allowed_files=<staged-set>`, `expected_message_sha256=sha256(<msg>)`, `created_at`, `ppid`.

When to use `--force` (irregular path):

- Hand-written single-file commits (e.g., adding a note to `docs/notes/foo.md`) where producing a full `/dev` -> `/qa` -> `/close` ceremony would be theatre.
- Spec-only commits where the change is pure documentation and there is no code-level closure evidence to produce.
- Manual recovery commits after partial automation (e.g., picking up where an aborted overnight cycle left off).
- Any flow the user explicitly wants to commit that does not fit the closed-task or bridge mode.

When NOT to use `--force`:

- The standard ceremony path (`/dev` -> `/qa` -> `/close` -> `/commit <task-id> -m "<msg>"`) — keep using closed-task mode for that. Closed-task mode REQUIRES the same meaningful session summary via `-m` (redev6 P-MSG / M-MSG-1) AND still validates closure evidence; the only difference vs `--force` is whether the closure-evidence chain runs.
- Overnight per-cycle commits — those are bridge mode (`commit.sh --auto-bulk-bridge <branch>`).

`--force` emits a one-line stderr warning on every invocation:
> `commit.sh: --force bypasses closure/task-id/dev-report checks; security relies on disable-model-invocation + inline-env rejection + bulk-detector + grant manifest`

Audit-log entries for `--force` carry `mode=force` for forensics.

The three modes (closed-task, bridge, force) are mutually exclusive — `commit.sh` parses the first positional argument to decide which flow runs.

## -m flag (commit message)

The `-m "<message>"` flag has different semantics in each mode:

- **Closed-task mode** (`commit.sh <task-id> -m "<msg>"`):
  - `-m` is **REQUIRED** (redev6 P-MSG / M-MSG-1). The auto-derived `commit(<task-id>): <H1>` boilerplate is REMOVED. Empty (`-m ""`) or missing (`commit.sh <task-id>` with no `-m`) → exit 2 with `commit message required (-m); agent must summarize session intent`.
  - The caller-supplied message is used verbatim. Closure detection / dev-report parsing / cross-repo filter / staged-set comparison all still run; only the closure-evidence chain is unchanged.
  - The audit-log entry records `message_source=caller` (always, by definition).

- **`--force` mode** (`commit.sh --force -m "<msg>"`):
  - `-m` is **REQUIRED** (redev6 P-MSG / M-MSG-2). The orchestrator MUST provide a non-empty message. Empty (`-m ""`) or missing (`--force` alone) → exit 2 with `commit message required (-m); agent must summarize session intent`. The audit-log entry records `message_source=caller` (always, by definition).
  - The message must be a meaningful **session-summary**: describe what the user/agent accomplished in this conversation, what files changed and why. Do NOT pass the task-id verbatim. Do NOT pass auto-generated boilerplate. Do NOT pass placeholder text. The message is the primary signal downstream agents read from `git log` to understand what changed.

- **`--auto-bulk-bridge` mode** (`commit.sh --auto-bulk-bridge <branch>`):
  - `-m` is **FORBIDDEN** (redev6 P-MSG / M-MSG-3). Bridge-mode message format is fixed: `auto-bulk: end-of-cycle commit for <branch>`. This format is required by `BLESSED_BRIDGE_RE` in `pretool-git-privilege-guard.py:92`. Passing `-m` → exit 2 with `commit.sh --auto-bulk-bridge: -m not allowed (bridge mode uses fixed BLESSED message format)`.

In all three modes the grant manifest's `expected_message_sha256` binds the actual message used (per `/root/docs/scheme6.md`): caller-supplied in closed-task and force, hard-coded BLESSED format in bridge.

`--force` and `--auto-bulk-bridge` are mutually exclusive — passing both flags exits 2 with usage. The wrapper's first-pass dispatch consumes exactly one mode flag; the second-pass loop rejects a second mode flag explicitly.

## Orchestrator duty: write a real session summary

The orchestrator invoking `/commit` MUST write a meaningful session-summary message describing what was accomplished in the conversation, NOT just the task-id or auto-generated boilerplate. The message is the primary signal downstream agents read from `git log` to understand what changed.

Concretely:

- A bad message: `commit(dev-20260425-145411): Development Completion Report` (auto-derived; opaque)
- A good message: `fix(api): widen POST /api/data timeout to 15s based on p95 latency analysis`
- Another good message: `dev(closed): redev6 P-FORCE + P-MSG — add --force escape hatch and mandatory -m flag to commit.sh; closed-task mode now accepts -m override; force mode requires non-empty -m; bridge mode forbids -m to preserve BLESSED_BRIDGE_RE`

Pass the summary via `-m "<session-summary>"` in either closed-task mode or `--force` mode — `-m` is REQUIRED in both (redev6 P-MSG / M-MSG-1 / M-MSG-2). When in doubt about whether the session is conventional enough for the closed-task ceremony, prefer `--force` plus a real summary over fabricating a closure artifact.

## Out of scope

- Free-form / model-driven commits — see `/quick-commit` (kept independent; different threat model). `--force` is NOT auto-invocable by the model: `disable-model-invocation: true` on this `commit.md` frontmatter is preserved (W-10), so every `--force` invocation is a deliberate human action through the slash command surface.
- Branch HEAD advancement for non-closed tasks — refused unless the user uses `--force` (redev6 escape hatch) with a real session-summary `-m`.
- `git push` — see `/push`.
- Auto-sequencing of `/commit` + `/merge` + `/push` from inside the agent context — explicitly NOT a goal (redev6 P-SHIP-OVERNIGHT-DOC W-1 / W-2; would give the agent unilateral push authority). The post-overnight three-command flow is documented in `commands/dev-overnight.md` Step 15 as three independent human invocations.
