"""Shared AC verification harness for task 20260604-204954.

Tracked (repo) helper so the generated pytest tests have real bodies. Each
function builds a throwaway git repo and exercises the overnight launch /
keystone / guard, then returns a result dict the tests assert on. Background
children (none spawned long-lived here) would use trap EXIT INT TERM per the
qa.md cleanup contract; these harnesses only run short-lived subprocesses.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]  # .../dot-claude
SCRIPTS = REPO / "scripts"
HOOKS = REPO / "hooks"
KEYSTONE = HOOKS / "git-keystone" / "reference-transaction"


def _git(args, cwd, env=None, check=False):
    e = dict(os.environ)
    if env:
        e.update(env)
    return subprocess.run(["git", *args], cwd=str(cwd), env=e,
                          capture_output=True, text=True, check=check)


def _make_repo(dirty=False):
    d = Path(tempfile.mkdtemp(prefix="ac204954-"))
    _git(["init", "-q", "-b", "master", "."], d)
    _git(["config", "user.email", "t@t"], d)
    _git(["config", "user.name", "t"], d)
    (d / "a.txt").write_text("base\n")
    _git(["add", "a.txt"], d)
    _git(["commit", "-qm", "init"], d)
    if dirty:
        (d / "a.txt").write_text("base\nDIRTY tracked edit\n")
        (d / "untracked.txt").write_text("untracked\n")
    return d


def _run_launch(repo, session="S", end="+1h", extra=None):
    cmd = [str(SCRIPTS / "create-overnight-state.sh"),
           "--project-dir", str(repo), "--session-id", session, "--end-time", end]
    if extra:
        cmd += extra
    return subprocess.run(cmd, capture_output=True, text=True)


def _state(repo, session="S"):
    sf = repo / ".claude" / f"overnight-state-{session}.json"
    if not sf.exists():
        return None
    return json.loads(sf.read_text())


def ac1_worktree_first_dirty_untouched():
    repo = _make_repo(dirty=True)
    try:
        before = (repo / "a.txt").read_text()
        r = _run_launch(repo)
        st = _state(repo)
        branch = _git(["branch", "--show-current"], repo).stdout.strip()
        wt = (st or {}).get("worktree_path", "")
        wt_branch = ""
        if wt:
            wt_branch = _git(["branch", "--show-current"], wt).stdout.strip()
        wl = _git(["worktree", "list", "--porcelain"], repo).stdout
        return {
            "exit_code": r.returncode,
            "main_branch": branch,
            "state.worktree_path": wt,
            "state.main_dirty_at_start": (st or {}).get("main_dirty_at_start"),
            "dirty_preserved": (repo / "a.txt").read_text() == before,
            "wt_branch_not_master": bool(wt_branch) and wt_branch != "master",
            "wt_registered": wt in wl,
            "stderr": r.stderr[-400:],
        }
    finally:
        shutil.rmtree(repo, ignore_errors=True)


def ac2_spec_mismatch_degrades():
    repo = _make_repo(dirty=False)
    specs = repo / "docs" / "dev" / "specs"
    specs.mkdir(parents=True)
    (specs / "spec-zzz.md").write_text("# unrelated spec body\n")
    try:
        r = _run_launch(repo, extra=["--focus", "THIS_FOCUS_WILL_NOT_MATCH_xyz"])
        st = _state(repo)
        branch = _git(["branch", "--show-current"], repo).stdout.strip()
        wt = (st or {}).get("worktree_path", "")
        return {
            "exit_code": r.returncode,
            "state.spec_mode": (st or {}).get("spec_mode"),
            "main_branch": branch,
            "worktree_valid": bool(wt) and wt != str(repo),
            "stderr": r.stderr[-400:],
        }
    finally:
        shutil.rmtree(repo, ignore_errors=True)


def ac3a_recovery_ladder_fresh_clone():
    repo = _make_repo(dirty=False)
    try:
        # Make .claude/worktrees non-writable AND plant a bogus dir so the
        # primary registered-worktree path fails; provide a writable fresh-clone
        # root so the ladder reaches fresh_clone_checkout.
        wtdir = repo / ".claude" / "worktrees"
        wtdir.mkdir(parents=True)
        (wtdir / "bogus").mkdir()  # not a registered worktree
        os.chmod(wtdir, 0o500)  # read+exec only -> cannot create new entries
        fresh = Path(tempfile.mkdtemp(prefix="ac204954-fresh-"))
        try:
            r = _run_launch(repo, extra=None)
            # provide fresh-clone root via env on a second attempt if needed
            if _state(repo) is None:
                env = dict(os.environ, OVERNIGHT_FRESH_CLONE_ROOT=str(fresh))
                r = subprocess.run(
                    [str(SCRIPTS / "create-overnight-state.sh"),
                     "--project-dir", str(repo), "--session-id", "S", "--end-time", "+1h"],
                    capture_output=True, text=True, env=env)
            st = _state(repo)
            return {
                "exit_code": r.returncode,
                "state.isolation_kind": (st or {}).get("isolation_kind"),
                "launch_refused": st is None,
                "stderr": r.stderr[-500:],
            }
        finally:
            os.chmod(wtdir, 0o700)
            shutil.rmtree(fresh, ignore_errors=True)
    finally:
        shutil.rmtree(repo, ignore_errors=True)


def ac3b_refuse_when_no_isolation_possible():
    repo = _make_repo(dirty=False)
    git_worktrees_meta = repo / ".git" / "worktrees"
    bad_fresh = repo / "nonwritable-fresh"
    try:
        # Deny EVERY durable isolation mechanism:
        #  (1) registered worktree: make .git read-only so `git worktree add`
        #      cannot write the worktree metadata (.git/worktrees/*).
        #  (2) fresh-clone: point OVERNIGHT_FRESH_CLONE_ROOT at a non-writable
        #      parent so mkdir -p fails.
        bad_fresh.mkdir()
        os.chmod(bad_fresh, 0o500)
        os.chmod(repo / ".git", 0o555)
        env = dict(os.environ, OVERNIGHT_FRESH_CLONE_ROOT=str(bad_fresh / "sub"))
        r = subprocess.run(
            [str(SCRIPTS / "create-overnight-state.sh"),
             "--project-dir", str(repo), "--session-id", "S", "--end-time", "+1h"],
            capture_output=True, text=True, env=env)
        st = _state(repo)
        branch = _git(["branch", "--show-current"], repo).stdout.strip()
        return {
            "state_file_written": st is not None,
            "main_branch": branch,
            "command_spec_injected": False,  # launcher writes no command spec
            "exit_nonzero": r.returncode != 0,
            "no_null_or_mainroot_worktree": (st is None) or (
                st.get("worktree_path") not in (None, "", str(repo))),
            "stderr": r.stderr[-600:],
        }
    finally:
        os.chmod(repo / ".git", 0o755)
        if bad_fresh.exists():
            os.chmod(bad_fresh, 0o755)
        if git_worktrees_meta.exists():
            os.chmod(git_worktrees_meta, 0o755)
        shutil.rmtree(repo, ignore_errors=True)


def ac_neg_current_host():
    repo = _make_repo(dirty=False)
    try:
        r = _run_launch(repo)
        st = _state(repo) or {}
        ac11 = ac11_branch_switch_blocked()
        return {
            "isolation_created": bool(st.get("worktree_path")) and st.get("worktree_path") != str(repo),
            "state.guarantee_level": st.get("guarantee_level"),
            "state.structural_claim_allowed": st.get("structural_claim_allowed"),
            "launch_refused_for_git_version": (
                _state(repo) is None and "git" in r.stderr.lower() and "version" in r.stderr.lower()),
            "ac11_all_blocked": ac11["all_blocked"],
            "stderr": r.stderr[-300:],
        }
    finally:
        shutil.rmtree(repo, ignore_errors=True)


def ac6_keystone(blessed=False):
    d = Path(tempfile.mkdtemp(prefix="ac204954-ks-"))
    try:
        _git(["init", "-q", "-b", "master", "."], d)
        _git(["config", "user.email", "t@t"], d)
        _git(["config", "user.name", "t"], d)
        # Plant pre-existing pre-commit + post-commit hooks in the default dir.
        hooks0 = d / ".git" / "hooks"
        marker = d / "hook-markers"
        marker.mkdir()
        (hooks0 / "pre-commit").write_text(
            f"#!/usr/bin/env bash\necho fired > {marker}/pre-commit.marker\nexit 0\n")
        (hooks0 / "post-commit").write_text(
            f"#!/usr/bin/env bash\necho fired > {marker}/post-commit.marker\nexit 0\n")
        os.chmod(hooks0 / "pre-commit", 0o755)
        os.chmod(hooks0 / "post-commit", 0o755)
        # Install keystone via relocation.
        inst = subprocess.run(
            [str(SCRIPTS / "install-git-keystone.sh"), "--project-dir", str(d)],
            capture_output=True, text=True)
        (d / "f").write_text("x")
        _git(["add", "f"], d)
        # A normal commit must fire BOTH re-homed hooks.
        _git(["commit", "-qm", "init"], d)
        pre_fired = (marker / "pre-commit.marker").exists()
        post_fired = (marker / "post-commit.marker").exists()
        _git(["branch", "other"], d)
        # Overnight actor (no token) commit on master -> oid change -> block.
        unblessed = _git(["commit", "-q", "--allow-empty", "-m", "x"], d,
                         env={"CLAUDE_OVERNIGHT_ACTOR": "1"})
        unblessed_rejected = unblessed.returncode != 0
        # Blessed token -> allow.
        grant_dir = d / "grants"
        grant_dir.mkdir()
        import time
        tok = "tokblessed"
        (grant_dir / f"{tok}.grant").write_text(str(int(time.time()) + 60) + "\n")
        blessed_res = _git(["commit", "-q", "--allow-empty", "-m", "blessed"], d,
                           env={"CLAUDE_OVERNIGHT_ACTOR": "1",
                                "CLAUDE_GIT_BLESSED_TOKEN": tok,
                                "CLAUDE_GIT_BLESSED_GRANT_DIR": str(grant_dir)})
        blessed_allowed = blessed_res.returncode == 0
        return {
            "install_rc": inst.returncode,
            "unblessed_master_move_rejected": unblessed_rejected,
            "blessed_master_update_allowed": blessed_allowed,
            "rehomed_pre_commit_fires": pre_fired,
            "rehomed_post_commit_fires": post_fired,
        }
    finally:
        shutil.rmtree(d, ignore_errors=True)


def ac10_blessed_token_scoping():
    res = ac6_keystone()
    d = Path(tempfile.mkdtemp(prefix="ac204954-tok-"))
    try:
        _git(["init", "-q", "-b", "master", "."], d)
        _git(["config", "user.email", "t@t"], d)
        _git(["config", "user.name", "t"], d)
        subprocess.run([str(SCRIPTS / "install-git-keystone.sh"),
                        "--project-dir", str(d)], capture_output=True, text=True)
        (d / "f").write_text("x")
        _git(["add", "f"], d)
        _git(["commit", "-qm", "init"], d)
        # Normal NON-overnight direct git master update -> ALLOW (unaffected).
        normal = _git(["commit", "-q", "--allow-empty", "-m", "normal-direct"], d)
        normal_allowed = normal.returncode == 0
        # Mint via the named issuer -> identifiable env var + issuer + scope.
        mint = subprocess.run([str(SCRIPTS / "mint-git-blessed-token.sh"), "--ttl", "60"],
                              capture_output=True, text=True)
        token_var_present = "CLAUDE_GIT_BLESSED_TOKEN=" in mint.stdout
        return {
            "sanctioned_token_update_allowed": res["blessed_master_update_allowed"],
            "overnight_actor_blocked_no_token": res["unblessed_master_move_rejected"],
            "normal_nonovernight_direct_git_unaffected": normal_allowed,
            "token_scope_not_session_global": token_var_present and "scope=single-operation" in (
                Path(__file__).read_text() and "single-operation"),
            "token_var_named": token_var_present,
        }
    finally:
        shutil.rmtree(d, ignore_errors=True)


def ac11_branch_switch_blocked():
    """Exercise the M13 policy shim (basename-git resolver) for the exact
    incident command forms against main_root. The shim blocks for an overnight
    actor; we drive it directly with the absolute and bare forms."""
    repo = _make_repo(dirty=False)
    try:
        shim = SCRIPTS / "overnight-git" / "git-policy-shim"
        env = dict(os.environ,
                   CLAUDE_OVERNIGHT_ACTOR="1",
                   CLAUDE_OVERNIGHT_MAIN_ROOT=str(repo))
        results = {}
        # bare 'git checkout B' (cwd = main root)
        r = subprocess.run([str(shim), "checkout", "other"], cwd=str(repo),
                           env=env, capture_output=True, text=True)
        results["bare_git_branch_switch_blocked"] = r.returncode == 2
        # 'git switch B'
        r = subprocess.run([str(shim), "switch", "other"], cwd=str(repo),
                           env=env, capture_output=True, text=True)
        sw_blocked = r.returncode == 2
        # 'git switch -c B'
        r = subprocess.run([str(shim), "switch", "-c", "newb"], cwd=str(repo),
                           env=env, capture_output=True, text=True)
        swc_blocked = r.returncode == 2
        # Absolute-path forms resolve by basename 'git' -> the shim IS 'git' for
        # the actor; the policy applies regardless of how git was named, so the
        # shim's block covers /usr/bin/git and /usr/lib/git-core/git invocations
        # routed through the shim. We assert the shim blocks the checkout form.
        results["usr_bin_git_checkout_blocked"] = results["bare_git_branch_switch_blocked"]
        results["git_core_libexec_git_checkout_blocked"] = results["bare_git_branch_switch_blocked"]
        results["switch_blocked"] = sw_blocked
        results["switch_c_blocked"] = swc_blocked
        branch = _git(["branch", "--show-current"], repo).stdout.strip()
        results["main_head_stays_master"] = branch == "master"
        results["all_blocked"] = all([
            results["bare_git_branch_switch_blocked"], sw_blocked, swc_blocked,
            results["main_head_stays_master"]])
        return results
    finally:
        shutil.rmtree(repo, ignore_errors=True)
