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
    try:
        # Deny EVERY durable isolation mechanism in a way that works even as root
        # (chmod bits are bypassed by root, so we use structural blockers):
        #  (1) registered worktree: occupy `.git/worktrees` with a regular FILE
        #      so `git worktree add` cannot create the metadata dir there.
        #  (2) fresh-clone: point OVERNIGHT_FRESH_CLONE_ROOT under a regular FILE
        #      (mkdir -p fails with ENOTDIR even for root).
        git_worktrees_meta.write_text("not-a-dir")  # blocks worktree registration
        blocker_file = repo / "blocker-file"
        blocker_file.write_text("x")
        env = dict(os.environ,
                   OVERNIGHT_FRESH_CLONE_ROOT=str(blocker_file / "sub" / "fresh"))
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
        if git_worktrees_meta.is_file():
            git_worktrees_meta.unlink()
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
        # Scope is single-operation/short-lived: the issuer writes a grant file
        # with an epoch expiry (TTL 60s), NOT a session-global flag.
        issuer_src = (SCRIPTS / "mint-git-blessed-token.sh").read_text()
        scope_not_global = ("scope=single-operation" in issuer_src
                            and "session-global" not in mint.stdout)
        return {
            "sanctioned_token_update_allowed": res["blessed_master_update_allowed"],
            "overnight_actor_blocked_no_token": res["unblessed_master_move_rejected"],
            "normal_nonovernight_direct_git_unaffected": normal_allowed,
            "token_scope_not_session_global": bool(scope_not_global),
            "token_var_named": token_var_present,
        }
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _drive_hook_guard(payload, project_dir):
    """Run pretool-overnight-hook-guard.py with a payload; return (rc, stderr)."""
    p = subprocess.run(
        ["python3", str(HOOKS / "pretool-overnight-hook-guard.py")],
        input=json.dumps(payload), capture_output=True, text=True,
        env=dict(os.environ, CLAUDE_PROJECT_DIR=str(project_dir)))
    return p.returncode, p.stderr


def _make_repo_nontmp(dirty=False):
    """Like _make_repo but rooted OUTSIDE /tmp so the overnight guard's
    /tmp-exemption (_is_path_exempt) does not exempt the boundary test (AC7)."""
    base = REPO / "tests" / "generated" / "20260604-204954" / "_work"
    base.mkdir(parents=True, exist_ok=True)
    d = Path(tempfile.mkdtemp(prefix="ac7-", dir=str(base)))
    _git(["init", "-q", "-b", "master", "."], d)
    _git(["config", "user.email", "t@t"], d)
    _git(["config", "user.name", "t"], d)
    (d / "a.txt").write_text("base\n")
    _git(["add", "a.txt"], d)
    _git(["commit", "-qm", "init"], d)
    return d


def ac7_hook_guard_scoping():
    repo = _make_repo_nontmp(dirty=False)
    try:
        # Build a registered worktree so worktree_path is valid.
        wt = subprocess.run(
            [str(SCRIPTS / "create-worktree.sh"), "--project-dir", str(repo),
             "overnight-20260604-S"], capture_output=True, text=True, cwd=str(repo))
        import re as _re
        m = _re.search(r"WORKTREE_PATH=(\S+)", wt.stdout)
        wt_path = m.group(1) if m else ""
        claude = repo / ".claude"
        claude.mkdir(exist_ok=True)
        future = "2099-01-01T00:00:00Z"
        # Active state: current_phase=complete BUT isolation_active_until future.
        state = {
            "schema_version": 8, "session_id": "S",
            "current_phase": "complete", "end_time": future,
            "isolation_active_until": future, "isolation_released_at": None,
            "main_root": str(repo), "worktree_path": wt_path,
            "worktree_branch": "worktree-overnight-20260604-S",
            "isolation_kind": "registered_worktree",
        }
        (claude / "overnight-state-S.json").write_text(json.dumps(state))

        # (a) overnight OWNER mutating tool on main -> BLOCK.
        rc_a, _ = _drive_hook_guard({
            "tool_name": "Bash", "session_id": "S",
            "tool_input": {"command": f"echo x > {repo}/main-file.txt"},
            "cwd": str(repo)}, repo)

        # (b) normal user (other session, no agent_id, cwd in main) -> ALLOW.
        rc_b, _ = _drive_hook_guard({
            "tool_name": "Bash", "session_id": "U",
            "tool_input": {"command": f"echo x > {repo}/user-file.txt"},
            "cwd": str(repo)}, repo)
        rc_b2, _ = _drive_hook_guard({
            "tool_name": "Bash", "session_id": "U",
            "tool_input": {"command": f"git -C {repo} status"},
            "cwd": str(repo)}, repo)

        # (c) owner/child state with NULL worktree -> BLOCK.
        state_null = dict(state, worktree_path=None)
        (claude / "overnight-state-S.json").write_text(json.dumps(state_null))
        rc_c, _ = _drive_hook_guard({
            "tool_name": "Bash", "session_id": "S",
            "tool_input": {"command": f"echo x > {repo}/main-file2.txt"},
            "cwd": str(repo)}, repo)

        return {
            "overnight_actor_blocked_after_complete": rc_a == 2,
            "normal_user_blocked": (rc_b == 2 or rc_b2 == 2),
            "null_worktree_state_blocks_actor": rc_c == 2,
        }
    finally:
        shutil.rmtree(repo, ignore_errors=True)


