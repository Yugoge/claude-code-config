# Close Report: /allow gaps cycle (2026-05-24)

**Task**: Evaluate whether the /allow gap fixes can be closed and shipped.

**Changes under review**:
- `hooks/lib/allowlist.py` — `_regex_safe()` helper; `match_sentinel_grant_for_bash_command()` extended with Pass 1 (regex op="*") and Pass 2 (env-var prefix skipping); `consume_grant_for_posttool()` regex calls migrated to `_regex_safe()`
- `hooks/userprompt-consent-allowlist.sh` — removed IS_REGEX early-exit; is_regex branch in sentinel write; multi-word bare pattern fix (`' '.join(bare)`)
- `hooks/posttool-allowlist-consume.py` — sentinel consumption unblocked for subagent contexts

---

## Round 1: QA initial position

**Position**: CLOSE: YES (conditional)

**Evidence**:
1. All 9 tests pass (test_allow_gaps.py and test_allow_gapAB.py — ran live)
2. regex path in match_sentinel_grant_for_bash_command Pass 1 uses inline SIGALRM at lines 469-481 — functionally equivalent to _regex_safe(), same timeout-guard pattern
3. Multi-word pattern fix: bare branch now does `pattern = ' '.join(bare)` — captures "git push origin" as the full pattern, which sentinel write splits into `{op:"git", args_contain:["push origin"]}`
4. Subagent sentinel consumption: posttool runs sentinel consume for subagents (Bash tool only, match-gated)
5. Dangerous ops bypass by /allow is by design — user binding directive documented at pretool-bash-safety.sh lines 440-450

**Concerns raised**:
A. Pass 1 defines `_alarm_handler` inside a tight inner loop per-subcommand per-ops-entry. Repeated `signal.signal()` calls have a small race window. Pre-existing in `_regex_safe()`.
B. Multi-word bare pattern change loses "comment" concept: `/allow git push origin` treats ALL tokens as pattern. Previously "git" was pattern and "push origin" was comment. CJK comment tokens would now become part of the pattern.

---

## Round 2: Codex adversarial challenge

**Codex prompt**: forwarded to codex exec with adversarial framing, all changed files as context, requesting PROPOSED_FIX for every blocker.

### Codex findings

#### BLOCKER 1: Bash sentinel task_id priority mismatch

**Finding**: `posttool-allowlist-consume.py` Bash branch resolves `task_id` with priority order: `data.task_id` > `CLAUDE_TASK_ID` > `session_id`. The sentinel writer (`userprompt-consent-allowlist.sh`) resolves with priority order: `CLAUDE_TASK_ID` > `SID` (session_id). When `data.task_id` differs from `CLAUDE_TASK_ID` (e.g., subagent posts with its own task_id), the consumer reads a different sentinel file than the writer wrote. The sentinel is never found, never consumed, and remains on disk until the TTL window (300s). During that window the grant is reusable — "one-use" semantic is broken.

**Codex live test**:
```
rc 0  exists_after True  stderr <empty>
```
Sentinel remained on disk after posttool ran with `data.task_id` != writer's `CLAUDE_TASK_ID`. Confirmed behavior.

**PROPOSED_FIX (Codex)**: Mirror the writer's priority. Replace the Bash branch task_id resolution:
```python
# Current (wrong order):
task_id = (
    data.get("task_id")
    or os.environ.get("CLAUDE_TASK_ID")
    or session_id
)

# Fixed (matches writer priority):
env_task_id = os.environ.get("CLAUDE_TASK_ID", "")
task_id = env_task_id if env_task_id else session_id
```
Then fall back to `data.get("task_id")` only if the primary lookup finds no sentinel.

**QA assessment**: CONFIRMED blocker. The priority inversion means subagent posttool events may fail to consume the sentinel. The "one-use" contract is violated for the exact scenario this feature was built to fix (subagent consumption). Severity: BLOCKER.

---

