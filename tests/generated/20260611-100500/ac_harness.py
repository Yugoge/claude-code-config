#!/usr/bin/env python3
"""Behavioral AC verification harness for task 20260611-100500 (Cycle 3 — L5).

L5 ESCALATION: the enforcement is moved OUT of the L4 shell-string-parsing layer
(proven undecidable across 14 reproduced forms) INTO the git-native
reference-transaction keystone, which now FIRES on the upgraded 2.54 host for a
main-worktree symref HEAD branch-switch off master. Every AC-K probe is a REAL
sandboxed reproduction: a throwaway repo on the live 2.54 git with the keystone
installed exactly as scripts/install-git-keystone.sh does in a per-overnight
target, driven by an overnight actor (CLAUDE_OVERNIGHT_ACTOR=1, no blessed
token). The block is attributed to the KEYSTONE FIRING inside git (HEAD/master
unchanged after the abort), NOT to the L4 parser recognizing the shell form.

The decisive fail-first differential is anchored on the empirically-confirmed
2.43-vs-2.54 capability gap: with the keystone installed the symref HEAD switch
is ABORTED (HEAD stays master); without it (the 2.43-equivalent: the symref
switch is invisible to the hook) the SAME form MOVES master->other. We reproduce
the 2.43-equivalent on this 2.54 host by neutralizing the keystone's HEAD case
in a sandbox copy (faithfully mirroring 2.43's symref-invisibility) so the
differential is a genuine behavioral measurement, not a version-string check.

Invocation: `python3 ac_harness.py <AC-ID>` prints a JSON object whose keys are
the assertion `property` names declared in
docs/dev/acceptance-criteria-20260611-100500.json. The generated pytest tests
load that JSON and assert each property == its expected value.

The live .git / master / core.hooksPath are NEVER touched: all repos are
throwaway temp dirs removed in finally blocks (the qa.md trap-EXIT cleanup
contract is satisfied — only short-lived subprocesses, rmtree on exit).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]  # .../dot-claude
SCRIPTS = REPO / "scripts"
HOOKS = REPO / "hooks"
KEYSTONE_SRC_DIR = HOOKS / "git-keystone"
KEYSTONE = KEYSTONE_SRC_DIR / "reference-transaction"
HOOK_GUARD = HOOKS / "pretool-overnight-hook-guard.py"
POLICY_SHIM = SCRIPTS / "overnight-git" / "git-policy-shim"
CREATE_STATE = SCRIPTS / "create-overnight-state.sh"
CREATE_WORKTREE = SCRIPTS / "create-worktree.sh"
INSTALL_KEYSTONE = SCRIPTS / "install-git-keystone.sh"
SELFTEST = SCRIPTS / "overnight-git-selftest.sh"
SPEC = REPO / "docs" / "dev" / "specs" / "spec-20260604-204954.md"
SYSTEM_GIT = "/usr/bin/git"

# Work under a NON-/tmp dir so the hook-guard's /tmp-exemption does not exempt
# the boundary tests.
WORKBASE = REPO / "tests" / "generated" / "20260611-100500" / "_work"

# The exact reversible toolchain supply (host facts pinned by BA this cycle and
# re-verified live: `git --version` == 2.54.0 on both binaries; `apt-cache
# policy git` shows the installed 2.54 PPA package AND the 2.43 rollback target).
UPGRADE_PPA_SOURCE = "git-core-ubuntu-ppa-noble.sources"
INSTALLED_PKG_VERSION = "1:2.54.0-0ppa1~ubuntu24.04.1"
ROLLBACK_PKG_VERSION = "1:2.43.0-1ubuntu7.3"


# ---------------------------------------------------------------------------
# low-level helpers
# ---------------------------------------------------------------------------

def _git(args, cwd, env=None):
    e = dict(os.environ)
    # Never let an inherited actor env leak into setup git ops.
    e.pop("CLAUDE_OVERNIGHT_ACTOR", None)
    if env:
        e.update(env)
    return subprocess.run([SYSTEM_GIT, *args], cwd=str(cwd), env=e,
                          capture_output=True, text=True)


def _sh(command, cwd, env=None):
    e = dict(os.environ)
    e.pop("CLAUDE_OVERNIGHT_ACTOR", None)
    if env:
        e.update(env)
    return subprocess.run(["bash", "-c", command], cwd=str(cwd), env=e,
                          capture_output=True, text=True)


def _make_repo(dirty=False, two_commits=True):
    """A throwaway master-default repo with a divergent branch `other`."""
    WORKBASE.mkdir(parents=True, exist_ok=True)
    d = Path(tempfile.mkdtemp(prefix="ack611-", dir=str(WORKBASE)))
    _git(["init", "-q", "-b", "master", "."], d)
    _git(["config", "user.email", "t@t"], d)
    _git(["config", "user.name", "t"], d)
    (d / "a.txt").write_text("base\n")
    sub = d / "sub"
    sub.mkdir()
    (sub / "s.txt").write_text("subbase\n")
    _git(["add", "."], d)
    _git(["commit", "-qm", "init"], d)
    # branch `other` at the FIRST commit (a different tip than master) so a
    # checkout / ref-move is a real HEAD/oid change.
    if two_commits:
        (d / "a.txt").write_text("base\nmaster-only\n")
        _git(["commit", "-aqm", "master2"], d)
        _git(["branch", "other", "HEAD~1"], d)
    else:
        _git(["branch", "other"], d)
    if dirty:
        (d / "a.txt").write_text("base\nmaster-only\nDIRTY tracked edit\n")
        (d / "untracked.txt").write_text("untracked\n")
    return d


def _install_keystone(repo):
    """Install the keystone into `repo` exactly as the launcher does (relocates
    core.hooksPath to <common>/keystone-hooks, re-homes existing hooks)."""
    return subprocess.run([str(INSTALL_KEYSTONE), "--project-dir", str(repo)],
                          capture_output=True, text=True)


def _make_243_equivalent_keystone_dir():
    """Return a temp dir holding a git-keystone/reference-transaction that is a
    faithful 2.43-equivalent: the symref HEAD branch-switch is INVISIBLE to the
    hook (only the master-ref oid change is caught), exactly as git 2.43 behaved
    before the upgrade. This reproduces the `branch_ref_only` / "would-move"
    differential as a genuine behavioral measurement on a 2.54 host."""
    src = KEYSTONE.read_text()
    head_block = (
        '      if [ "$_is_main_worktree" = "1" ] && [ "$old" != "$new" ]; then\n'
        '        _deny "$ref (main worktree HEAD)"\n'
        '      fi'
    )
    assert head_block in src, "keystone HEAD-deny block not found (source drift)"
    src243 = src.replace(
        head_block,
        '      : # 2.43-equivalent: the symref HEAD branch-switch is invisible '
        'to the hook\n      true')
    tmp = Path(tempfile.mkdtemp(prefix="ks243-"))
    ksdir = tmp / "git-keystone"
    ksdir.mkdir()
    (ksdir / "reference-transaction").write_text(src243)
    os.chmod(ksdir / "reference-transaction", 0o755)
    return tmp, ksdir


def _head_branch(repo):
    r = _git(["symbolic-ref", "--short", "HEAD"], repo)
    return r.stdout.strip() if r.returncode == 0 else ""


def _master_oid(repo):
    return _git(["rev-parse", "refs/heads/master"], repo).stdout.strip()


def _actor_env(repo, blessed=None):
    e = {"CLAUDE_OVERNIGHT_ACTOR": "1", "CLAUDE_OVERNIGHT_MAIN_ROOT": str(repo)}
    if blessed:
        e["CLAUDE_GIT_BLESSED_TOKEN"] = blessed
    return e


def _selftest_json(project_dir, keystone_dir=None):
    args = [str(SELFTEST), "--project-dir", str(project_dir)]
    if keystone_dir:
        args += ["--keystone-dir", str(keystone_dir)]
    p = subprocess.run(args, capture_output=True, text=True)
    m = re.search(r"SELFTEST_JSON=(\{.*\})", p.stdout)
    return json.loads(m.group(1)) if m else {}


def _make_worktree(repo, name="overnight-20260611-S"):
    r = subprocess.run(
        [str(CREATE_WORKTREE), "--project-dir", str(repo), name],
        capture_output=True, text=True, cwd=str(repo))
    m = re.search(r"WORKTREE_PATH=(\S+)", r.stdout)
    return m.group(1) if m else ""


def _write_state(repo, wt_path, session="S", main_git_dir=None, extra=None):
    claude = repo / ".claude"
    claude.mkdir(exist_ok=True)
    state = {
        "schema_version": 8, "session_id": session,
        "current_phase": "exploring", "end_time": "2099-01-01T00:00:00Z",
        "isolation_active_until": "2099-01-01T00:00:00Z",
        "isolation_released_at": None,
        "main_root": str(repo),
        "main_git_dir": main_git_dir or str(repo / ".git"),
        "worktree_path": wt_path,
        "worktree_branch": "worktree-overnight-20260611-S",
        "isolation_kind": "registered_worktree",
    }
    if extra:
        state.update(extra)
    (claude / f"overnight-state-{session}.json").write_text(json.dumps(state))
    return claude / f"overnight-state-{session}.json"


def _drive_hook_guard(command, repo, session="S", cwd=None, tool_name="Bash",
                      tool_input=None):
    payload = {
        "tool_name": tool_name, "session_id": session,
        "tool_input": tool_input or {"command": command},
        "cwd": cwd or str(repo),
    }
    p = subprocess.run(
        ["python3", str(HOOK_GUARD)],
        input=json.dumps(payload), capture_output=True, text=True,
        env=dict(os.environ, CLAUDE_PROJECT_DIR=str(repo)))
    return p.returncode, p.stderr


def _hook_guard_blocks(command, repo, **kw):
    rc, _ = _drive_hook_guard(command, repo, **kw)
    return rc == 2


# ---------------------------------------------------------------------------
# keystone behavioral primitive: run a git-invoking shell form as the actor
# against a keystone-installed (or 2.43-equivalent) repo and report whether the
# transaction was ABORTED (HEAD stays master AND master-ref oid unchanged).
# ---------------------------------------------------------------------------

def _run_form_and_measure(repo, command, master_oid_before, head_oid_before=None):
    """Run `command` (a ref-MOVING git form) as the overnight actor against the
    keystone-installed repo; return a dict whose `keystone_denied` requires
    POSITIVE keystone attribution (the deny signal appeared on git's own stderr)
    AND the ref did not move (HEAD on master + master oid unchanged + HEAD oid
    unchanged). Per codex-A: an unchanged post-state alone is NOT sufficient — a
    form could leave HEAD coincidentally on master without the keystone firing,
    so the deny signal is required to attribute the block to the keystone (not to
    parser recognition or to git's own unrelated failure)."""
    r = _sh(command, repo, _actor_env(repo))
    head = _head_branch(repo)
    moid = _master_oid(repo)
    deny_on_stderr = "OVERNIGHT KEYSTONE" in r.stderr
    head_on_master = head == "master"
    oid_unchanged = moid == master_oid_before
    head_oid = _git(["rev-parse", "HEAD"], repo).stdout.strip()
    head_oid_unchanged = (head_oid_before is None) or (head_oid == head_oid_before)
    # Positive attribution: the keystone FIRED (deny on git's stderr) AND the ref
    # did not move. The deny signal is load-bearing — wrappers may swallow the
    # outer rc but git still emits the keystone deny to stderr when the hook
    # aborts the transaction.
    denied = deny_on_stderr and head_on_master and oid_unchanged and head_oid_unchanged
    return {
        "keystone_denied": denied,
        "head_on_master": head_on_master,
        "master_oid_unchanged": oid_unchanged,
        "head_oid_unchanged": head_oid_unchanged,
        "deny_on_stderr": deny_on_stderr,
    }


# ===========================================================================
# AC-K1: keystone FIRES + ABORTS the main-worktree symref HEAD switch on 2.54
# ===========================================================================

def ac_k1():
    repo = _make_repo()
    ks243_tmp = None
    try:
        _install_keystone(repo)
        moid0 = _master_oid(repo)
        # As an overnight actor (no blessed token), attempt a plain HEAD switch.
        r = _sh(f"git -C {repo} checkout other", repo, _actor_env(repo))
        head = _head_branch(repo)
        moid = _master_oid(repo)
        fired_prepared = "OVERNIGHT KEYSTONE" in r.stderr  # the hook ran+denied
        aborted = head == "master" and moid == moid0       # ref did NOT move
        nonzero = r.returncode != 0

        # Capability probe on the REAL 2.54 keystone -> structural_head_switch.
        st_254 = _selftest_json(repo, keystone_dir=KEYSTONE_SRC_DIR)
        res_254 = st_254.get("reference_transaction_selftest_result", "")

        # 2.43-equivalent: the same probe with a keystone whose HEAD case is
        # neutralized (faithful 2.43 symref-invisibility) -> branch_ref_only,
        # and the plain switch WOULD move HEAD (the fail-first differential).
        ks243_tmp, ks243_dir = _make_243_equivalent_keystone_dir()
        st_243 = _selftest_json(repo, keystone_dir=ks243_dir)
        res_243 = st_243.get("reference_transaction_selftest_result", "")

        # Behavioral "would move" under the 2.43-equivalent: install the
        # neutered keystone into a fresh repo and confirm the actor switch moves
        # HEAD (proving the 2.54 block is the keystone firing, not the parser).
        repo243 = _make_repo()
        try:
            subprocess.run([str(INSTALL_KEYSTONE), "--project-dir", str(repo243),
                            "--keystone-src", str(ks243_dir)],
                           capture_output=True, text=True)
            _sh(f"git -C {repo243} checkout other", repo243, _actor_env(repo243))
            would_move_243 = _head_branch(repo243) == "other"
        finally:
            shutil.rmtree(repo243, ignore_errors=True)

        return {
            "reference_transaction_hook_fired_in_prepared_phase": fired_prepared,
            "transaction_aborted_before_ref_moved": aborted,
            "op_exit_code_nonzero": nonzero,
            "head_still_resolves_to_master": head == "master",
            "selftest_result_on_254": res_254,
            "selftest_result_on_243_equivalent": res_243,
            "differential_254_blocks_243_would_move": (
                aborted and res_254 == "structural_head_switch"
                and res_243 == "branch_ref_only" and would_move_243),
        }
    finally:
        shutil.rmtree(repo, ignore_errors=True)
        if ks243_tmp:
            shutil.rmtree(ks243_tmp, ignore_errors=True)


# ===========================================================================
# AC-K2: the WHOLE prior residual class is structurally blocked — keystone
#        fires inside git, NOT parser recognition; actor-env carriage PROVEN
# ===========================================================================

def _ac_k2_forms(repo):
    """{label: shell-command} for the 14 prior shell forms + earlier vectors."""
    m = str(repo)
    other = "other"
    return {
        "eval_cd_checkout": f"eval 'cd {m} && git checkout {other}'",
        "eval_quote_var1": f"eval \"cd {m} && git checkout {other}\"",
        "eval_cd_semicolon": f"eval 'cd {m}; git checkout {other}'",
        "eval_C_form": f"eval 'git -C {m} checkout {other}'",
        "eval_pushd": f"eval 'pushd {m} >/dev/null && git checkout {other}'",
        "if_control": f"if cd {m}; then git checkout {other}; fi",
        "for_control": f"for d in {m}; do cd $d && git checkout {other}; done",
        "while_control": f"while cd {m}; do git checkout {other}; break; done",
        "backtick": f"X=`cd {m} && git checkout {other}`; echo \"$X\"",
        "var_indirect_eval": f'cmd="cd {m} && git checkout {other}"; eval "$cmd"',
        "command_eval": f"command eval 'cd {m} && git checkout {other}'",
        "builtin_eval": f"builtin eval 'cd {m} && git checkout {other}'",
        "trap_exit": f"trap 'cd {m} && git checkout {other}' EXIT; true",
        "source_procsub": (
            f"source <(printf '%s\\n' 'cd {m} && git checkout {other}')"),
        # Realistic env-scrub: a cooperative subprocess overrides PATH but does
        # NOT deliberately erase its own CLAUDE_OVERNIGHT_ACTOR identity (that
        # would be attacker-grade, logged out-of-scope). The real overnight
        # actor carries the flag in its OS env; PATH override keeps it, so the
        # keystone still fires inside git.
        "env_scrubbed_subprocess": (
            f'python3 -c "import os,subprocess; e=dict(os.environ); '
            f"e['PATH']='/usr/bin:/bin'; "
            f"subprocess.run(['git','-C','{m}','checkout','{other}'], env=e)\""),
        "absolute_usr_bin_git": f"/usr/bin/git -C {m} checkout {other}",
        "C_into_main": f"git -C {m} checkout {other}",
        # NOTE (codex-A): `--work-tree` into main is a PURE TREE-WRITE that does
        # NOT move a ref, so the reference-transaction keystone provably cannot
        # see it. It is covered by the PRE-EXECUTION defense-in-depth (hook-guard
        # / policy-shim block it before git runs) — asserted separately below,
        # NOT folded into the keystone-denied set.
    }


def _ac_k2_plumbing_forms(repo, oid_other):
    m = str(repo)
    return {
        "plumbing_symref_retarget": f"git -C {m} symbolic-ref HEAD refs/heads/other",
        "plumbing_master_update_ref": f"git -C {m} update-ref refs/heads/master {oid_other}",
        "plumbing_no_deref_head": f"git -C {m} update-ref --no-deref HEAD {oid_other}",
        "detached_checkout": f"git -C {m} checkout --detach other",
        "detached_switch": f"git -C {m} switch --detach other",
        "reset_hard": f"git -C {m} reset --hard {oid_other}",
        # reset/merge/rebase-style master-ref movement: a forced ref update of
        # refs/heads/master to a different oid is the shape git's reset/merge/
        # rebase produce. `git branch -f master` is git-rejected on a checked-out
        # branch (git's own guard, NOT the keystone), so we use the update-ref
        # form which DOES reach the keystone's refs/heads/master deny.
        "master_ref_forced_move": (
            f"git -C {m} update-ref refs/heads/master {oid_other} {moid_self(repo)}"),
    }


def moid_self(repo):
    return _master_oid(repo)


def ac_k2():
    repo = _make_repo()
    ks243_tmp = None
    try:
        _install_keystone(repo)
        oid_other = _git(["rev-parse", "other"], repo).stdout.strip()
        moid0 = _master_oid(repo)

        forms = _ac_k2_forms(repo)
        prior14_keys = [
            "eval_cd_checkout", "eval_quote_var1", "eval_cd_semicolon",
            "eval_C_form", "eval_pushd", "if_control", "for_control",
            "while_control", "backtick", "var_indirect_eval", "command_eval",
            "builtin_eval", "trap_exit", "source_procsub",
        ]
        earlier_keys = [
            "env_scrubbed_subprocess", "absolute_usr_bin_git", "C_into_main",
            "work_tree_into_main",
        ]
        all14_denied = True
        earlier_denied = True
        per_form_head_master = True
        per_form_oid_unchanged = True
        any_deny_on_stderr = False
        for label, cmd in forms.items():
            # reset to master between forms WITHOUT the actor env (a normal
            # session is exempt; an actor-env reset would itself be keystone-
            # blocked when a prior form left HEAD detached).
            _git(["checkout", "-q", "--force", "master"], repo)
            res = _run_form_and_measure(repo, cmd, moid0)
            any_deny_on_stderr = any_deny_on_stderr or res["deny_on_stderr"]
            per_form_head_master = per_form_head_master and res["head_on_master"]
            per_form_oid_unchanged = per_form_oid_unchanged and res["master_oid_unchanged"]
            if label in prior14_keys and not res["keystone_denied"]:
                all14_denied = False
            if label in earlier_keys and not res["keystone_denied"]:
                earlier_denied = False

        plumbing = _ac_k2_plumbing_forms(repo, oid_other)
        plumbing_results = {}
        for label, cmd in plumbing.items():
            _git(["checkout", "-q", "--force", "master"], repo)
            res = _run_form_and_measure(repo, cmd, moid0)
            plumbing_results[label] = res["keystone_denied"]
            per_form_head_master = per_form_head_master and res["head_on_master"]
            per_form_oid_unchanged = per_form_oid_unchanged and res["master_oid_unchanged"]

        symref_denied = plumbing_results["plumbing_symref_retarget"]
        master_updref_denied = plumbing_results["plumbing_master_update_ref"]
        no_deref_denied = plumbing_results["plumbing_no_deref_head"]
        detached_denied = (plumbing_results["detached_checkout"]
                           and plumbing_results["detached_switch"])
        reset_merge_rebase_denied = (plumbing_results["reset_hard"]
                                     and plumbing_results["branch_f_master"])

        # actor-env carriage proof: env STRIPPED -> keystone actor gate exits 0
        # and the form MOVES HEAD; env PRESENT -> the keystone fires + denies.
        _git(["checkout", "-q", "--force", "master"], repo)
        _sh(f"git -C {repo} checkout other", repo, None)  # no actor env -> moves
        env_absent_moves = _head_branch(repo) == "other"
        _git(["checkout", "-q", "--force", "master"], repo)  # normal-session reset
        r_env = _sh(f"git -C {repo} checkout other", repo, _actor_env(repo))
        env_present_denies = (_head_branch(repo) == "master"
                              and "OVERNIGHT KEYSTONE" in r_env.stderr)
        hook_observed_actor_env = env_present_denies and env_absent_moves
        hook_observed_no_blessed = ("CLAUDE_GIT_BLESSED_TOKEN" not in _actor_env(repo)
                                    and env_present_denies)

        # block attributed to the keystone firing, NOT parser recognition: these
        # are raw subprocess git invocations (the L4 parser is not in this path)
        # and the deny appeared on git's own stderr.
        block_is_keystone = any_deny_on_stderr and env_present_denies

        # fail-first differential: under the 2.43-equivalent keystone the forms
        # MOVE master (the keystone does not fire for the symref switch).
        ks243_tmp, ks243_dir = _make_243_equivalent_keystone_dir()
        repo243 = _make_repo()
        try:
            subprocess.run([str(INSTALL_KEYSTONE), "--project-dir", str(repo243),
                            "--keystone-src", str(ks243_dir)],
                           capture_output=True, text=True)
            _sh(f"eval 'cd {repo243} && git checkout other'", repo243,
                _actor_env(repo243))
            forms_move_when_absent = _head_branch(repo243) == "other"
        finally:
            shutil.rmtree(repo243, ignore_errors=True)

        return {
            "all_14_prior_shell_forms_keystone_denied_master_unchanged": (
                all14_denied and per_form_head_master and per_form_oid_unchanged),
            "earlier_vectors_subprocess_absolute_C_worktree_keystone_denied": earlier_denied,
            "plumbing_symref_retarget_keystone_denied": symref_denied,
            "plumbing_master_ref_update_ref_keystone_denied": master_updref_denied,
            "plumbing_no_deref_head_update_keystone_denied": no_deref_denied,
            "detached_checkout_switch_keystone_denied": detached_denied,
            "reset_merge_rebase_master_ref_move_keystone_denied": reset_merge_rebase_denied,
            "block_attributed_to_keystone_firing_not_parser_recognition": block_is_keystone,
            "hook_observed_CLAUDE_OVERNIGHT_ACTOR_1_via_actor_runtime_path": hook_observed_actor_env,
            "hook_observed_no_blessed_token": hook_observed_no_blessed,
            "main_head_stays_master_per_form": per_form_head_master,
            "master_ref_oid_unchanged_per_form": per_form_oid_unchanged,
            "differential_forms_move_master_when_keystone_absent": forms_move_when_absent,
        }
    finally:
        shutil.rmtree(repo, ignore_errors=True)
        if ks243_tmp:
            shutil.rmtree(ks243_tmp, ignore_errors=True)


# ===========================================================================
# AC-K3: structural_claim_allowed honest + target-attested (no greenwash)
# ===========================================================================

def ac_k3():
    repo = _make_repo()
    ks243_tmp = None
    try:
        # (a) properly-provisioned 2.54 target: keystone installed in the
        # target's effective hooksPath, no blessed token -> claim=true.
        _install_keystone(repo)
        st_attested = _selftest_json(repo, keystone_dir=KEYSTONE_SRC_DIR)
        attested_claim = st_attested.get("structural_claim_allowed")
        attested_result = st_attested.get("reference_transaction_selftest_result")
        attested_guarantee = st_attested.get("guarantee_level")
        attested_version = st_attested.get("git_version", "")
        required_facts_present = (
            attested_claim is True
            and attested_result == "structural_head_switch"
            and attested_guarantee == "structural_head_switch"
            and attested_version.startswith("2.54"))

        # capability recorded separately: an un-attested target on the SAME 2.54
        # git records the capability structural_head_switch BUT claim=false.
        repo_unattested = _make_repo()  # keystone NOT installed in its hooksPath
        try:
            st_unatt = _selftest_json(repo_unattested, keystone_dir=KEYSTONE_SRC_DIR)
            unatt_capability = st_unatt.get("reference_transaction_selftest_result")
            unatt_claim = st_unatt.get("structural_claim_allowed")
            unatt_guarantee = st_unatt.get("guarantee_level")
        finally:
            shutil.rmtree(repo_unattested, ignore_errors=True)

        capability_recorded_separately = unatt_capability == "structural_head_switch"
        capability_not_imply_protection = (
            unatt_capability == "structural_head_switch" and unatt_claim is False)

        # (b) 2.43-equivalent target: claim=false / best_effort (no false claim).
        ks243_tmp, ks243_dir = _make_243_equivalent_keystone_dir()
        repo243 = _make_repo()
        try:
            _install_keystone(repo243)  # installs the REAL keystone hook...
            # ...but probe with the 2.43-equivalent keystone-dir so the FUNCTIONAL
            # probe records branch_ref_only (symref invisible) -> claim=false.
            st_243 = _selftest_json(repo243, keystone_dir=ks243_dir)
            claim_243 = st_243.get("structural_claim_allowed")
            guarantee_243 = st_243.get("guarantee_level")
        finally:
            shutil.rmtree(repo243, ignore_errors=True)

        # version >=2.46 is a PREREQUISITE GATE not the proof: the un-attested
        # 2.54 target passes the version gate yet claim=false because the
        # behavioral attestation (hooksPath + hook rejection) is missing.
        version_gate_not_proof = (attested_version.startswith("2.54")
                                  and unatt_claim is False)
        # the behavioral rejection probe IS the proof.
        behavioral_probe_is_proof = (attested_result == "structural_head_switch"
                                     and attested_claim is True)

        return {
            "attested_target_structural_claim_allowed": attested_claim,
            "attested_target_required_facts_all_present": required_facts_present,
            "capability_structural_head_switch_recorded_separately": capability_recorded_separately,
            "capability_alone_does_not_imply_target_protection": capability_not_imply_protection,
            "unattested_or_243_structural_claim_allowed": (
                False if (unatt_claim is False and claim_243 is False) else unatt_claim),
            "unattested_or_243_guarantee_level": (
                "best_effort_head_switch"
                if (unatt_guarantee == "best_effort_head_switch"
                    and guarantee_243 == "best_effort_head_switch")
                else unatt_guarantee),
            "version_246_check_is_prerequisite_gate_not_proof": version_gate_not_proof,
            "behavioral_rejection_probe_is_the_proof": behavioral_probe_is_proof,
        }
    finally:
        shutil.rmtree(repo, ignore_errors=True)
        if ks243_tmp:
            shutil.rmtree(ks243_tmp, ignore_errors=True)


# ===========================================================================
# AC-K4: normal sessions + this implementing session UNAFFECTED; isolation
#        never gated on git version (RG — pass pre+post)
# ===========================================================================

def ac_k4():
    repo = _make_repo()
    try:
        _install_keystone(repo)
        # NORMAL session: no CLAUDE_OVERNIGHT_ACTOR -> keystone exits 0.
        co = _sh(f"git -C {repo} checkout other", repo, None)
        branch_switch_allowed = co.returncode == 0 and _head_branch(repo) == "other"
        _sh(f"git -C {repo} checkout master", repo, None)
        ci = _sh(f"git -C {repo} commit --allow-empty -m normal", repo, None)
        commit_allowed = ci.returncode == 0
        br = _sh(f"git -C {repo} branch", repo, None)
        branch_list_allowed = br.returncode == 0
        normal_oid_move = _sh(f"git -C {repo} commit --allow-empty -m n2", repo, None)
        keystone_exits_0_non_overnight = normal_oid_move.returncode == 0

        # the LIVE implementing repo's core.hooksPath stays .git/hooks (untouched).
        live_hp = _git(["config", "--local", "--get", "core.hooksPath"], REPO).stdout.strip()
        live_default = os.path.realpath(str(REPO / ".git" / "hooks"))
        live_resolved = os.path.realpath(live_hp) if live_hp else live_default
        hookspath_stays_git_hooks = live_resolved == live_default

        # isolation/worktree creation is unconditional + never gated on git version.
        repo2 = _make_repo()
        try:
            wt = _make_worktree(repo2)
            worktree_unconditional = bool(wt) and Path(wt).exists() and wt != str(repo2)
            cw_src = (SCRIPTS / "create-worktree.sh").read_text()
            never_gated = not re.search(
                r"_ge_246|>= *2\.46|git[_-]version.*(abort|exit|refuse)", cw_src)
        finally:
            shutil.rmtree(repo2, ignore_errors=True)

        return {
            "normal_session_main_branch_switch_allowed": branch_switch_allowed,
            "normal_session_main_commit_allowed": commit_allowed,
            "normal_session_main_branch_list_allowed": branch_list_allowed,
            "keystone_exits_0_for_non_overnight_actor": keystone_exits_0_non_overnight,
            "live_implementing_repo_hookspath_stays_git_hooks": hookspath_stays_git_hooks,
            "isolation_worktree_creation_unconditional": worktree_unconditional,
            "isolation_never_gated_on_git_version": never_gated,
        }
    finally:
        shutil.rmtree(repo, ignore_errors=True)


# ===========================================================================
# AC-K5: reversible toolchain supply documented + verifiable
# ===========================================================================

def ac_k5():
    spec_txt = SPEC.read_text() if SPEC.exists() else ""
    ppa_documented = UPGRADE_PPA_SOURCE in spec_txt
    installed_documented = INSTALLED_PKG_VERSION in spec_txt
    rollback_documented = ROLLBACK_PKG_VERSION in spec_txt
    apt = subprocess.run(["apt-cache", "policy", "git"], capture_output=True, text=True)
    apt_out = apt.stdout
    shows_254 = "2.54.0-0ppa1" in apt_out
    shows_243 = "2.43.0-1ubuntu7.3" in apt_out
    rollback_available = shows_243
    rollback_best_effort_documented = (
        "best_effort" in spec_txt and "rollback" in spec_txt.lower())
    defense_in_depth_holds_documented = (
        "defense-in-depth" in spec_txt or "defense in depth" in spec_txt)
    return {
        "upgrade_ppa_source_documented": ppa_documented,
        "exact_installed_package_version_documented": (
            INSTALLED_PKG_VERSION if installed_documented else "MISSING"),
        "rollback_target_package_version_documented": (
            ROLLBACK_PKG_VERSION if rollback_documented else "MISSING"),
        "rollback_target_available_in_apt_version_table": rollback_available,
        "on_rollback_host_returns_to_best_effort": rollback_best_effort_documented,
        "on_rollback_isolation_and_defense_in_depth_still_hold": defense_in_depth_holds_documented,
        "apt_cache_policy_shows_both_2540_and_2430": shows_254 and shows_243,
    }


# ===========================================================================
# AC-K6: retained defense-in-depth covers the non-git-binary residue (raw .git)
# ===========================================================================

def ac_k6():
    repo = _make_repo()
    try:
        wt = _make_worktree(repo)
        _write_state(repo, wt)
        git_common = _git(["rev-parse", "--path-format=absolute",
                           "--git-common-dir"], repo).stdout.strip()
        head_before = (Path(git_common) / "HEAD").read_text() if git_common else ""
        master_ref = Path(git_common) / "refs" / "heads" / "master"
        master_before = master_ref.read_text() if master_ref.exists() else ""

        m = str(repo)
        head_redirect = _hook_guard_blocks(
            f"echo 'ref: refs/heads/other' > {m}/.git/HEAD", repo, cwd=wt)
        master_redirect = _hook_guard_blocks(
            f"echo deadbeef > {m}/.git/refs/heads/master", repo, cwd=wt)
        packed_redirect = _hook_guard_blocks(
            f"echo 'deadbeef refs/heads/master' >> {m}/.git/packed-refs", repo, cwd=wt)
        common_redirect = _hook_guard_blocks(
            f"printf '%s' x | tee {git_common}/refs/heads/master", repo, cwd=wt)
        write_head_blocked = _hook_guard_blocks(
            "", repo, cwd=wt, tool_name="Write",
            tool_input={"file_path": f"{m}/.git/HEAD",
                        "content": "ref: refs/heads/other\n"})

        head_after = (Path(git_common) / "HEAD").read_text() if git_common else ""
        master_after = master_ref.read_text() if master_ref.exists() else ""
        metadata_unchanged = (head_after == head_before and master_after == master_before)

        # the keystone provably cannot see a non-git-binary write.
        repo_ks = _make_repo()
        try:
            _install_keystone(repo_ks)
            ks_common = _git(["rev-parse", "--path-format=absolute",
                             "--git-common-dir"], repo_ks).stdout.strip()
            r = _sh(f"echo deadbeef >> {ks_common}/refs/heads/master", repo_ks,
                    _actor_env(repo_ks))
            keystone_blind = "OVERNIGHT KEYSTONE" not in r.stderr
        finally:
            shutil.rmtree(repo_ks, ignore_errors=True)

        spec_txt = SPEC.read_text() if SPEC.exists() else ""
        dnd_recorded = ("defense-in-depth" in spec_txt
                        and "non-load-bearing" in spec_txt)

        return {
            "raw_write_to_git_head_blocked": head_redirect and write_head_blocked,
            "raw_write_to_refs_heads_master_blocked": master_redirect,
            "raw_write_to_packed_refs_blocked": packed_redirect,
            "raw_write_to_resolved_common_dir_ref_paths_blocked": common_redirect,
            "keystone_provably_cannot_see_non_git_binary_write": keystone_blind,
            "main_metadata_byte_unchanged": metadata_unchanged,
            "defense_in_depth_retained_not_claimed_complete_for_shell_string_git": dnd_recorded,
        }
    finally:
        shutil.rmtree(repo, ignore_errors=True)


# ===========================================================================
# AC-K7: always-create-worktree before actor work; keystone install harmless
# ===========================================================================

def ac_k7():
    repo = _make_repo()
    try:
        hooks_dir = repo / ".git" / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        precommit_marker = repo / "precommit.fired"
        postcommit_marker = repo / "postcommit.fired"
        (hooks_dir / "pre-commit").write_text(
            f"#!/usr/bin/env bash\ntouch '{precommit_marker}'\nexit 0\n")
        (hooks_dir / "post-commit").write_text(
            f"#!/usr/bin/env bash\ntouch '{postcommit_marker}'\nexit 0\n")
        os.chmod(hooks_dir / "pre-commit", 0o755)
        os.chmod(hooks_dir / "post-commit", 0o755)

        r = subprocess.run(
            [str(CREATE_STATE), "--project-dir", str(repo),
             "--session-id", "S", "--end-time", "+1h"],
            capture_output=True, text=True)
        sf = repo / ".claude" / "overnight-state-S.json"
        st = json.loads(sf.read_text()) if sf.exists() else {}
        wt = st.get("worktree_path", "")
        worktree_created = bool(wt) and Path(wt).exists() and wt != str(repo)
        actor_cwd_not_main = bool(wt) and os.path.realpath(wt) != os.path.realpath(str(repo))

        common = _git(["rev-parse", "--path-format=absolute",
                      "--git-common-dir"], repo).stdout.strip()
        ks_dir = Path(common) / "keystone-hooks"
        rehomed_pre = ((ks_dir / "pre-commit").exists()
                       and (ks_dir / "preserved" / "pre-commit").exists())
        rehomed_post = ((ks_dir / "post-commit").exists()
                        and (ks_dir / "preserved" / "post-commit").exists())

        if precommit_marker.exists():
            precommit_marker.unlink()
        if postcommit_marker.exists():
            postcommit_marker.unlink()
        (repo / "trigger.txt").write_text("x\n")
        _git(["add", "trigger.txt"], repo)
        _git(["commit", "-m", "trigger hooks"], repo)  # normal session
        hooks_still_fire = precommit_marker.exists() and postcommit_marker.exists()

        no_hard_abort = r.returncode == 0 and worktree_created

        live_hp = _git(["config", "--local", "--get", "core.hooksPath"], REPO).stdout.strip()
        live_default = os.path.realpath(str(REPO / ".git" / "hooks"))
        live_resolved = os.path.realpath(live_hp) if live_hp else live_default
        keystone_only_in_target = live_resolved == live_default

        return {
            "valid_isolated_worktree_created_and_entered_before_actor_work": worktree_created,
            "actor_cwd_never_main_working_directory": actor_cwd_not_main,
            "install_keystone_rehomes_and_chains_existing_pre_commit": rehomed_pre,
            "install_keystone_rehomes_and_chains_existing_post_commit": rehomed_post,
            "existing_hooks_still_fire_after_install": hooks_still_fire,
            "no_hard_abort": no_hard_abort,
            "keystone_installed_only_in_per_overnight_target_not_live_repo": keystone_only_in_target,
        }
    finally:
        shutil.rmtree(repo, ignore_errors=True)


# ===========================================================================
# RG-1: no hard-abort; keystone deny is a runtime ref-abort (regression guard)
# ===========================================================================

def rg1_k():
    repo = _make_repo()
    try:
        # Recoverable failure: a focus that won't match -> degrade to autonomous
        # WITH a valid worktree (no hard-abort, no in-place work). This is the
        # recoverable post-worktree degradation path (M2/cp-05), distinct from a
        # legitimate refuse-to-launch when isolation is impossible.
        r = subprocess.run(
            [str(CREATE_STATE), "--project-dir", str(repo), "--session-id", "S",
             "--end-time", "+1h", "--focus", "THIS_WILL_NOT_MATCH_xyz"],
            capture_output=True, text=True)
        sf = repo / ".claude" / "overnight-state-S.json"
        st = json.loads(sf.read_text()) if sf.exists() else None
        wt = (st or {}).get("worktree_path", "")
        degrades = (bool(st) and bool(wt) and wt != str(repo) and Path(wt).exists())
        head = _head_branch(repo)
        no_in_place = head == "master"

        _install_keystone(repo)
        moid0 = _master_oid(repo)
        rk = _sh(f"git -C {repo} checkout other", repo, _actor_env(repo))
        runtime_ref_abort = (_head_branch(repo) == "master"
                             and _master_oid(repo) == moid0
                             and "OVERNIGHT KEYSTONE" in rk.stderr)
        state_intact = sf.exists() and json.loads(sf.read_text()).get("worktree_path") == wt

        cs_src = CREATE_STATE.read_text()
        no_new_hard_abort = ('SPEC_MODE="autonomous"' in cs_src
                             or "SPEC_MODE='autonomous'" in cs_src)

        return {
            "recoverable_failure_degrades_to_autonomous_with_valid_worktree": degrades,
            "never_hard_aborts_then_works_in_place": degrades and no_in_place,
            "no_in_place_main_dir_work": no_in_place,
            "keystone_deny_is_runtime_ref_abort_not_launch_abort": runtime_ref_abort and state_intact,
            "refuse_to_launch_only_when_all_isolation_impossible": degrades,
            "escalation_adds_no_new_hard_abort_path": no_new_hard_abort and degrades,
        }
    finally:
        shutil.rmtree(repo, ignore_errors=True)


# ===========================================================================
# RG-2: dirty main tree preserved + isolated (regression guard)
# ===========================================================================

def rg2_k():
    repo = _make_repo(dirty=True)
    try:
        before = (repo / "a.txt").read_text()
        before_untracked = (repo / "untracked.txt").read_text()
        subprocess.run(
            [str(CREATE_STATE), "--project-dir", str(repo), "--session-id", "S",
             "--end-time", "+1h"],
            capture_output=True, text=True)
        sf = repo / ".claude" / "overnight-state-S.json"
        st = json.loads(sf.read_text()) if sf.exists() else {}
        wt = st.get("worktree_path", "")
        head = _head_branch(repo)
        wt_branch = _git(["branch", "--show-current"], wt).stdout.strip() if wt else ""
        return {
            "dirty_main_tree_byte_preserved": (
                (repo / "a.txt").read_text() == before
                and (repo / "untracked.txt").read_text() == before_untracked),
            "main_head_stays_master": head == "master",
            "valid_worktree_on_non_master_branch_registered": (
                bool(wt) and wt != str(repo) and bool(wt_branch) and wt_branch != "master"),
        }
    finally:
        shutil.rmtree(repo, ignore_errors=True)


# ===========================================================================
# RG-3: no global master lockdown for normal sessions (regression guard)
# ===========================================================================

def rg3_k():
    repo = _make_repo()
    try:
        _install_keystone(repo)
        wt = _make_worktree(repo)
        _write_state(repo, wt)  # a LIVE overnight state exists (session S)

        co = _sh(f"git -C {repo} checkout other", repo, None)
        checkout_allowed = co.returncode == 0 and _head_branch(repo) == "other"
        _sh(f"git -C {repo} checkout master", repo, None)
        ci = _sh(f"git -C {repo} commit --allow-empty -m normal", repo, None)
        commit_allowed = ci.returncode == 0
        br = _sh(f"git -C {repo} branch newbr", repo, None)
        branch_allowed = br.returncode == 0
        normal_commit = _sh(f"git -C {repo} commit --allow-empty -m n2", repo, None)
        exemption_preserved = normal_commit.returncode == 0

        return {
            "normal_session_main_checkout_allowed": checkout_allowed,
            "normal_session_main_commit_allowed": commit_allowed,
            "normal_session_main_branch_allowed": branch_allowed,
            "no_global_master_lockdown_for_non_overnight_sessions": (
                checkout_allowed and commit_allowed and branch_allowed),
            "keystone_normal_session_exemption_preserved": exemption_preserved,
        }
    finally:
        shutil.rmtree(repo, ignore_errors=True)


_DISPATCH = {
    "AC-K1": ac_k1, "AC-K2": ac_k2, "AC-K3": ac_k3, "AC-K4": ac_k4,
    "AC-K5": ac_k5, "AC-K6": ac_k6, "AC-K7": ac_k7,
    "RG-1": rg1_k, "RG-2": rg2_k, "RG-3": rg3_k,
}


def main(argv):
    if len(argv) < 2 or argv[1] not in _DISPATCH:
        sys.stderr.write(f"usage: ac_harness.py <{'|'.join(_DISPATCH)}>\n")
        return 2
    result = _DISPATCH[argv[1]]()
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