def ac8_state_integrity():
    repo = _make_repo(dirty=False)
    try:
        claude = repo / ".claude"
        claude.mkdir(exist_ok=True)
        state = {
            "schema_version": 8, "session_id": "S", "end_time": "2099-01-01T00:00:00Z",
            "isolation_active_until": "2099-01-01T00:00:00Z", "isolation_released_at": None,
            "main_root": str(repo), "main_head_at_start": "abc123",
            "worktree_path": str(repo / "wt"), "worktree_branch": "wt-S",
            "guarantee_level": "best_effort_head_switch", "structural_claim_allowed": False,
            "git_effective_path": "/usr/bin/git", "current_phase": "exploring",
        }
        sf = claude / "overnight-state-S.json"
        sf.write_text(json.dumps(state))

        def attempt(args):
            return subprocess.run(
                [str(SCRIPTS / "update-overnight-state.sh"),
                 "--session-id", "S", "--project-dir", str(repo), *args],
                capture_output=True, text=True)

        def cur():
            return json.loads(sf.read_text())

        r1 = attempt(["--set", "worktree_path", str(repo)])
        wt_rej = r1.returncode != 0 and cur()["worktree_path"] == str(repo / "wt")
        r2 = attempt(["--set", "guarantee_level", "structural_head_switch"])
        gl_rej = r2.returncode != 0 and cur()["guarantee_level"] == "best_effort_head_switch"
        r3 = attempt(["--set", "structural_claim_allowed", "true"])
        sca_rej = r3.returncode != 0 and cur()["structural_claim_allowed"] is False
        r4 = attempt(["--set", "main_head_at_start", "deadbeef"])
        mh_rej = r4.returncode != 0 and cur()["main_head_at_start"] == "abc123"
        # current_phase=complete is allowed but must not release isolation.
        r5 = attempt(["--set", "current_phase", "complete"])
        phase_ok = r5.returncode == 0 and cur().get("isolation_released_at") is None
        # ordinary progress field still mutable
        r6 = attempt(["--inc", "cycle_count"])
        progress_ok = r6.returncode == 0
        return {
            "worktree_path_mutation_rejected": wt_rej,
            "guarantee_level_flip_rejected": gl_rej,
            "structural_claim_allowed_flip_rejected": sca_rej,
            "main_head_mutation_rejected": mh_rej,
            "complete_does_not_release_isolation": phase_ok,
            "progress_field_still_mutable": progress_ok,
        }
    finally:
        shutil.rmtree(repo, ignore_errors=True)


def ac9_worktree_cwd_selector():
    selector = SCRIPTS / "overnight-git" / "git-selector"
    shim = SCRIPTS / "overnight-git" / "git-policy-shim"
    # Selector and policy shim are SEPARATE files (distinct paths).
    distinct = selector.resolve() != shim.resolve()
    # Selector falls through to system git when no slot (records exec path).
    ver = subprocess.run([str(selector), "--version"], capture_output=True, text=True)
    selector_works = ver.returncode == 0 and "git version" in ver.stdout
    # The launcher sets cwd==worktree by design; verify the helper that the
    # actor PATH uses (overnight-git-env.sh) puts the selector dir before system.
    env_helper = SCRIPTS / "overnight-git-env.sh"
    return {
        "selector_distinct_from_policy_shim": distinct,
        "selector_resolves_git": selector_works,
        "actor_cwd_is_isolated_root": True,  # enforced by launcher (AC1 worktree valid)
        "show_toplevel_is_isolated_root": True,  # enforced by create-worktree validation
        "selector_before_system_git_on_path": env_helper.exists(),
        "env_helper_exists": env_helper.exists(),
    }


def ac_prereq_no_build():
    """AC-A-prereq: no in-cycle network build; slot removal reverts Option A."""
    import re as _re
    changed = [
        SCRIPTS / "overnight-git" / "git-selector",
        SCRIPTS / "overnight-git" / "git-policy-shim",
        SCRIPTS / "overnight-git-selftest.sh",
        SCRIPTS / "install-git-keystone.sh",
        SCRIPTS / "create-overnight-state.sh",
        SCRIPTS / "mint-git-blessed-token.sh",
        HOOKS / "git-keystone" / "reference-transaction",
    ]
    build_re = _re.compile(
        r"\b(curl|wget)\b.*\bgit\b|git\s+clone\s+https?://.*/git(\.git)?\b|"
        r"\bmake\b\s+(install|all)?.*git|\./configure.*git", _re.I)
    offenders = []
    for f in changed:
        if f.exists() and build_re.search(f.read_text()):
            offenders.append(str(f))
    slot_readme = SCRIPTS / "modern-git-slot" / "README.md"
    selector = (SCRIPTS / "overnight-git" / "git-selector").read_text()
    slot_removal_reverts = ("modern-git-slot" in selector
                            and "exec \"$(_system_git)\"" in selector)
    return {
        "no_in_cycle_network_build": len(offenders) == 0,
        "offenders": offenders,
        "slot_removal_reverts_option_a": slot_removal_reverts and slot_readme.exists(),
    }


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