#### BLOCKER 2: args_contain comment injection via substring matching

**Finding**: `/allow git push origin` creates sentinel `{op:"git", args_contain:["push origin"]}`. The matcher at `allowlist.py:508` checks:
```python
if all(isinstance(a, str) and a in rest for a in args_contain):
    return entry
```
where `rest = " ".join(tokens[1:])` — everything after the `op` token. For `git commit -m "push origin"`, `op="git"`, `rest="commit -m push origin"`. The check `"push origin" in "commit -m push origin"` evaluates to `True`. So a `/allow git push origin` grant matches `git commit -m "push origin"`.

**Codex live test** (direct Python invocation):
```python
match_sentinel_grant_for_bash_command(TASK_ID, 'git commit -m bad # push origin')
# => {'op': 'git', 'args_contain': ['push origin']}  — MATCH (bug)

match_sentinel_grant_for_bash_command(TASK_ID, 'git commit -m "push origin"')
# => {'op': 'git', 'args_contain': ['push origin']}  — MATCH (bug)
```

**Security impact**: `pretool-git-privilege-guard.py` calls `_check_git_allowlist()` in `_evaluate_commit()`. If `_check_git_allowlist()` returns True (sentinel matched), the commit guard exits 0 (allowed). A `/allow git push origin` grant intended only for git push operations can be exploited to authorize `git commit` by embedding the string "push origin" in a commit message or comment. This bypasses the commit privilege guard for the duration of the grant TTL.

**PROPOSED_FIX (Codex)**: The sentinel write should anchor the subcommand args precisely. Use a list of individual tokens rather than a joined string. For `/allow git push origin`, write `{op:"git", args_contain:["push", "origin"]}` and match each token against `tokens[1:]` individually (token set membership rather than substring-in-joined-string):
```python
# In userprompt-consent-allowlist.sh sentinel write:
# rest = "push origin" → args_contain = ["push", "origin"]
entry['args_contain'] = rest.split()

# In allowlist.py match:
rest_tokens = set(tokens[1:])
if all(isinstance(a, str) and a in rest_tokens for a in args_contain):
    return entry
```
This prevents "push origin" from matching inside `commit -m "push origin"` because individual tokens "push" and "origin" would also appear in `["commit", "-m", "push", "origin"]`. However, this still has a weakness: `git push --force origin` would also match since "push" and "origin" appear as tokens.

**Stronger fix**: require that the args_contain tokens appear as a contiguous subsequence (not just a set), or require exact token-by-token matching starting from position 1 (no interleaving):
```python
# Contiguous subsequence check:
def _contains_subseq(haystack: list, needle: list) -> bool:
    if not needle:
        return True
    for i in range(len(haystack) - len(needle) + 1):
        if haystack[i:i+len(needle)] == needle:
            return True
    return False

# In matcher:
rest_tokens = tokens[1:]
if all(isinstance(a, str) for a in args_contain) and _contains_subseq(rest_tokens, args_contain):
    return entry
```
With this, `["push", "origin"]` would match `["push", "origin", "main"]` but NOT `["commit", "-m", "push", "origin"]` — correct for most grant intents.

Note: the sentinel writer would still need to split `rest` into a token list so `args_contain` carries individual tokens, not a space-joined string.

**QA assessment**: CONFIRMED blocker. The live test proves `git commit -m "push origin"` matches a `/allow git push origin` grant. This is a privilege escalation path. The args_contain-as-joined-string design was already present before this cycle, but this cycle's multi-word pattern change amplifies the vulnerability: previously `/allow git push origin` wrote `{op:"git", args_contain:["push origin"]}` only if the first bare token was "git" and rest was "push origin". Now with `' '.join(bare)` the exact same sentinel structure is produced, but the test coverage only verified that the intended command matches — not that unintended commands are excluded. Severity: BLOCKER.

---

#### MAJOR 1: Pass 1 does not call _regex_safe() — inline SIGALRM in inner loop

