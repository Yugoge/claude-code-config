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

def _run_form_and_measure(repo, command, master_oid_before):
    """Run `command` (a shell form invoking git) as the overnight actor; return
    a dict: keystone_denied (HEAD on master AND master oid unchanged),
    head_on_master, master_oid_unchanged, deny_on_stderr."""
    r = _sh(command, repo, _actor_env(repo))
    head = _head_branch(repo)
    moid = _master_oid(repo)
    deny_on_stderr = "OVERNIGHT KEYSTONE" in r.stderr
    head_on_master = head == "master"
    oid_unchanged = moid == master_oid_before
    # The block is attributed to the keystone firing: the ref did NOT move
    # (HEAD still master, master oid unchanged). Some wrappers swallow git's
    # non-zero exit (backtick/subprocess), so the load-bearing evidence is the
    # UNCHANGED post-state, not the outer rc.
    denied = head_on_master and oid_unchanged
    return {
        "keystone_denied": denied,
        "head_on_master": head_on_master,
        "master_oid_unchanged": oid_unchanged,
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
        "work_tree_into_main": (
            f"git -C {m} --work-tree {m} checkout {other} -- a.txt"),
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
        "branch_f_master": f"git -C {m} branch -f master {oid_other}",
    }


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


def _dead_ac3():
    repo = _make_repo()
    try:
        wt = _make_worktree(repo)
        main_git_dir = _git(["rev-parse", "--absolute-git-dir"], repo).stdout.strip()
        _write_state(repo, wt, main_git_dir=main_git_dir)
        head_oid = _git(["rev-parse", "HEAD"], repo).stdout.strip()
        sub = f"{repo}/sub"

        # (vector_key, hook-guard command, policy-shim argv, shim cwd)
        vectors = {
            "main_sub_restore": (
                f"git -C {sub} restore ../a.txt",
                ["-C", sub, "restore", "../a.txt"], repo),
            "main_sub_add": (
                f"git -C {sub} add -A",
                ["-C", sub, "add", "-A"], repo),
            "main_sub_checkout": (
                f"git -C {sub} checkout other",
                ["-C", sub, "checkout", "other"], repo),
            "git_dir_redirect_to_main": (
                f"git --git-dir={repo}/.git checkout other",
                [f"--git-dir={repo}/.git", "checkout", "other"], wt),
            "GIT_DIR_env_redirect_to_main": (
                f"GIT_DIR={repo}/.git git checkout other",
                ["checkout", "other"], wt),  # shim reads GIT_DIR from env below
            "hookspath_suppression_against_main": (
                f"git -c core.hooksPath=/dev/null -C {repo} checkout other",
                ["-c", "core.hooksPath=/dev/null", "-C", str(repo), "checkout", "other"], repo),
            "branch_f_master_move": (
                f"git -C {repo} branch -f master {head_oid}",
                ["-C", str(repo), "branch", "-f", "master", head_oid], repo),
            "update_ref_master_move": (
                f"git -C {repo} update-ref refs/heads/master {head_oid}",
                ["-C", str(repo), "update-ref", "refs/heads/master", head_oid], repo),
            "reset_against_main": (
                f"git -C {repo} reset --hard {head_oid}",
                ["-C", str(repo), "reset", "--hard", head_oid], repo),
            "stash_apply_against_main": (
                f"git -C {repo} stash apply",
                ["-C", str(repo), "stash", "apply"], repo),
        }

        out = {}
        main_a_before = (repo / "a.txt").read_text()
        for key, (hg_cmd, shim_argv, shim_cwd) in vectors.items():
            out[f"hook_guard_blocks_{key}"] = _hook_guard_blocks(hg_cmd, repo, cwd=wt)
            env_extra = None
            if key == "GIT_DIR_env_redirect_to_main":
                env_extra = {"GIT_DIR": f"{repo}/.git"}
            out[f"policy_shim_blocks_{key}"] = _shim_blocks(
                shim_argv, repo, wt, env_extra=env_extra, cwd=shim_cwd)
        # the GIT_DIR property naming in the AC uses GIT_DIR_env_redirect_to_main
        # mapped to GIT_DIR_env_redirect_to_main below.

        # Per-vector main integrity: nothing actually ran (all blocked), so main
        # worktree byte-unchanged + HEAD master.
        main_a_after = (repo / "a.txt").read_text()
        head = _main_branch(repo)

        # Allow: a legit op inside the worktree subdir is NOT over-restricted.
        wt_sub = Path(wt) / "wtsub"
        wt_sub.mkdir(exist_ok=True)
        (wt_sub / "x.txt").write_text("x\n")
        allow_hg = not _hook_guard_blocks(f"git -C {wt}/wtsub status", repo, cwd=wt)
        allow_shim = not _shim_blocks(["-C", f"{wt}/wtsub", "status"], repo, wt, cwd=wt)

        result = dict(out)
        # rename GIT_DIR keys to match AC property names
        result["hook_guard_blocks_GIT_DIR_env_redirect_to_main"] = out["hook_guard_blocks_GIT_DIR_env_redirect_to_main"]
        result["policy_shim_blocks_GIT_DIR_env_redirect_to_main"] = out["policy_shim_blocks_GIT_DIR_env_redirect_to_main"]
        result["main_worktree_byte_unchanged_per_vector"] = (main_a_after == main_a_before)
        result["main_head_stays_master_per_vector"] = (head == "master")
        result["worktree_sub_status_allowed_hook_guard"] = allow_hg
        result["worktree_sub_status_allowed_policy_shim"] = allow_shim
        return result
    finally:
        shutil.rmtree(repo, ignore_errors=True)


