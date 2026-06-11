#!/usr/bin/env python3
"""One-shot: fill the remaining generated skeleton tests with real bodies that
call ac_harness, preserving AC_UID/AC_TYPE/function-name/docstring verbatim and
removing only the TEST_INCOMPLETE sentinel. Idempotent: skips already-filled
files (no pytest.fail sentinel present)."""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))

IMPORT_BLOCK = (
    "import os\n"
    "import sys\n"
    "\n"
    "import pytest\n"
    "\n"
    "sys.path.insert(0, os.path.dirname(__file__))\n"
    "import ac_harness  # noqa: E402\n"
)

# Map test filename -> (func_name, body_lines)
SPECS = {
    "test_AC2_b9cd5709e51167a6.py": ("test_AC2", [
        "    r = ac_harness.ac2_spec_mismatch_degrades()",
        "    assert r['exit_code'] == 0, r",
        "    assert r['state.spec_mode'] == 'autonomous', r",
        "    assert r['main_branch'] == 'master', r",
        "    assert r['worktree_valid'] is True, r",
    ]),
    "test_AC3a_8216dc10e4dac0ec.py": ("test_AC3a", [
        "    r = ac_harness.ac3a_recovery_ladder_fresh_clone()",
        "    assert r['exit_code'] == 0, r",
        "    assert r['state.isolation_kind'] in ('registered_worktree', 'fresh_clone_checkout'), r",
        "    assert r['launch_refused'] is False, r",
    ]),
    "test_AC3b_76aae39049bf6c1d.py": ("test_AC3b", [
        "    r = ac_harness.ac3b_refuse_when_no_isolation_possible()",
        "    assert r['state_file_written'] is False, r",
        "    assert r['main_branch'] == 'master', r",
        "    assert r['command_spec_injected'] is False, r",
        "    assert r['no_null_or_mainroot_worktree'] is True, r",
    ]),
    "test_AC4_2f9bf3e5db1cdb49.py": ("test_AC4", [
        "    # AC4 is a source-level contract on prompt-workflow.py: timeout >=60,",
        "    # fail-closed (raise SystemExit), no EnterWorktree, partial cleanup.",
        "    import pathlib",
        "    src = (pathlib.Path(ac_harness.HOOKS) / 'prompt-workflow.py').read_text()",
        "    assert 'timeout=60' in src, 'state-script timeout must be >=60s'",
        "    assert 'raise SystemExit(2)' in src, 'dev-overnight launch must fail closed'",
        "    assert '_cleanup_overnight_partials' in src, 'partial todo/bookmark cleaned'",
        "    assert 'Call EnterWorktree' not in src.split('def _build_worktree_instruction')[1].split('def ')[0], 'no EnterWorktree prompt'",
        "    assert 'except SystemExit' in src, 'main() must not swallow launch failure into exit(0)'",
    ]),
    "test_AC6_10c3021230a37303.py": ("test_AC6", [
        "    r = ac_harness.ac6_keystone()",
        "    assert r['install_rc'] == 0, r",
        "    assert r['unblessed_master_move_rejected'] is True, r",
        "    assert r['blessed_master_update_allowed'] is True, r",
        "    assert r['rehomed_pre_commit_fires'] is True, r",
        "    assert r['rehomed_post_commit_fires'] is True, r",
    ]),
    "test_AC7_c21a8a3c7ad7a644.py": ("test_AC7", [
        "    r = ac_harness.ac7_hook_guard_scoping()",
        "    assert r['overnight_actor_blocked_after_complete'] is True, r",
        "    assert r['normal_user_blocked'] is False, r",
        "    assert r['null_worktree_state_blocks_actor'] is True, r",
    ]),
    "test_AC8_e48503d9ff3f0e8b.py": ("test_AC8", [
        "    r = ac_harness.ac8_state_integrity()",
        "    assert r['worktree_path_mutation_rejected'] is True, r",
        "    assert r['guarantee_level_flip_rejected'] is True, r",
        "    assert r['structural_claim_allowed_flip_rejected'] is True, r",
        "    assert r['complete_does_not_release_isolation'] is True, r",
    ]),
    "test_AC9_4c339b355e923f8b.py": ("test_AC9", [
        "    r = ac_harness.ac9_worktree_cwd_selector()",
        "    assert r['actor_cwd_is_isolated_root'] is True, r",
        "    assert r['show_toplevel_is_isolated_root'] is True, r",
        "    assert r['selector_before_system_git_on_path'] is True, r",
        "    assert r['selector_distinct_from_policy_shim'] is True, r",
    ]),
    "test_AC10_128e1d3f57c24067.py": ("test_AC10", [
        "    r = ac_harness.ac10_blessed_token_scoping()",
        "    assert r['sanctioned_token_update_allowed'] is True, r",
        "    assert r['overnight_actor_blocked_no_token'] is True, r",
        "    assert r['normal_nonovernight_direct_git_unaffected'] is True, r",
        "    assert r['token_scope_not_session_global'] is True, r",
    ]),
    "test_AC11_7bfb0c8e652993a6.py": ("test_AC11", [
        "    r = ac_harness.ac11_branch_switch_blocked()",
        "    assert r['bare_git_branch_switch_blocked'] is True, r",
        "    assert r['usr_bin_git_checkout_blocked'] is True, r",
        "    assert r['git_core_libexec_git_checkout_blocked'] is True, r",
        "    assert r['main_head_stays_master'] is True, r",
    ]),
    "test_AC-A-neg-current-host_47071655abea3bcc.py": ("test_AC_A_neg_current_host", [
        "    r = ac_harness.ac_neg_current_host()",
        "    assert r['isolation_created'] is True, r",
        "    assert r['state.guarantee_level'] == 'best_effort_head_switch', r",
        "    assert r['state.structural_claim_allowed'] is False, r",
        "    assert r['launch_refused_for_git_version'] is False, r",
        "    assert r['ac11_all_blocked'] is True, r",
    ]),
    "test_AC-A-prereq_546a4b438172386d.py": ("test_AC_A_prereq", [
        "    r = ac_harness.ac_prereq_no_build()",
        "    assert r['no_in_cycle_network_build'] is True, r",
        "    assert r['slot_removal_reverts_option_a'] is True, r",
    ]),
    "test_AC-A-pos_92dabc1af2799f5e.py": ("test_AC_A_pos", [
        "    # CONDITIONAL / fixture-gated: structural mode requires an operator-",
        "    # provided pinned git >=2.46 full distribution at the configured slot.",
        "    # On THIS host (git 2.43.0, no slot) the precondition is UNMET, so this",
        "    # AC is precondition-SKIPPED (NOT failed), per the AC runnability gate.",
        "    import shutil, subprocess",
        "    slot = os.environ.get('CLAUDE_MODERN_GIT_SLOT', '')",
        "    has_slot = bool(slot) and os.path.exists(os.path.join(slot, 'bin', 'git'))",
        "    if not has_slot:",
        "        pytest.skip('precondition unmet: no pinned git>=2.46 full distribution at the configured slot (current host)')",
        "    # Fixture present: run the self-test and assert structural claim.",
        "    out = subprocess.run(['bash', str(ac_harness.SCRIPTS / 'overnight-git-selftest.sh'),",
        "                          '--project-dir', str(ac_harness.REPO)],",
        "                         capture_output=True, text=True)",
        "    line = [x for x in out.stdout.splitlines() if x.startswith('SELFTEST_JSON=')]",
        "    import json as _json",
        "    data = _json.loads(line[0][len('SELFTEST_JSON='):]) if line else {}",
        "    assert data.get('guarantee_level') == 'structural_head_switch', data",
        "    assert data.get('structural_claim_allowed') is True, data",
    ]),
}


def patch(fname, func, body):
    path = os.path.join(HERE, fname)
    text = open(path).read()
    if "TEST_INCOMPLETE" not in text and "pytest.fail" not in text:
        print("skip (already filled):", fname)
        return
    # Insert import block after the first "import pytest" stanza.
    if "import ac_harness" not in text:
        text = re.sub(r"\nimport pytest\n", "\n" + IMPORT_BLOCK, text, count=1)
    # Replace the sentinel block (everything from the TODO comment to the
    # pytest.fail call) with the real body.
    lines = text.splitlines()
    out = []
    skip = False
    for ln in lines:
        if ln.strip().startswith("# TODO(dev): replace"):
            skip = True
            out.extend(body)
            continue
        if skip:
            # the sentinel spans the comment lines + the pytest.fail line
            if ln.strip().startswith("pytest.fail("):
                skip = False
            continue
        out.append(ln)
    open(path, "w").write("\n".join(out) + "\n")
    print("filled:", fname)


for fn, (func, body) in SPECS.items():
    patch(fn, func, body)
print("done")
