# BA Specification: Register AC7 and AC7b in per-task manifest (task 20260526-052559)

**Request ID**: dev-20260526-203808-manifest
**Created**: 2026-05-26T20:38:08Z
**Tier**: SMALL

## Goal

Add two missing entries (`ac-07` and `ac-07b`) to `tests/generated/20260526-052559/manifest.json` so the `active_tests` array has 8 entries instead of 6. The global index at `tests/generated/manifest.json` already has the correct task entry and requires no structural change (its schema tracks manifest paths, not test counts).

## Context

Task 20260526-052559 produced test files for ACs 1–6 when the test-writer ran. After the manifest was already written, the test-writer added two more files — `test_ac_07_ac07-venv-activate-allowed.py` and `test_ac_07b_ac07b-forged-arg-blocked.py` — covering M5 positive (canonical venv-activate form) and M5 negative (forged `--sid` argument) behaviours for `pretool-bash-safety.sh`. These files exist on disk and pass pytest collection, but are absent from `active_tests` in the per-task manifest, making QA traceability incomplete.

## Setup / Environment

- **applicability**: N/A
- **reason**: non-UI -- config; cycle does not produce (1) rendered UI changes, (2) browser interaction, (3) Playwright invocation, (4) screenshot evidence, or (5) any change to user-triggered code paths

## Evidence (Contract A)

- **Observed**: "manifest.json active_tests array has 6 entries; it should have 8 — AC7 and AC7b files added by test-writer after manifest was already written"
- **Measured**: `active_tests` array length = 6 at `tests/generated/20260526-052559/manifest.json:5`
- **Expected**: `active_tests` array length = 8 (two additional entries for `ac-07` and `ac-07b`)
- **Gap**: 2 missing entries; both test files confirmed present on disk via directory listing

## Scope (Contract B)

- **Search pattern**: `"ac_id"` in `tests/generated/20260526-052559/manifest.json`
- **Search scope**: `tests/generated/20260526-052559/`
- **User reported**: `tests/generated/20260526-052559/manifest.json`
- **Additional found via grep**: `tests/generated/manifest.json` (global index — already has task entry; no structural update required)
- **All occurrences**: `tests/generated/20260526-052559/manifest.json` (6 existing `ac_id` entries)

## Reference Source (Contract C)

- **Tier**: tier_2_verified
- **Source**: Existing manifest schema observed in `tests/generated/20260526-052559/manifest.json` (lines 1–88) and test file headers (`test_ac_07_ac07-venv-activate-allowed.py` lines 1–6, `test_ac_07b_ac07b-forged-arg-blocked.py` lines 1–6)
- **Location**: `/dev/shm/dev-workspace/dot-claude/tests/generated/20260526-052559/manifest.json`
- **Copy allowed**: yes — schema is project-internal convention; reuse verbatim field names

## Prior Attempts (Contract D)

- **Triggered**: no

## Requirements (MoSCoW)

### Must Have
- Add `ac-07` entry to `active_tests` in `tests/generated/20260526-052559/manifest.json`
- Add `ac-07b` entry to `active_tests` in `tests/generated/20260526-052559/manifest.json`

### Won't Have (Non-Goals)
- Modifying the global `tests/generated/manifest.json` beyond confirming the task entry is present (it already is)
- Updating any test file contents
- Changing schema_version or any other manifest field

## Requirements Decomposition

| ID | Source phrase (verbatim from user) | Classification | Acceptance criterion |
|----|------------------------------------|----------------|----------------------|
| R1 | "register AC7 and AC7b in the per-task manifest" | user-need clause | manifest active_tests has 8 entries with correct ac-07 and ac-07b objects |
| R2 | "update the global manifest at tests/generated/manifest.json if the task entry there needs updating" | user-need clause (conditional) | global manifest already has the task entry; verify presence only — no write needed |

## Acceptance Criteria

### AC1: Per-task manifest has exactly 8 active_tests entries
- GIVEN `tests/generated/20260526-052559/manifest.json` after dev applies the change
- WHEN the JSON is parsed and `active_tests` array length is measured
- THEN `len(active_tests) == 8`

### AC2: AC7 entry is correctly registered
- GIVEN the updated per-task manifest
- WHEN searching `active_tests` for `"ac_id": "ac-07"`
- THEN one entry exists with `ac_uid = "ac07-venv-activate-allowed"`, `type = "hook"`, `file = "tests/generated/20260526-052559/test_ac_07_ac07-venv-activate-allowed.py"`, `status = "active"`, `task_id = "20260526-052559"`

### AC3: AC7b entry is correctly registered
- GIVEN the updated per-task manifest
- WHEN searching `active_tests` for `"ac_id": "ac-07b"`
- THEN one entry exists with `ac_uid = "ac07b-forged-arg-blocked"`, `type = "hook"`, `file = "tests/generated/20260526-052559/test_ac_07b_ac07b-forged-arg-blocked.py"`, `status = "active"`, `task_id = "20260526-052559"`

### AC4: Global manifest task entry is present
- GIVEN `tests/generated/manifest.json`
- WHEN searching `tasks[]` for `"task_id": "20260526-052559"`
- THEN one entry exists with `manifest_path = "tests/generated/20260526-052559/manifest.json"` (no write required — entry already exists)

## Technical Hints

- Affected files: `tests/generated/20260526-052559/manifest.json` (write required); `tests/generated/manifest.json` (read-verify only, no write needed)
- New entries must follow the existing object shape exactly: `task_id`, `ac_id`, `ac_uid`, `type`, `file`, `status`, `hook_check`
- `hook_check` for ac-07: `{"method": "pytest or bash subprocess", "expected_exit": 0}` — minimal form matching ac-03 schema (no command or description fields)
- `hook_check` for ac-07b: `{"method": "pytest or bash subprocess", "expected_exit": 2, "expected_stderr_token": "bulk-commit-auth-flag-write"}` — matching ac-02 schema (no command or description fields)
- Append the two new entries at the end of `active_tests` to minimize diff
- **Codex adversarial review**: confirmed draft is correct; applied fix to drop extra non-canonical fields (command, description) from hook_check objects per Codex finding