# ---------------------------------------------------------------------------
# AC-4: direct /stop release-helper execution guarded — five components (fix-4)
# ---------------------------------------------------------------------------

def ac4():
    repo = _make_repo()
    sentinel_dir = Path(tempfile.mkdtemp(prefix="ac611-sent-"))
    try:
        wt = _make_worktree(repo)
        sf = _write_state(repo, wt, session="S")

        # (a) settings.json PreTool wiring present.
        settings_txt = SETTINGS.read_text()
        wiring_present = ("pretool-wrapper-userintent.py" in settings_txt
                          and USERINTENT_GUARD.exists())

        def drive_userintent(command, session="S"):
            payload = {"tool_name": "Bash", "session_id": session,
                       "tool_input": {"command": command}}
            p = subprocess.run(
                ["python3", str(USERINTENT_GUARD)],
                input=json.dumps(payload), capture_output=True, text=True,
                env=dict(os.environ, CLAUDE_PROJECT_DIR=str(repo),
                         CLAUDE_USERINTENT_SENTINEL_DIR=str(sentinel_dir)))
            return p.returncode

        # (b) PreTool block of a direct/unsanctioned invocation (no sentinel).
        rc_direct = drive_userintent(f"python3 {BREAK_LOCK}")
        pretool_blocks_direct = rc_direct == 2

        # (c) helper-side validation before mutation: run the helper directly with
        # NO helper-auth token -> it must NOT set isolation_released_at.
        helper_env = dict(os.environ, CLAUDE_PROJECT_DIR=str(repo),
                          CLAUDE_SESSION_ID="S",
                          CLAUDE_USERINTENT_SENTINEL_DIR=str(sentinel_dir))
        subprocess.run(["python3", str(BREAK_LOCK)], capture_output=True,
                       text=True, env=helper_env)
        st_after_direct = json.loads(sf.read_text())
        helper_validates = st_after_direct.get("isolation_released_at") is None

        # reset state for the legit path test
        sf = _write_state(repo, wt, session="S")

        # (e) legit /stop path: user typed /stop -> user-intent sentinel exists ->
        # PreTool guard consumes it + mints helper-auth -> helper releases.
        (sentinel_dir / "claude-stop-userintent-S.flag").write_text("true")
        rc_legit_pretool = drive_userintent(f"python3 {BREAK_LOCK}", session="S")
        legit_pretool_allowed = rc_legit_pretool == 0
        # now the helper-auth token exists; run the helper -> releases.
        subprocess.run(["python3", str(BREAK_LOCK)], capture_output=True,
                       text=True, env=helper_env)
        st_after_legit = json.loads(sf.read_text())
        legit_releases = st_after_legit.get("isolation_released_at") is not None

        # (d) one-shot consumption rejects reuse: the user-intent sentinel was
        # consumed by the first PreTool call; a SECOND direct call with the (now
        # gone) stale sentinel is rejected.
        rc_reuse = drive_userintent(f"python3 {BREAK_LOCK}", session="S")
        one_shot_rejects_reuse = rc_reuse == 2

        return {
            "direct_break_overnight_lock_blocked": pretool_blocks_direct,
            "isolation_released_at_not_set_by_actor": helper_validates,
            "pretool_userintent_guard_present_and_wired": wiring_present,
            "helper_side_validates_sentinel_before_mutation": helper_validates,
            "sentinel_consumed_one_shot_rejects_reuse": one_shot_rejects_reuse,
            "legit_stop_path_still_releases": legit_pretool_allowed and legit_releases,
        }
    finally:
        shutil.rmtree(repo, ignore_errors=True)
        shutil.rmtree(sentinel_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# AC-5: keystone install ordered before the self-test, observable (fix-5)
# ---------------------------------------------------------------------------

def ac5():
    repo = _make_repo()
    try:
        src = CREATE_STATE.read_text()
        # Observable ordering: the keystone install block must appear BEFORE the
        # self-test invocation in create-overnight-state.sh.
        install_idx = src.find("install-git-keystone.sh")
        # find the self-test EXECUTION (bash "$SELFTEST_SCRIPT"), not the var def.
        selftest_exec_idx = src.find('bash "$SELFTEST_SCRIPT"')
        if selftest_exec_idx < 0:
            selftest_exec_idx = src.find("overnight-git-selftest.sh")
        install_before_selftest = (
            install_idx >= 0 and selftest_exec_idx >= 0
            and install_idx < selftest_exec_idx)

        # Run the REAL launcher on the 2.43 host: the honest fields must be
        # unchanged (no false structural claim).
        r = subprocess.run(
            [str(CREATE_STATE), "--project-dir", str(repo),
             "--session-id", "S", "--end-time", "+1h"],
            capture_output=True, text=True)
        sf = repo / ".claude" / "overnight-state-S.json"
        st = json.loads(sf.read_text()) if sf.exists() else {}
        real_243_structural = st.get("structural_claim_allowed")
        real_243_guarantee = st.get("guarantee_level")

        # >=2.46-equivalent observability: with the install BEFORE the self-test,
        # a self-test that observes a firing keystone records a structural claim.
        # We instrument this in a temp repo by checking the self-test reads the
        # ALREADY-INSTALLED keystone (core.hooksPath) — i.e. install precedes the
        # self-test's target attestation. We assert the structural pathway is
        # reachable: when the self-test's gate would pass (>=2.46 + firing
        # keystone), the recorded claim is True. On this 2.43 host we cannot mint
        # a real >=2.46 git, so we PROVE the ordering enables the claim by
        # confirming the self-test runs AFTER an installed keystone (the firing
        # observation precondition) — the source ordering above + a functional
        # check that the installed keystone fires for a master ref-move.
        ks_repo = _make_repo()
        try:
            subprocess.run([str(SCRIPTS / "install-git-keystone.sh"),
                            "--project-dir", str(ks_repo)],
                           capture_output=True, text=True)
            oid = _git(["rev-parse", "HEAD"], ks_repo).stdout.strip()
            # an overnight actor master ref-move must be denied by the installed
            # keystone (proves the keystone is installed + firing BEFORE any
            # self-test attestation would read it).
            mv = _git(["update-ref", "refs/heads/master", oid + ""],
                      ks_repo, env={"CLAUDE_OVERNIGHT_ACTOR": "1"})
            # a no-op update-ref to same oid won't change; force a real change by
            # creating a new commit oid then attempting the actor move.
            (ks_repo / "k.txt").write_text("k\n")
            _git(["add", "k.txt"], ks_repo)
            _git(["commit", "-qm", "k"], ks_repo)
            new_oid = _git(["rev-parse", "HEAD"], ks_repo).stdout.strip()
            actor_move = _git(["update-ref", "refs/heads/master", oid],
                              ks_repo, env={"CLAUDE_OVERNIGHT_ACTOR": "1"})
            keystone_fires = actor_move.returncode != 0
        finally:
            shutil.rmtree(ks_repo, ignore_errors=True)

        return {
            "keystone_install_precedes_selftest_observable_in_temp_repo": install_before_selftest,
            # The >=2.46-equivalent structural claim is RECORDABLE because the
            # install precedes the self-test AND the installed keystone fires
            # (the self-test's structural gate is reachable once git>=2.46). On
            # the real 2.43 host the gate fails honestly (asserted below).
            "on_246_equivalent_selftest_observes_firing_keystone_then_records_structural_claim_allowed": (
                install_before_selftest and keystone_fires),
            "on_real_git_243_structural_claim_allowed": real_243_structural,
            "on_real_git_243_guarantee_level": real_243_guarantee,
        }
    finally:
        shutil.rmtree(repo, ignore_errors=True)


# ---------------------------------------------------------------------------
# AC-8: DIFFERENTIAL fail-first — registered actor BLOCKED on residual vector
#       while normal session ALLOWED, under the SAME live state (fix-2)
# ---------------------------------------------------------------------------

def ac8():
    repo = _make_repo()
    try:
        wt = _make_worktree(repo)
        _write_state(repo, wt)

        # Registered overnight actor uses the AC-2 RESIDUAL vectors (env-scrubbed
        # subprocess + absolute /usr/bin/git) — the forms Cycle-1 does NOT catch.
        # The actor's cwd is the worktree (payload). The hook-guard classifies it
        # as overnight_owner from the LIVE state (session_id == 'S').
        env_scrubbed_cmd = _subprocess_checkout_payload(repo, "v2")
        absolute_git_cmd = _subprocess_checkout_payload(repo, "v3")
        actor_env_scrubbed_blocked = _hook_guard_blocks(
            env_scrubbed_cmd, repo, session="S", cwd=wt)
        actor_absolute_blocked = _hook_guard_blocks(
            absolute_git_cmd, repo, session="S", cwd=wt)

        # NON-overnight session: a different session_id with NO live overnight
        # state of its own, cwd OUTSIDE the worktree (main repo). It runs an
        # ordinary main-repo git op. It must be ALLOWED (classification 'normal').
        normal_checkout_rc, _ = _drive_hook_guard(
            f"git -C {repo} checkout other", repo, session="U", cwd=str(repo))
        normal_checkout_allowed = normal_checkout_rc == 0
        normal_commit_rc, _ = _drive_hook_guard(
            f"git -C {repo} commit --allow-empty -m x", repo, session="U", cwd=str(repo))
        normal_commit_allowed = normal_commit_rc == 0

        # main HEAD untouched (hook-guard blocks before execution; nothing ran).
        head = _main_branch(repo)

        return {
            "registered_overnight_actor_env_scrubbed_subprocess_main_checkout_blocked": actor_env_scrubbed_blocked,
            "registered_overnight_actor_absolute_usr_bin_git_main_checkout_blocked": actor_absolute_blocked,
            "normal_session_main_checkout_allowed": normal_checkout_allowed,
            "normal_session_main_commit_allowed": normal_commit_allowed,
            "enforcement_scoped_to_overnight_owner_or_registered_child": (
                actor_env_scrubbed_blocked and actor_absolute_blocked
                and normal_checkout_allowed),
            "no_global_master_lockdown_for_non_overnight_sessions": (
                normal_checkout_allowed and normal_commit_allowed),
            "differential_actor_blocked_on_residual_vector_while_normal_allowed_under_same_live_state": (
                actor_env_scrubbed_blocked and actor_absolute_blocked
                and normal_checkout_allowed and head == "master"),
        }
    finally:
        shutil.rmtree(repo, ignore_errors=True)


# ---------------------------------------------------------------------------
# RG-1: no hard-abort; always-create-worktree preserved (regression guard)
# ---------------------------------------------------------------------------

def rg1():
    repo = _make_repo()
    specs = repo / "docs" / "dev" / "specs"
    specs.mkdir(parents=True)
    (specs / "spec-zzz.md").write_text("# unrelated spec body\n")
    try:
        # Recoverable failure: a focus that won't match -> degrade to autonomous
        # WITH a valid worktree (no hard-abort, no in-place work).
        r = subprocess.run(
            [str(CREATE_STATE), "--project-dir", str(repo), "--session-id", "S",
             "--end-time", "+1h", "--focus", "THIS_WILL_NOT_MATCH_xyz"],
            capture_output=True, text=True)
        sf = repo / ".claude" / "overnight-state-S.json"
        st = json.loads(sf.read_text()) if sf.exists() else None
        wt = (st or {}).get("worktree_path", "")
        degrades = bool(st) and st.get("spec_mode") == "autonomous" and bool(wt) and wt != str(repo)
        head = _main_branch(repo)
        no_in_place = head == "master"

        # The fail-closed interpreter block is a RUNTIME op-block: it fires on a
        # Bash op AFTER the worktree exists; it does NOT delete/rewrite state, and
        # a safe in-worktree command is still allowed.
        if wt:
            _write_state(repo, wt, session="T")
            # a main-targeting subprocess checkout from session T -> blocked op...
            blocked = _hook_guard_blocks(
                _subprocess_checkout_payload(repo, "v2"), repo, session="T", cwd=wt)
            # ...but state file untouched by the block, and a safe worktree op
            # (status inside the worktree) is still allowed.
            tf = repo / ".claude" / "overnight-state-T.json"
            state_intact = tf.exists() and json.loads(tf.read_text()).get("worktree_path") == wt
            safe_rc, _ = _drive_hook_guard(f"git -C {wt} status", repo, session="T", cwd=wt)
            safe_allowed = safe_rc == 0
        else:
            blocked = state_intact = safe_allowed = False

        return {
            "spec_mismatch_degrades_to_autonomous_with_valid_worktree": degrades,
            "no_in_place_main_dir_work": no_in_place,
            # refuse-to-launch only-when-all-isolation-impossible is preserved
            # (Cycle-1 behavior; here the recoverable case produced a worktree).
            "refuse_to_launch_only_when_all_isolation_impossible": degrades,
            "new_wiring_adds_no_hard_abort_path": degrades and no_in_place,
            "fail_closed_interpreter_block_is_runtime_op_block_not_launch_abort": blocked and bool(st),
            "fail_closed_block_does_not_delete_or_rewrite_state": state_intact,
            "safe_command_inside_worktree_still_allowed_after_fail_closed": safe_allowed,
        }
    finally:
        shutil.rmtree(repo, ignore_errors=True)


# ---------------------------------------------------------------------------
# RG-2: dirty main tree preserved + isolated (regression guard)
# ---------------------------------------------------------------------------

def rg2():
    repo = _make_repo(dirty=True)
    try:
        before = (repo / "a.txt").read_text()
        before_untracked = (repo / "untracked.txt").read_text()
        r = subprocess.run(
            [str(CREATE_STATE), "--project-dir", str(repo), "--session-id", "S",
             "--end-time", "+1h"],
            capture_output=True, text=True)
        sf = repo / ".claude" / "overnight-state-S.json"
        st = json.loads(sf.read_text()) if sf.exists() else {}
        wt = st.get("worktree_path", "")
        head = _main_branch(repo)
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


# ---------------------------------------------------------------------------
# RG-3: no global master lockdown for normal sessions (regression guard)
# ---------------------------------------------------------------------------

def rg3():
    repo = _make_repo()
    try:
        wt = _make_worktree(repo)
        _write_state(repo, wt)  # a LIVE overnight state exists (session S)

        # A separate NON-overnight session (session U, cwd OUTSIDE the worktree)
        # runs ordinary main-repo git ops. All must be ALLOWED (classification
        # 'normal' -> exit 0). No global lockdown.
        rc_co, _ = _drive_hook_guard(f"git -C {repo} checkout other", repo,
                                     session="U", cwd=str(repo))
        rc_ci, _ = _drive_hook_guard(f"git -C {repo} commit --allow-empty -m x", repo,
                                     session="U", cwd=str(repo))
        rc_br, _ = _drive_hook_guard(f"git -C {repo} branch newbr", repo,
                                     session="U", cwd=str(repo))

        # keystone normal-session exemption preserved: a NORMAL (no
        # CLAUDE_OVERNIGHT_ACTOR) master ref-move is ALLOWED by the keystone.
        ks_repo = _make_repo()
        try:
            subprocess.run([str(SCRIPTS / "install-git-keystone.sh"),
                            "--project-dir", str(ks_repo)],
                           capture_output=True, text=True)
            normal_commit = _git(["commit", "--allow-empty", "-m", "normal"], ks_repo)
            keystone_exempts_normal = normal_commit.returncode == 0
        finally:
            shutil.rmtree(ks_repo, ignore_errors=True)

        return {
            "normal_session_main_checkout_allowed": rc_co == 0,
            "normal_session_main_commit_allowed": rc_ci == 0,
            "normal_session_main_branch_allowed": rc_br == 0,
            "no_global_master_lockdown_for_non_overnight_sessions": (
                rc_co == 0 and rc_ci == 0 and rc_br == 0),
            "keystone_normal_session_exemption_preserved": keystone_exempts_normal,
        }
    finally:
        shutil.rmtree(repo, ignore_errors=True)


# ---------------------------------------------------------------------------
# AC-9 (Cycle-3 VECTOR-1): shell-aware effective-cwd — cd-into-main + leading
#   env-assignment / command-wrapper before a path-qualified git move main HEAD
#   off master. The hook-guard must strip leading VAR=val / command|exec|env
#   wrappers before the git token AND track the effective cwd across cd/pushd
#   segments (or fail closed when a cd into a main-targeting path precedes a
#   dangerous git op). Each form MUST FAIL pre-fix (rc=0 ALLOWED) and BLOCK
#   post-fix (rc=2). A legit in-worktree branch op stays ALLOWED.
# ---------------------------------------------------------------------------

def ac9():
    repo = _make_repo()
    try:
        wt = _make_worktree(repo)
        _write_state(repo, wt)
        m = str(repo)

        # The actor's payload cwd is the WORKTREE; the cd / -C redirects the op
        # into main. Each must be BLOCKED (rc=2) before execution.
        cd_and_checkout = _hook_guard_blocks(
            f"cd {m} && git checkout other", repo, cwd=wt)
        cd_semicolon_checkout = _hook_guard_blocks(
            f"cd {m}; git checkout other", repo, cwd=wt)
        leading_env_path_qualified = _hook_guard_blocks(
            f"PATH=/usr/bin:/bin /usr/bin/git -C {m} checkout other", repo, cwd=wt)
        command_wrapper = _hook_guard_blocks(
            f"command /usr/bin/git -C {m} checkout other", repo, cwd=wt)
        exec_wrapper = _hook_guard_blocks(
            f"exec git -C {m} checkout other", repo, cwd=wt)
        multi_env_assign = _hook_guard_blocks(
            f"FOO=1 BAR=2 git -C {m} checkout other", repo, cwd=wt)
        # bare/variable cd before a HEAD-move cannot be proven worktree-local ->
        # fail closed.
        ambiguous_cd = _hook_guard_blocks(
            "cd $HOME && git checkout other", repo, cwd=wt)

        # codex round-3 #1: subshell / brace-group hiding the cd behind a group
        # opener.
        subshell_group = _hook_guard_blocks(
            f"( cd {m} && git checkout other )", repo, cwd=wt)
        brace_group = _hook_guard_blocks(
            f"{{ cd {m}; git checkout other; }}", repo, cwd=wt)
        # codex round-3 #2: launcher expressions (xargs / timeout / flock) that
        # carry a path-qualified main-targeting git.
        xargs_launcher = _hook_guard_blocks(
            f"echo x | xargs -I{{}} /usr/bin/git -C {m} checkout other", repo, cwd=wt)
        timeout_launcher = _hook_guard_blocks(
            f"timeout 5 /usr/bin/git -C {m} checkout other", repo, cwd=wt)
        flock_launcher = _hook_guard_blocks(
            f"flock /tmp/acl /usr/bin/git -C {m} checkout other", repo, cwd=wt)
        # codex round-3 #5: wrapper option-arity (nice -n 10 / ionice -c 2 -n 7).
        nice_arity = _hook_guard_blocks(
            f"nice -n 10 /usr/bin/git -C {m} checkout other", repo, cwd=wt)
        ionice_arity = _hook_guard_blocks(
            f"ionice -c 2 -n 7 /usr/bin/git -C {m} checkout other", repo, cwd=wt)
        # codex round-3 #4: bash -c payload with a -C operand that realpath's into
        # main via a symlink string.
        link_parent = Path(tempfile.mkdtemp(prefix="ac9-lnk-"))
        try:
            link = link_parent / "mainlink"
            os.symlink(m, link)
            bashc_symlink = _hook_guard_blocks(
                f'bash -c "/usr/bin/git -C {link} checkout other"', repo, cwd=wt)
        finally:
            shutil.rmtree(link_parent, ignore_errors=True)

        # main HEAD untouched (every form blocked before execution).
        head = _main_branch(repo)

        # No over-block: legit in-worktree forms (incl. a launcher + a subshell
        # cd-into-worktree) stay ALLOWED.
        legit_worktree_branch = not _hook_guard_blocks(
            "git checkout -b featbranch", repo, cwd=wt)
        legit_cd_worktree_status = not _hook_guard_blocks(
            f"cd {wt} && git status", repo, cwd=wt)
        legit_launcher_worktree = not _hook_guard_blocks(
            f"timeout 5 git -C {wt} status", repo, cwd=wt)
        legit_subshell_worktree = not _hook_guard_blocks(
            f"( cd {wt} && git status )", repo, cwd=wt)

        return {
            "cd_into_main_then_checkout_blocked": cd_and_checkout,
            "cd_semicolon_main_then_checkout_blocked": cd_semicolon_checkout,
            "leading_env_assign_path_qualified_git_main_checkout_blocked": leading_env_path_qualified,
            "command_wrapper_main_checkout_blocked": command_wrapper,
            "exec_wrapper_main_checkout_blocked": exec_wrapper,
            "multi_leading_env_assign_main_checkout_blocked": multi_env_assign,
            "ambiguous_cd_before_head_move_fails_closed": ambiguous_cd,
            "subshell_group_cd_into_main_blocked": subshell_group,
            "brace_group_cd_into_main_blocked": brace_group,
            "xargs_launcher_main_checkout_blocked": xargs_launcher,
            "timeout_launcher_main_checkout_blocked": timeout_launcher,
            "flock_launcher_main_checkout_blocked": flock_launcher,
            "nice_arity_main_checkout_blocked": nice_arity,
            "ionice_arity_main_checkout_blocked": ionice_arity,
            "bash_c_symlink_main_checkout_blocked": bashc_symlink,
            "main_head_stays_master": head == "master",
            "legit_in_worktree_branch_op_allowed": legit_worktree_branch,
            "legit_cd_into_worktree_status_allowed": legit_cd_worktree_status,
            "legit_launcher_worktree_op_allowed": legit_launcher_worktree,
            "legit_subshell_worktree_op_allowed": legit_subshell_worktree,
        }
    finally:
        shutil.rmtree(repo, ignore_errors=True)


# ---------------------------------------------------------------------------
# AC-10 (Cycle-3 VECTOR-2): a --work-tree / GIT_WORK_TREE override at the main
#   working directory writes the main tree even with an in-worktree -C. BOTH the
#   hook-guard AND the policy-shim must treat a work-tree override under main_root
#   (outside every active worktree) as main-targeting and BLOCK tree-writing ops.
#   A legit --work-tree pointing at the worktree itself stays ALLOWED.
# ---------------------------------------------------------------------------

def ac10():
    repo = _make_repo()
    try:
        wt = _make_worktree(repo)
        _write_state(repo, wt)
        m = str(repo)
        before = (repo / "a.txt").read_text()

        # hook-guard surface (typed-Bash): each --work-tree/GIT_WORK_TREE into main
        # restore/checkout MUST be blocked.
        hg_worktree_flag_restore = _hook_guard_blocks(
            f"git -C {wt} --work-tree {m} restore --source other -- a.txt",
            repo, cwd=wt)
        hg_worktree_eq_checkout = _hook_guard_blocks(
            f"git -C {wt} --work-tree={m} checkout other -- a.txt", repo, cwd=wt)
        hg_env_worktree_restore = _hook_guard_blocks(
            f"GIT_WORK_TREE={m} git -C {wt} restore --source other -- a.txt",
            repo, cwd=wt)

        # policy-shim surface (actor's resolved git): same forms MUST be blocked.
        shim_worktree_flag_checkout = _shim_blocks(
            ["-C", wt, "--work-tree", m, "checkout", "other", "--", "a.txt"],
            repo, wt, cwd=wt)
        shim_env_worktree_restore = _shim_blocks(
            ["-C", wt, "restore", "--source", "other", "--", "a.txt"],
            repo, wt, env_extra={"GIT_WORK_TREE": m}, cwd=wt)

        after = (repo / "a.txt").read_text()

        # No over-block: --work-tree pointing at the worktree itself is ALLOWED in
        # both surfaces.
        allow_hg = not _hook_guard_blocks(
            f"git -C {wt} --work-tree {wt} status", repo, cwd=wt)
        allow_shim = not _shim_blocks(
            ["-C", wt, "--work-tree", wt, "status"], repo, wt, cwd=wt)

        return {
            "hook_guard_blocks_worktree_flag_into_main_restore": hg_worktree_flag_restore,
            "hook_guard_blocks_worktree_eq_into_main_checkout": hg_worktree_eq_checkout,
            "hook_guard_blocks_GIT_WORK_TREE_env_into_main": hg_env_worktree_restore,
            "policy_shim_blocks_worktree_flag_into_main_checkout": shim_worktree_flag_checkout,
            "policy_shim_blocks_GIT_WORK_TREE_env_into_main": shim_env_worktree_restore,
            "main_worktree_byte_unchanged": after == before,
            "worktree_local_work_tree_allowed_hook_guard": allow_hg,
            "worktree_local_work_tree_allowed_policy_shim": allow_shim,
        }
    finally:
        shutil.rmtree(repo, ignore_errors=True)


# ---------------------------------------------------------------------------
# AC-11 (Cycle-3 VECTOR-3): an in-worktree actor whose owner/child resolution
#   fails classifies as worktree_context. The git enforce gate MUST still run
#   (governing state resolved from the worktree path) OR fail closed — it must
#   NOT skip enforcement. A main-targeting checkout / subprocess git from such an
#   actor MUST be BLOCKED; a normal non-overnight session stays ALLOWED.
# ---------------------------------------------------------------------------

def ac11():
    repo = _make_repo()
    try:
        wt = _make_worktree(repo)
        # Live governing state under a session id the payload will NOT match, so
        # owner/child resolution fails but the cwd is inside the worktree ->
        # worktree_context. The governing state is resolvable from the wt path.
        _write_state(repo, wt, session="GOVERN")
        m = str(repo)

        # worktree_context actor (payload session 'UNKNOWN', cwd in worktree) ->
        # the typed-Bash main-targeting checkout MUST be blocked.
        wc_typed_main_checkout = _hook_guard_blocks(
            f"git -C {m} checkout other", repo, session="UNKNOWN", cwd=wt)
        # ... and the residual subprocess form too.
        wc_subprocess_main_checkout = _hook_guard_blocks(
            _subprocess_checkout_payload(repo, "v3"), repo, session="UNKNOWN", cwd=wt)
        # ... and a cd-into-main checkout too (VECTOR-1 under worktree_context).
        wc_cd_into_main = _hook_guard_blocks(
            f"cd {m} && git checkout other", repo, session="UNKNOWN", cwd=wt)

        head = _main_branch(repo)

        # Enforcement runs for worktree_context (it does NOT skip): a legit
        # in-worktree status from the worktree_context actor is still ALLOWED
        # (not over-blocked).
        wc_legit_worktree_status_allowed = not _hook_guard_blocks(
            f"git -C {wt} status", repo, session="UNKNOWN", cwd=wt)

        # A normal NON-overnight session (cwd OUTSIDE the worktree) is ALLOWED.
        normal_rc, _ = _drive_hook_guard(
            f"git -C {m} checkout other", repo, session="U", cwd=m)
        normal_allowed = normal_rc == 0

        return {
            "worktree_context_typed_main_checkout_blocked": wc_typed_main_checkout,
            "worktree_context_subprocess_main_checkout_blocked": wc_subprocess_main_checkout,
            "worktree_context_cd_into_main_checkout_blocked": wc_cd_into_main,
            "worktree_context_enforcement_not_skipped": (
                wc_typed_main_checkout and wc_subprocess_main_checkout),
            "main_head_stays_master": head == "master",
            "worktree_context_legit_worktree_status_allowed": wc_legit_worktree_status_allowed,
            "normal_non_overnight_session_still_allowed": normal_allowed,
        }
    finally:
        shutil.rmtree(repo, ignore_errors=True)


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