**Finding**: Pass 1 (lines 463-481 of allowlist.py) defines `_alarm_handler` inside the per-subcommand, per-entry inner loop. Each iteration re-executes `signal.signal(signal.SIGALRM, _alarm_handler)`. This is a race window: if another SIGALRM fires between `signal.alarm(1)` and the try block, the old handler may still be active. Pre-existing in `_regex_safe()` itself, but `_regex_safe()` was introduced to centralize this logic. Pass 1 re-duplicates it.

**PROPOSED_FIX (Codex)**: Replace the inline SIGALRM block in Pass 1 with a call to `_regex_safe()`:
```python
# Replace lines 468-480:
if isinstance(regex_pattern, str):
    matched = _regex_safe(regex_pattern, sub)
    if matched:
        return entry
```
This eliminates the duplication and ensures the helper's implementation is the single canonical timeout guard.

**QA assessment**: VALID but not a new blocker — the race window pre-exists and is shared with `_regex_safe()`. The deduplication concern is real (maintainability regression). Severity: MAJOR. Not a release blocker on its own.

---

#### MAJOR 2: CJK / non-ASCII tokens treated as pattern, not comment

**Finding**: `/allow git push origin 删冗余文件` (or any trailing non-ASCII comment tokens) now becomes `pattern = "git push origin 删冗余文件"`. `_looks_regex()` returns False (no metacharacters), so it is treated as a literal 4-word pattern. The sentinel write produces `{op:"git", args_contain:["push origin 删冗余文件"]}`. The substring "push origin 删冗余文件" will never appear in a real git command's argument list, so the grant silently becomes unusable. The user intended "删冗余文件" as a human comment, not as part of the allowed operation.

**PROPOSED_FIX (Codex)**: Detect the boundary between ASCII command tokens and non-ASCII comment tokens. Stop joining at the first token that contains non-ASCII characters:
```python
import unicodedata
def _is_command_token(s):
    return all(ord(c) < 128 for c in s)

ascii_bare = []
for t in bare:
    if not _is_command_token(t):
        break
    ascii_bare.append(t)
comment_bare = bare[len(ascii_bare):]
pattern = ' '.join(ascii_bare) if ascii_bare else '.*'
is_regex = _looks_regex(pattern)
comment = ' '.join(comment_bare)
```
This restores the prior behavior where CJK comment tokens are preserved as comments.

**QA assessment**: VALID. This is a real regression: users who relied on CJK comments in `/allow` invocations will silently get non-functional grants. Severity: MAJOR. Release blocker for internationalized user contexts; non-blocking for ASCII-only users.

---

#### MINOR 1: Struct rejection heuristic false negatives

**Finding**: The nested-quantifier rejection heuristic in `userprompt-consent-allowlist.sh` (lines 131-146) uses `re.search(r'\([^)]*[+*][^)]*\)[+*]', p)`. This misses patterns like `(a+){3,}` or `(a+)` without a trailing quantifier. Also misses `(?:a+)+`.

**PROPOSED_FIX (Codex)**: Heuristic hardening or switching to a timeout-only defense. Given SIGALRM is already present as the consumer-side guard, the structural rejection is defense-in-depth only. Not a blocker.

**QA assessment**: OBSERVATION_ONLY for this cycle. The V1b structural check is defense-in-depth; SIGALRM handles what it misses. Out of scope for this cycle.

---

## Round 2: QA position after Codex

**Two confirmed blockers prevent close**:

1. **BLOCKER 1 (task_id priority inversion)**: The sentinel writer keys on `CLAUDE_TASK_ID || SID`. The Bash sentinel consumer resolves `data.task_id` first. When subagents post posttool events with their own `data.task_id`, the consumer looks up the wrong sentinel file, finds nothing, and the sentinel remains on disk — violating the one-use semantic that was explicitly the goal of Gap A.

2. **BLOCKER 2 (args_contain comment injection)**: `{op:"git", args_contain:["push origin"]}` matches `git commit -m "push origin"` via the `a in rest` substring check. This allows a `/allow git push origin` grant to authorize `git commit` operations through `pretool-git-privilege-guard.py`'s `_evaluate_commit()` → `_check_git_allowlist()` path. Live-tested and confirmed.

Both blockers require code changes before close.

---

## Final verdict

CLOSE: NO - args_contain uses substring-in-joined-rest matching so a "/allow git push origin" grant also authorizes "git commit -m push origin" via the privilege guard, and the posttool task_id priority order is inverted from the writer breaking one-use consumption for subagents.

---

## Re-evaluation cycle (2026-05-24T20:30Z) — post-fix verification

### Changes claimed fixed since prior CLOSE: NO

| # | Fix claimed | Status |
|---|---|---|
| BLOCKER 1 | posttool task_id priority matches writer (CLAUDE_TASK_ID > session_id) | Verified PASS |
| BLOCKER 2 | args_contain injection prevented via prefix matching | Verified PASS |
| MAJOR 1 | Pass 1 uses `_regex_safe()` helper instead of inline SIGALRM | Verified PASS |
| MAJOR 2 | CJK comment: bare-token parser stops at first non-ASCII token | Verified PASS |
| Sentinel writer | `entry['args_contain'] = rest.split()` (individual tokens) | Verified PASS |

### QA verification evidence

**Live test runs** (all pass):
- `/var/tmp/test_allow_gaps.py`: Gap1 basic, timeout guard, bad regex, Gap2 env-prefix — ALL PASS
- `/var/tmp/test_allow_gapAB.py`: Gap B-1,B-2,B-3 (multi-word match/neg/exact), Gap A-1,A-2 (subagent/main-agent consume) — ALL PASS
- `/var/tmp/test_inject.py`: intended command PASS, injection via quoted commit msg BLOCKED, injection via shell comment BLOCKED — ALL PASS

**Additional QA edge cases** (all pass):
- EC-1: `git stash list` does NOT match `push origin` grant (different subcommand at prefix)
- EC-3: old-style `args_contain=["push origin"]` normalizes and matches `git push origin master`
- EC-4: `git commit -m "push origin"` does NOT match `push,origin` grant (prefix check blocks)
- EC-5/EC-6: empty/absent `args_contain` matches any git command (wildcard intent preserved)
- BLOCKER1: posttool consumed sentinel via `CLAUDE_TASK_ID` env var confirmed
- BLOCKER1 fallback: `session_id` fallback works when `CLAUDE_TASK_ID` absent

### Round 1 QA position (before Codex)

CLOSE: YES

All four named items fixed. The prefix-match approach is correct for its stated scope. The task_id priority inversion is fixed in the Bash branch. No regressions detected in the named test coverage.

Noted but accepted: EC-2 shows `git -C /tmp push origin` does NOT match a `push origin` grant because `-C` appears at the prefix position. This is a pre-existing limitation of structural matching — not a regression introduced by these fixes.

---

### Round 1 Codex adversarial challenge

**Codex verdict: CLOSE NO** — two new BLOCKERs with PROPOSED_FIX for both.

#### Codex BLOCKER 1: Compound command injection via first-subcommand match

**Finding**: `match_sentinel_grant_for_bash_command()` returns success if ANY subcommand in a compound Bash command matches the grant. The pretool-bash-safety.sh sentinel short-circuit then exits 0 (allow) for the ENTIRE Bash call — including all other subcommands in the chain.

**Codex live test** (confirmed independently at `/var/tmp/test_codex_blockers.py`):
```
git push origin; systemctl restart happy-daemon-dev => True
git commit -m push-origin => False
```

**Security impact**: A user grants `/allow git push origin`. The agent then runs `git push origin; systemctl restart happy-daemon-dev`. The first subcommand matches the grant → sentinel short-circuit exits 0 before the daemon-restart prohibition check (pretool-bash-safety.sh:560). The daemon restart executes. The entire safety layer is bypassed for the dangerous trailing subcommand.

This also affects: branch-protection checks, force-push guards, and every other safety layer in pretool-bash-safety.sh that fires AFTER the sentinel short-circuit.

**QA independent confirmation** (`test_codex_blockers.py`): CONFIRMED. `git push origin; systemctl restart happy-daemon-dev` returns `True` from the matcher with a `push origin` grant.

**PROPOSED_FIX (Codex)**: Require the entire Bash command to consist of exactly one subcommand for structural sentinel grants. If the command splits into multiple subcommands, deny (return None):

```python
subs = _bash_subcommands(command)
if len(subs) != 1:
    return None
for sub in subs:
    ...
```

If multi-command support is needed later, require EVERY subcommand to match an allowed operation (no unmatched extras).

**QA assessment**: CONFIRMED BLOCKER. The injection is real and the proposed fix is correct. The security invariant is "allow the granted command, not all commands after the granted command". Severity: BLOCKER.

---

#### Codex BLOCKER 2: Malformed posttool input does not consume session-keyed sentinel

**Finding**: The `except Exception` branch in `posttool-allowlist-consume.py:68-74` uses only `os.environ.get("CLAUDE_TASK_ID", "")`. When `CLAUDE_TASK_ID` is absent and the writer keyed the sentinel by `session_id` (because `CLAUDE_TASK_ID` was also absent at write time), the malformed-input branch does not find the sentinel and does not consume it.

**Writer priority** (userprompt-consent-allowlist.sh:198): `TASK_ID="${CLAUDE_TASK_ID:-${SID}}"` — uses session_id as fallback.

**Malformed branch** (posttool-allowlist-consume.py:71): `task_id = os.environ.get("CLAUDE_TASK_ID", "")` — no session_id fallback.

**Codex live test** (confirmed independently):
```
still_exists  (sentinel remained after malformed posttool with no CLAUDE_TASK_ID set)
```

**QA independent confirmation** (`test_codex_blockers.py`): CONFIRMED. Sentinel with `task_id=session_id` remains after malformed posttool input when `CLAUDE_TASK_ID` is absent.

**PROPOSED_FIX (Codex)**:
```python
except Exception:
    env_task_id = os.environ.get("CLAUDE_TASK_ID", "")
    session_id = os.environ.get("CLAUDE_SESSION_ID", "default")
    task_id = env_task_id if env_task_id else session_id
    if task_id:
        consume_sentinel_grant_on_terminal_result(task_id, "malformed")
    sys.exit(0)
```

**QA assessment**: CONFIRMED BLOCKER. Violates the AC2 "consume-on-any-terminal-result including malformed" contract when `CLAUDE_TASK_ID` is absent. Severity: BLOCKER (AC2 contract violation).

---

### Round 1 QA position after Codex (final)

Prior fixes (BLOCKER 1 args_contain injection, BLOCKER 1 task_id priority, MAJOR 1 Pass1 dedup, MAJOR 2 CJK) are all verified as correctly fixed.

Two new blockers found by Codex, independently confirmed by QA:

1. **Compound command injection**: `git push origin; <dangerous>` matches a `git push origin` grant and bypasses ALL subsequent safety checks via the sentinel short-circuit. This is the highest-severity finding — it defeats the entire safety layer for compound commands.

2. **Malformed posttool task_id gap**: When `CLAUDE_TASK_ID` is absent, malformed posttool input does not consume a session_id-keyed sentinel. Minor severity relative to #1 but violates explicit AC2 contract.

Both have PROPOSED_FIX. Neither is the same as the previously-closed BLOCKERs.

---

## Final verdict

CLOSE: NO - compound command injection confirmed: a "/allow git push origin" grant authorizes "git push origin; systemctl restart happy-daemon-dev" in full via first-subcommand sentinel match, bypassing daemon-restart prohibition and all subsequent safety layers.
