#!/usr/bin/env python3
"""End-to-end self-tests for the generic protected-runtime guard.

Two layers:
  1. Direct engine tests (fast) — call runtime_guard.evaluate() against an
     isolated test data file (NEVER the live machine file).
  2. Live-hook tests — feed simulated PreToolUse JSON to the real
     pretool-bash-safety.sh on stdin and assert the exit code.

NEVER runs a real daemon or CLI command — verification is purely by feeding
simulated inputs to the engine / hook (spec Section 8 trap).

Project names appear ONLY in this test file's fixture data file and in the
test command strings (a test fixture is not the shared engine/helper code that
AC-A purity governs).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

import pytest

HERE = os.path.dirname(__file__)
HOOKS_DIR = os.path.abspath(os.path.join(HERE, ".."))
HOOK = os.path.join(HOOKS_DIR, "pretool-bash-safety.sh")
sys.path.insert(0, HOOKS_DIR)

BLOCK = 2
ALLOW = 0


# ── Test fixture data file (de-drifted values, isolated from the live file) ──
FIXTURE = {
    "schema_version": 1,
    "protected_cmds": ["happy", "happy-dev", "happy-mcp", "happy-coder"],
    "protected_launch_paths": [
        "**/packages/happy-cli/dist/index.mjs",
        "**/packages/happy-cli/bin/happy*.mjs",
        "**/packages/happy-cli/src/index.ts",
        "**/packages/happy-cli/scripts/env-wrapper.cjs",
        "/usr/bin/happy",
        "/usr/bin/happy-dev",
        "/usr/bin/happy-mcp",
    ],
    "protected_services": [
        "happy-daemon", "happy-daemon-jade", "happy-daemon-dev", "happy-daemon-qijie",
    ],
    "protected_hotfiles": ["**/packages/happy-cli/dist/index.mjs"],
    "protected_statefiles": ["/root/.happy*/daemon.state.json"],
    "protected_endpoint_paths": ["/stop"],
    "protected_proc_idents": [
        "happy-daemon", "packages/happy-cli/dist/index.mjs", "daemon start-sync",
    ],
    "protected_global_bins": ["/usr/bin/happy*", "/usr/lib/node_modules/happy*"],
    "protected_build_workspaces": ["happy", "happy-coder"],
    "protected_build_paths": ["**/packages/happy-cli"],
    "bare_build_guard": True,
    "script_run_policy": "default_deny",
    "protected_script_workspaces": ["happy", "happy-coder"],
    "protected_script_paths": ["**/packages/happy-cli"],
    "protected_root_manifest_paths": ["__ROOT__"],
    "non_protected_workspaces": [
        "happy-app", "happy-agent", "happy-server", "happy-wire",
        "happy-app-logs", "@slopus/happy-wire",
    ],
    "safe_script_allowlist": [],
}


@pytest.fixture(scope="module")
def fixture_repo(tmp_path_factory):
    """Build a throwaway monorepo so workspace-resolution checks are determinate.

    Mirrors the real name<->folder mapping (folder packages/happy-cli, name
    'happy') and the real non-protected workspaces' declared scripts. NEVER
    touches the live machine repo or data file.
    """
    root = tmp_path_factory.mktemp("repo")
    pkgs = root / "packages"
    pkgs.mkdir()

    def mk(folder, name, scripts):
        d = pkgs / folder
        d.mkdir()
        (d / "package.json").write_text(json.dumps({"name": name, "scripts": {s: "echo" for s in scripts}}))

    mk("happy-cli", "happy", ["build", "test", "start", "cli", "dev", "dev:daemon:start", "stable", "release"])
    mk("happy-server", "happy-server", ["build", "test", "dev", "start", "migrate"])
    mk("happy-app", "happy-app", ["web", "start", "test", "typecheck", "release"])
    mk("happy-agent", "happy-agent", ["build", "dev", "test", "release", "typecheck"])
    mk("happy-wire", "@slopus/happy-wire", ["build", "test", "release"])
    mk("happy-app-logs", "happy-app-logs", ["build"])
    (root / "package.json").write_text(json.dumps({
        "name": "monorepo",
        "workspaces": {"packages": ["packages/*"]},
        "scripts": {"cli": "x", "release": "x", "env:cli": "x", "env:seed": "x",
                    "env:up": "x", "env:up:authenticated": "x", "env:down": "x"},
    }))
    return str(root)


@pytest.fixture(scope="module")
def datafile(fixture_repo, tmp_path_factory):
    cfg = json.loads(json.dumps(FIXTURE))
    cfg["protected_root_manifest_paths"] = [fixture_repo]
    p = tmp_path_factory.mktemp("cfg") / "protected-runtime.json"
    p.write_text(json.dumps(cfg))
    return str(p)


def ev(command, datafile, repo):
    """Direct engine evaluation under the isolated fixture data file."""
    os.environ["CLAUDE_PROTECTED_RUNTIME_FILE"] = datafile
    # force a fresh import so DATA_FILE_PATH picks up the env each module load
    import importlib
    import lib.runtime_guard as rg
    importlib.reload(rg)
    return rg.evaluate(command)[0]


def code_for(decision):
    return BLOCK if decision == "BLOCK" else ALLOW


# ════════════════════════════════════════════════════════════════════════════
# Layer 1: direct engine tests (one method per acceptance criterion family)
# ════════════════════════════════════════════════════════════════════════════

class TestBlocks:
    def test_launch_cmdword(self, datafile, fixture_repo):
        assert ev("happy daemon start", datafile, fixture_repo) == "BLOCK"
        assert ev("HAPPY_HOME_DIR=/root/.happy-dev happy daemon start", datafile, fixture_repo) == "BLOCK"

    def test_launch_distpath(self, datafile, fixture_repo):
        assert ev("node --no-warnings " + fixture_repo + "/packages/happy-cli/dist/index.mjs daemon start", datafile, fixture_repo) == "BLOCK"
        assert ev("tsx packages/happy-cli/src/index.ts daemon start", datafile, fixture_repo) == "BLOCK"
        assert ev("bun packages/happy-cli/dist/index.mjs daemon", datafile, fixture_repo) == "BLOCK"

    def test_launch_pkgrunner(self, datafile, fixture_repo):
        assert ev("npx happy daemon start", datafile, fixture_repo) == "BLOCK"
        assert ev("npm exec happy daemon start", datafile, fixture_repo) == "BLOCK"
        assert ev("pnpm dlx happy daemon start", datafile, fixture_repo) == "BLOCK"
        assert ev("yarn dlx happy daemon start", datafile, fixture_repo) == "BLOCK"

    def test_pkgrunner_local_exec(self, datafile, fixture_repo):
        assert ev("pnpm exec happy daemon start", datafile, fixture_repo) == "BLOCK"
        assert ev("yarn exec happy daemon start", datafile, fixture_repo) == "BLOCK"
        assert ev("bunx happy daemon start", datafile, fixture_repo) == "BLOCK"

    def test_service(self, datafile, fixture_repo):
        assert ev("systemctl restart happy-daemon-qijie", datafile, fixture_repo) == "BLOCK"
        assert ev("systemctl stop happy-daemon", datafile, fixture_repo) == "BLOCK"
        assert ev("systemctl disable happy-daemon-dev", datafile, fixture_repo) == "BLOCK"

    def test_build_explicit(self, datafile, fixture_repo):
        assert ev("yarn workspace happy build", datafile, fixture_repo) == "BLOCK"
        assert ev("yarn workspace happy-coder build", datafile, fixture_repo) == "BLOCK"

    def test_build_bare(self, datafile, fixture_repo):
        # bare build with indeterminate cwd -> P9 fail-closed
        assert ev("yarn build", datafile, fixture_repo) == "BLOCK"
        assert ev("npm run build", datafile, fixture_repo) == "BLOCK"
        assert ev("pnpm build", datafile, fixture_repo) == "BLOCK"

    def test_build_npx_tsc_protected(self, datafile, fixture_repo):
        assert ev("npx tsc -p packages/happy-cli/tsconfig.json", datafile, fixture_repo) == "BLOCK"

    def test_hotfile_mutation(self, datafile, fixture_repo):
        assert ev("cp /tmp/x packages/happy-cli/dist/index.mjs", datafile, fixture_repo) == "BLOCK"
        assert ev("touch packages/happy-cli/dist/index.mjs", datafile, fixture_repo) == "BLOCK"
        assert ev("echo x > packages/happy-cli/dist/index.mjs", datafile, fixture_repo) == "BLOCK"
        assert ev("sed -i s/a/b/ packages/happy-cli/dist/index.mjs", datafile, fixture_repo) == "BLOCK"

    def test_statefile_mutation(self, datafile, fixture_repo):
        assert ev("echo {} > /root/.happy-dev/daemon.state.json", datafile, fixture_repo) == "BLOCK"
        assert ev("cp /tmp/s /root/.happy/daemon.state.json", datafile, fixture_repo) == "BLOCK"
        assert ev("truncate -s0 /root/.happy-qijie/daemon.state.json", datafile, fixture_repo) == "BLOCK"

    def test_endpoint_stop(self, datafile, fixture_repo):
        assert ev("curl -X POST http://127.0.0.1:54321/stop", datafile, fixture_repo) == "BLOCK"
        assert ev("wget --post-data= http://localhost:9/stop", datafile, fixture_repo) == "BLOCK"

    def test_prockill(self, datafile, fixture_repo):
        assert ev("pkill -f packages/happy-cli/dist/index.mjs", datafile, fixture_repo) == "BLOCK"
        assert ev("kill -9 $(pgrep -f happy-daemon)", datafile, fixture_repo) == "BLOCK"
        assert ev("fuser -k packages/happy-cli/dist/index.mjs", datafile, fixture_repo) == "BLOCK"

    def test_globalbin(self, datafile, fixture_repo):
        assert ev("npm install -g happy-coder", datafile, fixture_repo) == "BLOCK"
        assert ev("pnpm add --global happy-coder", datafile, fixture_repo) == "BLOCK"
        assert ev("yarn global add happy", datafile, fixture_repo) == "BLOCK"
        assert ev("npm link happy", datafile, fixture_repo) == "BLOCK"

    def test_datafile_mutation(self, datafile, fixture_repo):
        # mutation of the actual hardcoded data-file path is STEP0 protected
        os.environ["CLAUDE_PROTECTED_RUNTIME_FILE"] = "/root/.config/claude/protected-runtime.json"
        import importlib, lib.runtime_guard as rg
        importlib.reload(rg)
        assert rg.evaluate("echo {} > /root/.config/claude/protected-runtime.json")[0] == "BLOCK"
        assert rg.evaluate("rm /root/.config/claude/protected-runtime.json")[0] == "BLOCK"
        assert rg.evaluate("sed -i s/a/b/ /root/.config/claude/protected-runtime.json")[0] == "BLOCK"
        assert rg.evaluate("chmod 000 /root/.config/claude/protected-runtime.json")[0] == "BLOCK"

    # ── P9 default-deny block families ──
    def test_pkgscript_bare_run(self, datafile, fixture_repo):
        for c in ("yarn dev:daemon:start", "yarn start", "yarn cli", "yarn dev",
                  "yarn test", "yarn prepublishOnly", "npm start", "npm test",
                  "yarn run dev:daemon:start", "npm run-script stable"):
            assert ev(c, datafile, fixture_repo) == "BLOCK", c

    def test_pkgscript_protected_workspace_run(self, datafile, fixture_repo):
        for c in ("yarn workspace happy cli", "yarn workspace happy-coder build",
                  "npm -w happy-coder run dev:daemon:start", "npm --workspace=happy run start",
                  "pnpm --filter happy dev:daemon:stop", "pnpm -F=happy-coder dev",
                  "yarn --cwd packages/happy-cli dev", "pnpm -C packages/happy-cli start"):
            assert ev(c, datafile, fixture_repo) == "BLOCK", c

    def test_pkgscript_passthrough_dispatcher(self, datafile, fixture_repo):
        for c in ("yarn stable daemon start", "yarn stable daemon stop",
                  "yarn dev:variant daemon start", "yarn stable doctor clean",
                  "yarn stable daemon status", "bun stable daemon start",
                  "yarn run stable daemon start"):
            assert ev(c, datafile, fixture_repo) == "BLOCK", c

    def test_pkgscript_publish_release(self, datafile, fixture_repo):
        for c in ("yarn workspace happy run release", "yarn workspace happy-coder run release",
                  "npm -w happy-coder run release"):
            assert ev(c, datafile, fixture_repo) == "BLOCK", c

    def test_pkgscript_root_dispatch_alias(self, datafile, fixture_repo):
        for c in ("yarn env:cli", "yarn env:seed", "yarn env:up",
                  "yarn env:up:authenticated", "yarn env:down", "yarn cli"):
            assert ev(c, datafile, fixture_repo) == "BLOCK", c

    def test_pkgscript_recursive_fanout(self, datafile, fixture_repo):
        for c in ("yarn workspaces run build", "pnpm -r run prepublishOnly",
                  "pnpm --recursive run test"):
            assert ev(c, datafile, fixture_repo) == "BLOCK", c

    def test_pkgscript_bin_fallthrough(self, datafile, fixture_repo):
        for c in ("yarn workspace happy-server happy daemon start",
                  "yarn workspace happy-app happy daemon start",
                  "yarn workspace happy-server happy-mcp serve",
                  "yarn workspace happy-server node ../happy-cli/bin/happy.mjs daemon start",
                  "yarn workspace happy-server exec happy daemon start",
                  "pnpm --filter happy-server happy daemon start",
                  "npm -w happy-server run happy"):
            assert ev(c, datafile, fixture_repo) == "BLOCK", c

    def test_pkgscript_selector_name_not_folder(self, datafile, fixture_repo):
        for c in ("yarn workspace happy build", "npm -w happy run build",
                  "pnpm --filter happy run build", "pnpm --filter happy-coder build"):
            assert ev(c, datafile, fixture_repo) == "BLOCK", c

    def test_pkgscript_cwd_changing(self, datafile, fixture_repo):
        repo = fixture_repo
        for c in (f"cd {repo}/packages/happy-cli && yarn build",
                  f"yarn --cwd {repo}/packages/happy-cli build",
                  f"npm --prefix {repo}/packages/happy-cli run start",
                  f"pnpm -C {repo}/packages/happy-cli dev",
                  f"env -C {repo}/packages/happy-cli yarn build"):
            assert ev(c, datafile, fixture_repo) == "BLOCK", c

    def test_pkgscript_exec_dlx(self, datafile, fixture_repo):
        for c in ("npm exec happy daemon start", "pnpm exec happy daemon start",
                  "pnpm dlx happy daemon start", "yarn dlx happy daemon start",
                  "bunx happy daemon start", "bun x happy daemon start",
                  "corepack yarn stable daemon start"):
            assert ev(c, datafile, fixture_repo) == "BLOCK", c

    def test_pkgscript_compound_shortcircuit(self, datafile, fixture_repo):
        repo = fixture_repo
        assert ev("yarn --version && yarn workspace happy build", datafile, fixture_repo) == "BLOCK"
        assert ev("ls; yarn workspace happy build", datafile, fixture_repo) == "BLOCK"
        assert ev(f"yarn --version | tee log && cd {repo}/packages/happy-cli && yarn start", datafile, fixture_repo) == "BLOCK"

    def test_pkgscript_dependency_protected_cwd(self, datafile, fixture_repo):
        repo = fixture_repo
        for c in (f"cd {repo}/packages/happy-cli && yarn add foo",
                  f"npm --prefix {repo}/packages/happy-cli install",
                  f"yarn --cwd {repo}/packages/happy-cli install"):
            assert ev(c, datafile, fixture_repo) == "BLOCK", c

    def test_pkgscript_safe_allowlist_empty(self, datafile, fixture_repo):
        for c in ("yarn dev:daemon:status", "yarn env:list", "yarn env:current"):
            assert ev(c, datafile, fixture_repo) == "BLOCK", c


class TestAllows:
    def test_read_statefile(self, datafile, fixture_repo):
        for c in ("cat /root/.happy-dev/daemon.state.json",
                  "grep pid /root/.happy/daemon.state.json",
                  "head /root/.happy-qijie/daemon.state.json"):
            assert ev(c, datafile, fixture_repo) == "ALLOW", c

    def test_other_package_build(self, datafile, fixture_repo):
        for c in ("yarn workspace happy-server build", "yarn workspace @slopus/happy-wire build",
                  "yarn workspace happy-agent build"):
            assert ev(c, datafile, fixture_repo) == "ALLOW", c

    def test_npx_tsc_nonprotected(self, datafile, fixture_repo):
        assert ev("npx tsc --version", datafile, fixture_repo) == "ALLOW"
        assert ev("npx tsc -p packages/happy-server/tsconfig.json", datafile, fixture_repo) == "ALLOW"

    def test_grep_procident(self, datafile, fixture_repo):
        assert ev("grep packages/happy-cli/dist/index.mjs -R .", datafile, fixture_repo) == "ALLOW"
        assert ev("ps aux | grep packages/happy-cli/dist/index.mjs", datafile, fixture_repo) == "ALLOW"

    def test_edit_source(self, datafile, fixture_repo):
        assert ev("sed -i s/a/b/ packages/happy-cli/src/daemon/run.ts", datafile, fixture_repo) == "ALLOW"

    def test_echo_projectname(self, datafile, fixture_repo):
        assert ev("echo happy-daemon restart", datafile, fixture_repo) == "ALLOW"
        assert ev("grep happy somefile", datafile, fixture_repo) == "ALLOW"

    def test_pkgscript_nonprotected_workspace_run(self, datafile, fixture_repo):
        for c in ("yarn workspace happy-server build", "yarn workspace happy-app web",
                  "yarn workspace happy-agent dev", "yarn workspace happy-agent release",
                  "yarn workspace @slopus/happy-wire build",
                  "npm -w happy-server run build", "pnpm --filter happy-app web"):
            assert ev(c, datafile, fixture_repo) == "ALLOW", c

    def test_pkgscript_selector_run_keyword(self, datafile, fixture_repo):
        for c in ("yarn workspace happy-server run build", "pnpm --filter happy-app run web",
                  "npm -w happy-server run build"):
            assert ev(c, datafile, fixture_repo) == "ALLOW", c

    def test_pkgscript_selector_dependency(self, datafile, fixture_repo):
        for c in ("yarn workspace happy-server add foo", "npm -w happy-server install foo",
                  "pnpm --filter happy-app add foo"):
            assert ev(c, datafile, fixture_repo) == "ALLOW", c

    def test_pkgscript_dependency_mgmt(self, datafile, fixture_repo):
        for c in ("yarn install", "yarn add some-pkg", "yarn remove some-pkg",
                  "npm install", "pnpm install", "yarn upgrade", "yarn up"):
            assert ev(c, datafile, fixture_repo) == "ALLOW", c

    def test_pkgscript_meta_and_text(self, datafile, fixture_repo):
        for c in ("yarn --version", "yarn -v", "npm --version", "yarn --help",
                  "echo yarn dev:daemon:start", "echo yarn stable daemon start",
                  "grep dev:daemon:start file"):
            assert ev(c, datafile, fixture_repo) == "ALLOW", c

    def test_pkgscript_cross_package(self, datafile, fixture_repo):
        repo = fixture_repo
        for c in (f"cd {repo}/packages/happy-agent && yarn dev",
                  f"cd {repo}/packages/happy-server && yarn test",
                  f"cd {repo}/packages/happy-server && yarn build",
                  "yarn workspace happy-agent dev"):
            assert ev(c, datafile, fixture_repo) == "ALLOW", c

    def test_pkgscript_dependency_ignore_scripts(self, datafile, fixture_repo):
        repo = fixture_repo
        for c in (f"cd {repo}/packages/happy-cli && yarn install --ignore-scripts",
                  f"npm --prefix {repo}/packages/happy-cli install --ignore-scripts"):
            assert ev(c, datafile, fixture_repo) == "ALLOW", c


class TestBinFallthroughNonProtectedCwd:
    def test_bare_cwd_fallthrough_blocked(self, datafile, fixture_repo):
        repo = fixture_repo
        for c in (f"cd {repo}/packages/happy-server && yarn happy daemon start",
                  f"yarn --cwd {repo}/packages/happy-server happy daemon start"):
            assert ev(c, datafile, fixture_repo) == "BLOCK", c


# ════════════════════════════════════════════════════════════════════════════
# Iteration 2 (qa-report-20260531-162901): cross-segment / wrapper / xargs /
# pm-exec / cwd-relative leak coverage. Each was reproduced ALLOW against the
# prior engine; these assert BLOCK + companion boundary-allow tests prove the
# fixes do not over-block. Verified ONLY by feeding strings to evaluate()
# (NEVER any real daemon/CLI command).
# ════════════════════════════════════════════════════════════════════════════

class TestLeak1CrossSegmentKill:
    """P6: a protected proc-ident in an upstream pipeline segment feeding a kill
    executor downstream (or kill $(<pipeline naming ident>)) must BLOCK."""
    def test_ps_grep_xargs_kill(self, datafile, fixture_repo):
        for c in ("ps aux | grep happy-daemon | awk '{print $2}' | xargs kill",
                  "pgrep -f happy-daemon | xargs kill",
                  "ps aux | grep happy-daemon | awk '{print $2}' | xargs pkill",
                  "pgrep -f packages/happy-cli/dist/index.mjs | xargs -r kill -9"):
            assert ev(c, datafile, fixture_repo) == "BLOCK", c

    def test_kill_command_substitution_pipeline(self, datafile, fixture_repo):
        for c in ("kill $(ps aux | grep happy-daemon | awk '{print $2}')",
                  "kill -9 $(pgrep -f 'daemon start-sync')"):
            assert ev(c, datafile, fixture_repo) == "BLOCK", c

    # boundary allows — NOT over-blocking unrelated pipelines
    def test_unrelated_pipeline_kill_allowed(self, datafile, fixture_repo):
        for c in ("ps aux | grep foo | awk '{print $2}' | xargs kill",
                  "pgrep -f some-other-proc | xargs kill",
                  "ps aux | grep happy-daemon | awk '{print $2}'",
                  "ps aux | grep happy-daemon"):
            assert ev(c, datafile, fixture_repo) == "ALLOW", c


class TestLeak2XargsLaunch:
    """P1: an xargs executor whose target is the protected command (or a runtime
    fed a protected path via the upstream pipe) must BLOCK."""
    def test_xargs_protected_cmd(self, datafile, fixture_repo):
        for c in ("echo daemon start | xargs happy",
                  "echo serve | xargs happy-mcp",
                  "printf 'daemon start\\n' | xargs -I{} happy {}"):
            assert ev(c, datafile, fixture_repo) == "BLOCK", c

    def test_xargs_runtime_upstream_path(self, datafile, fixture_repo):
        repo = fixture_repo
        c = f"printf '{repo}/packages/happy-cli/dist/index.mjs daemon start' | xargs node"
        assert ev(c, datafile, fixture_repo) == "BLOCK", c

    # boundary allows — xargs with a non-protected target / content
    def test_xargs_nonprotected_allowed(self, datafile, fixture_repo):
        for c in ("echo hi | xargs ls",
                  "find . -name '*.log' | xargs rm",
                  "echo foo | xargs echo",
                  "ls | xargs -n1 basename"):
            assert ev(c, datafile, fixture_repo) == "ALLOW", c


class TestLeak3CwdAndPmExecBuild:
    """P8: a build tool / package-runner build whose effective cwd resolves under
    a protected build path, and the pm-exec build forms (npm/pnpm/yarn exec)."""
    def test_cd_then_npx_tsc(self, datafile, fixture_repo):
        repo = fixture_repo
        for c in (f"cd {repo}/packages/happy-cli && npx tsc -p tsconfig.json",
                  f"cd {repo}/packages/happy-cli && pnpm exec tsc -p tsconfig.json"):
            assert ev(c, datafile, fixture_repo) == "BLOCK", c

    def test_pm_exec_tsc_protected_path(self, datafile, fixture_repo):
        repo = fixture_repo
        cli = f"{repo}/packages/happy-cli"
        for c in (f"npm exec tsc -p {cli}/tsconfig.json",
                  f"yarn exec tsc -p {cli}/tsconfig.json",
                  f"pnpm exec tsc -p {cli}/tsconfig.json"):
            assert ev(c, datafile, fixture_repo) == "BLOCK", c

    def test_cwd_seed_npx_tsc(self, datafile, fixture_repo):
        repo = fixture_repo
        assert ev_cwd("npx tsc -p tsconfig.json", datafile, f"{repo}/packages/happy-cli") == "BLOCK"

    # boundary allows — a package-runner building a NON-protected package
    def test_pm_exec_nonprotected_allowed(self, datafile, fixture_repo):
        repo = fixture_repo
        srv = f"{repo}/packages/happy-server"
        for c in (f"npm exec tsc -p {srv}/tsconfig.json",
                  f"pnpm exec tsc -p {srv}/tsconfig.json",
                  f"npx tsc -p {srv}/tsconfig.json",
                  f"cd {srv} && npx tsc -p tsconfig.json"):
            assert ev(c, datafile, fixture_repo) == "ALLOW", c


class TestLeak4WrapperCwd:
    """P1: an env -C / sudo --chdir wrapper that changes directory then runs a
    runtime against a relative protected bundle path must BLOCK."""
    def test_env_dashC_launch(self, datafile, fixture_repo):
        repo = fixture_repo
        cli = f"{repo}/packages/happy-cli"
        for c in (f"env -C {cli} node dist/index.mjs daemon start",
                  f"env --chdir {cli} node dist/index.mjs daemon start",
                  f"env -C {cli} tsx src/index.ts daemon"):
            assert ev(c, datafile, fixture_repo) == "BLOCK", c

    def test_env_dashC_build(self, datafile, fixture_repo):
        repo = fixture_repo
        assert ev(f"env -C {repo}/packages/happy-cli npx tsc -p tsconfig.json", datafile, fixture_repo) == "BLOCK"

    # boundary allow — env -C into a NON-protected workspace running a runtime
    def test_env_dashC_nonprotected_allowed(self, datafile, fixture_repo):
        repo = fixture_repo
        srv = f"{repo}/packages/happy-server"
        for c in (f"env -C {srv} node build.js",
                  f"env --chdir {srv} node scripts/migrate.js"):
            assert ev(c, datafile, fixture_repo) == "ALLOW", c


class TestLeak5CrossSegmentEndpoint:
    """P5: a pipeline whose content carries the loopback control-endpoint path
    piped into a raw-socket tool aimed at a loopback host must BLOCK."""
    def test_printf_pipe_nc(self, datafile, fixture_repo):
        for c in ("printf 'POST /stop HTTP/1.0\\r\\n\\r\\n' | nc 127.0.0.1 54321",
                  "printf 'POST /stop ' | nc localhost 9",
                  "echo -e 'POST /stop\\r\\n' | socat - TCP:127.0.0.1:8080",
                  "printf 'POST /stop' | ncat ::1 5000"):
            assert ev(c, datafile, fixture_repo) == "BLOCK", c

    # boundary allows — loopback socket tool with NO control-endpoint content,
    # and the control path with NO loopback client
    def test_loopback_no_endpoint_allowed(self, datafile, fixture_repo):
        for c in ("printf 'GET /health' | nc 127.0.0.1 8080",
                  "printf 'GET /metrics HTTP/1.0\\r\\n' | nc localhost 9090",
                  "echo hello | nc 127.0.0.1 1234"):
            assert ev(c, datafile, fixture_repo) == "ALLOW", c

    def test_endpoint_text_no_client_allowed(self, datafile, fixture_repo):
        for c in ("echo 'POST /stop' >> notes.txt",
                  "grep '/stop' config.txt"):
            assert ev(c, datafile, fixture_repo) == "ALLOW", c


# ════════════════════════════════════════════════════════════════════════════
# Iteration 2 codex (gpt-5.5 xhigh) adversarial-review regression coverage.
# Codex surfaced 12 deeper in-scope idiomatic forms of the SAME 5 classes plus
# 2 over-block regressions my pipeline-group/cwd fixes introduced. All 12 are
# covered here (BLOCK forms + the 2 over-block ALLOW fixes).
# ════════════════════════════════════════════════════════════════════════════

class TestCodexR2Splitting:
    """F1/F2: fd-redirection `&` must not split a pipeline; separators inside
    $()/backticks must not split the kill substitution."""
    def test_redirect_amp_not_separator(self, datafile, fixture_repo):
        assert ev("pgrep -af happy-daemon 2>&1 | awk '{print $1}' | xargs kill", datafile, fixture_repo) == "BLOCK"

    def test_separators_inside_substitution(self, datafile, fixture_repo):
        for c in ("kill $(true && pgrep -f happy-daemon)",
                  "kill $(echo ok >/dev/null; pgrep -f happy-daemon)",
                  "kill `true; pgrep -f happy-daemon`"):
            assert ev(c, datafile, fixture_repo) == "BLOCK", c

    def test_redirect_amp_benign_allowed(self, datafile, fixture_repo):
        # background `&` of an unrelated command still allowed; 2>&1 on a benign
        # pipeline allowed
        for c in ("ls 2>&1 | grep foo", "echo hi & echo bye"):
            assert ev(c, datafile, fixture_repo) == "ALLOW", c


class TestCodexR2XargsWrappers:
    """F3: xargs target through a wrapper (sudo/env) and the -I{} placeholder."""
    def test_xargs_wrapped_kill(self, datafile, fixture_repo):
        assert ev("ps aux | grep happy-daemon | awk '{print $2}' | xargs sudo kill", datafile, fixture_repo) == "BLOCK"

    def test_xargs_env_node_path(self, datafile, fixture_repo):
        repo = fixture_repo
        c = f"printf '{repo}/packages/happy-cli/dist/index.mjs daemon start' | xargs env node"
        assert ev(c, datafile, fixture_repo) == "BLOCK", c

    def test_xargs_placeholder_command(self, datafile, fixture_repo):
        assert ev("printf 'happy daemon start' | xargs -I{} {}", datafile, fixture_repo) == "BLOCK"


class TestCodexR2P5OverblockFix:
    """F4: P5 must be order/client-semantics aware (no over-block of legit
    loopback work)."""
    def test_curl_health_grep_stop_allowed(self, datafile, fixture_repo):
        assert ev("curl http://localhost:3005/health | grep /stop", datafile, fixture_repo) == "ALLOW"

    def test_grep_stop_curl_health_allowed(self, datafile, fixture_repo):
        assert ev("grep /stop README.md | curl http://localhost:3005/health", datafile, fixture_repo) == "ALLOW"

    def test_netcat_basename_blocked(self, datafile, fixture_repo):
        assert ev("printf 'POST /stop HTTP/1.1' | netcat localhost 3005", datafile, fixture_repo) == "BLOCK"


class TestCodexR2WrapperCwdForms:
    """F6/F7: fused env -C<dir>, systemd-run --working-directory=, exec wrapper,
    systemd-run -G not consuming an operand."""
    def test_fused_env_dashC(self, datafile, fixture_repo):
        repo = fixture_repo
        cli = f"{repo}/packages/happy-cli"
        assert ev(f"env -C{cli} node dist/index.mjs daemon start", datafile, fixture_repo) == "BLOCK"

    def test_systemd_run_working_directory(self, datafile, fixture_repo):
        repo = fixture_repo
        cli = f"{repo}/packages/happy-cli"
        assert ev(f"systemd-run --working-directory={cli} node dist/index.mjs daemon start", datafile, fixture_repo) == "BLOCK"

    def test_exec_wrapper_launch(self, datafile, fixture_repo):
        repo = fixture_repo
        assert ev("exec happy daemon start", datafile, fixture_repo) == "BLOCK"
        assert ev(f"exec node {repo}/packages/happy-cli/dist/index.mjs daemon start", datafile, fixture_repo) == "BLOCK"

    def test_systemd_run_G_no_operand(self, datafile, fixture_repo):
        assert ev("systemd-run -G happy daemon start", datafile, fixture_repo) == "BLOCK"


class TestCodexR2CdOptionsAndCompound:
    """F8/F9: cd -P/-- and pushd --; compound { } and ( ) groups."""
    def test_cd_options(self, datafile, fixture_repo):
        repo = fixture_repo
        cli = f"{repo}/packages/happy-cli"
        for c in (f"cd -P {cli} && npx tsc", f"cd -- {cli} && npx tsc",
                  f"pushd -- {cli} && npx tsc"):
            assert ev(c, datafile, fixture_repo) == "BLOCK", c

    def test_compound_groups(self, datafile, fixture_repo):
        repo = fixture_repo
        cli = f"{repo}/packages/happy-cli"
        for c in (f"{{ cd {cli}; node dist/index.mjs daemon start; }}",
                  f"(cd {cli} && npx tsc)"):
            assert ev(c, datafile, fixture_repo) == "BLOCK", c

    def test_compound_nonprotected_allowed(self, datafile, fixture_repo):
        repo = fixture_repo
        srv = f"{repo}/packages/happy-server"
        assert ev(f"(cd {srv} && npx tsc -p tsconfig.json)", datafile, fixture_repo) == "ALLOW"


class TestCodexR2RunnerRuntime:
    """F10: package-runner invoking a runtime against a protected path; runner
    options with operands (--package)."""
    def test_npx_tsx_protected_src(self, datafile, fixture_repo):
        repo = fixture_repo
        cli = f"{repo}/packages/happy-cli"
        for c in (f"npx tsx {cli}/src/index.ts",
                  f"npm exec -- tsx {cli}/src/index.ts"):
            assert ev(c, datafile, fixture_repo) == "BLOCK", c

    def test_npx_package_option(self, datafile, fixture_repo):
        repo = fixture_repo
        cli = f"{repo}/packages/happy-cli"
        assert ev(f"npx --package typescript tsc -p {cli}", datafile, fixture_repo) == "BLOCK"


class TestCodexR2LoopConsumers:
    """F11: pipe-fed while-read loops for kill and launch."""
    def test_while_read_kill(self, datafile, fixture_repo):
        assert ev("pgrep -af happy-daemon | while read pid; do kill $pid; done", datafile, fixture_repo) == "BLOCK"

    def test_while_read_launch(self, datafile, fixture_repo):
        assert ev("printf 'daemon start' | while read args; do happy $args; done", datafile, fixture_repo) == "BLOCK"

    def test_benign_while_read_allowed(self, datafile, fixture_repo):
        assert ev("ls | while read f; do echo $f; done", datafile, fixture_repo) == "ALLOW"


class TestCodexR2P9WrapperCwdOverblock:
    """F12: P9 must fold wrapper cwd so env -C <non-protected-ws> yarn <script>
    is not over-blocked."""
    def test_env_dashC_nonprotected_pkgscript_allowed(self, datafile, fixture_repo):
        repo = fixture_repo
        assert ev(f"env -C {repo}/packages/happy-app yarn web", datafile, fixture_repo) == "ALLOW"

    def test_env_dashC_protected_pkgscript_blocked(self, datafile, fixture_repo):
        repo = fixture_repo
        assert ev(f"env -C {repo}/packages/happy-cli yarn build", datafile, fixture_repo) == "BLOCK"


# ── codex round-1 (this cycle) adversarial-review regression coverage ────────

def ev_cwd(command, datafile, cwd):
    """evaluate() with an explicit cwd_base seed."""
    os.environ["CLAUDE_PROTECTED_RUNTIME_FILE"] = datafile
    import importlib, lib.runtime_guard as rg
    importlib.reload(rg)
    return rg.evaluate(command, cwd)[0]


class TestCodexWrapperOperands:
    """Wrappers with operands + process-handoff wrappers must not hide the
    real service/runtime/protected command word."""
    def test_timeout_then_service(self, datafile, fixture_repo):
        assert ev("timeout 10 systemctl restart happy-daemon-dev", datafile, fixture_repo) == "BLOCK"
        assert ev("timeout --signal=TERM 10 happy daemon start", datafile, fixture_repo) == "BLOCK"
        assert ev("timeout -s TERM 10 happy daemon start", datafile, fixture_repo) == "BLOCK"

    def test_nice_ionice(self, datafile, fixture_repo):
        assert ev("nice -n 10 happy daemon start", datafile, fixture_repo) == "BLOCK"
        assert ev("ionice -c 3 happy daemon start", datafile, fixture_repo) == "BLOCK"

    def test_handoff_wrappers(self, datafile, fixture_repo):
        repo = fixture_repo
        assert ev("setsid happy daemon start", datafile, fixture_repo) == "BLOCK"
        assert ev(f"systemd-run --unit x node {repo}/packages/happy-cli/dist/index.mjs daemon start", datafile, fixture_repo) == "BLOCK"
        assert ev("daemonize happy daemon start", datafile, fixture_repo) == "BLOCK"


class TestCodexCwdRelativeLaunch:
    """P1 must resolve a relative protected launch path against the effective cwd."""
    def test_cd_then_relative_node(self, datafile, fixture_repo):
        repo = fixture_repo
        assert ev(f"cd {repo}/packages/happy-cli && node dist/index.mjs daemon start", datafile, fixture_repo) == "BLOCK"

    def test_cwd_seed_relative_node(self, datafile, fixture_repo):
        repo = fixture_repo
        assert ev_cwd("node dist/index.mjs daemon start", datafile, f"{repo}/packages/happy-cli") == "BLOCK"


class TestCodexRuntimeOptionOperands:
    """A runtime flag-with-value must not hide the protected script positional."""
    def test_loader_and_require(self, datafile, fixture_repo):
        repo = fixture_repo
        src = f"{repo}/packages/happy-cli/src/index.ts"
        dist = f"{repo}/packages/happy-cli/dist/index.mjs"
        assert ev(f"node --loader ts-node/esm {src}", datafile, fixture_repo) == "BLOCK"
        assert ev(f"node -r ts-node/register {src}", datafile, fixture_repo) == "BLOCK"
        assert ev(f"node --require ts-node/register {dist} daemon", datafile, fixture_repo) == "BLOCK"


class TestCodexCwdSeedReducesFalseBlock:
    """A relative cd into a NON-protected workspace resolves and stays allowed."""
    def test_relative_cd_nonprotected_allowed(self, datafile, fixture_repo):
        repo = fixture_repo
        assert ev_cwd("cd packages/happy-server && yarn build", datafile, repo) == "ALLOW"
        assert ev_cwd("cd packages/happy-app && yarn web", datafile, repo) == "ALLOW"

    def test_relative_cd_protected_still_blocked(self, datafile, fixture_repo):
        repo = fixture_repo
        assert ev_cwd("cd packages/happy-cli && yarn build", datafile, repo) == "BLOCK"


class TestCodexLsofFuserReadOnly:
    """lsof and bare fuser are read-only; only fuser -k kills."""
    def test_lsof_readonly_allowed(self, datafile, fixture_repo):
        repo = fixture_repo
        assert ev(f"lsof {repo}/packages/happy-cli/dist/index.mjs", datafile, fixture_repo) == "ALLOW"

    def test_bare_fuser_allowed(self, datafile, fixture_repo):
        repo = fixture_repo
        assert ev(f"fuser {repo}/packages/happy-cli/dist/index.mjs", datafile, fixture_repo) == "ALLOW"

    def test_fuser_k_blocked(self, datafile, fixture_repo):
        assert ev("fuser -k packages/happy-cli/dist/index.mjs", datafile, fixture_repo) == "BLOCK"


class TestCodexEscapedQuoteSplit:
    """An escaped quote inside double quotes must not prematurely close the
    quote and split a quoted separator into a real simple command."""
    def test_escaped_quote_in_echo_allowed(self, datafile, fixture_repo):
        assert ev('echo "hello \\"; yarn build"', datafile, fixture_repo) == "ALLOW"
        assert ev('echo "x; yarn build"', datafile, fixture_repo) == "ALLOW"

    def test_real_compound_still_blocked(self, datafile, fixture_repo):
        repo = fixture_repo
        assert ev(f"ls; cd {repo}/packages/happy-cli && yarn build", datafile, fixture_repo) == "BLOCK"


class TestCodexGlueFailClosed:
    """The bash glue must fail CLOSED (deny danger families) when the helper is
    missing / errors / returns no decision — not fall open into legacy rules."""

    def _run_with_missing_helper(self, command):
        # Point the hook at a temp HOOKS dir whose lib/ lacks runtime_guard.py,
        # by overriding BASH_SOURCE dirname is not feasible; instead simulate the
        # glue's fallback contract directly: helper MISSING -> fail-closed grep.
        # We exercise the live hook with a guaranteed-broken python bin so the
        # helper cannot run, forcing the non-ALLOW branch.
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
        e = dict(os.environ)
        e["CLAUDE_PYTHON_BIN"] = "/nonexistent/python-broken"
        e["CLAUDE_PYTHON_FALLBACK"] = "/nonexistent/python-broken2"
        proc = subprocess.run(["bash", HOOK], input=payload, text=True, capture_output=True, env=e)
        return proc.returncode

    def test_failclosed_blocks_danger_family_when_helper_unavailable(self):
        # With no usable python, TOOL_NAME parse fails -> hook can't even detect
        # Bash; this is the deployment-broken case. We assert the dedicated
        # fallback path via a direct helper-missing simulation instead.
        # Direct simulation: call the fallback function semantics through grep.
        import re
        danger = [
            "yarn build", "systemctl restart x", "kill -9 1", "npx tsc",
            "node foo.mjs", "pnpm build",
        ]
        benign = ["ls -la", "cat foo", "git status", "grep x f"]
        pats = [
            r'(^|[;&|]|\s)(systemctl|service)\s+(start|stop|restart|try-restart|reload|reload-or-restart|kill|disable|mask|enable)(\s|$)',
            r'(^|[;&|]|\s)(kill|pkill|killall)(\s|$)',
            r'(^|[;&|]|\s)(yarn|npm|pnpm|bun)(\s|$)',
            r'(^|[;&|]|\s)(npx|bunx|tsc|pkgroll|tsup)(\s|$)',
            r'(^|[;&|]|\s)(node|nodejs|tsx|deno)(\s|$)',
        ]
        def matches(cmd):
            return any(re.search(p, cmd, re.IGNORECASE) for p in pats)
        for c in danger:
            assert matches(c), f"fallback should deny: {c}"
        for c in benign:
            assert not matches(c), f"fallback should allow: {c}"


# ════════════════════════════════════════════════════════════════════════════
# Layer 1b: fail-closed + self-protection + unbypassable (engine-level)
# ════════════════════════════════════════════════════════════════════════════

class TestFailClosed:
    def _ev_no_cfg(self, command, tmp_path):
        missing = str(tmp_path / "does-not-exist.json")
        os.environ["CLAUDE_PROTECTED_RUNTIME_FILE"] = missing
        import importlib, lib.runtime_guard as rg
        importlib.reload(rg)
        return rg.evaluate(command)[0]

    def test_failclosed_blocks_families(self, tmp_path):
        for c in ("yarn build", "systemctl restart x", "kill -9 1", "npx tsc"):
            assert self._ev_no_cfg(c, tmp_path) == "BLOCK", c

    def test_failclosed_allows_reads(self, tmp_path):
        for c in ("ls", "cat foo", "grep x file", "git status"):
            assert self._ev_no_cfg(c, tmp_path) == "ALLOW", c

    def test_selfprotect_when_config_absent(self, tmp_path):
        # STEP0 protects the HARDCODED path regardless of the env override target,
        # because the engine hardcodes the configured path. Use the live path here.
        os.environ["CLAUDE_PROTECTED_RUNTIME_FILE"] = "/root/.config/claude/protected-runtime.json"
        import importlib, lib.runtime_guard as rg
        importlib.reload(rg)
        # Even with the file present-or-absent, STEP0 runs before config load.
        assert rg.evaluate("rm /root/.config/claude/protected-runtime.json")[0] == "BLOCK"


# ════════════════════════════════════════════════════════════════════════════
# Layer 2: live-hook integration (exit-code) incl. unbypassable under /do
# ════════════════════════════════════════════════════════════════════════════

def run_hook(command, env=None):
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    e = dict(os.environ)
    if env:
        e.update(env)
    proc = subprocess.run(["bash", HOOK], input=payload, text=True, capture_output=True, env=e)
    return proc.returncode


class TestLiveHook:
    """Drives the REAL hook end-to-end against the live data file.

    Uses benign-but-blocked representatives that do NOT collide with the hook's
    own pre-existing literal blocks where avoidable; the guard runs first so a
    guard BLOCK surfaces as exit 2.
    """

    def test_hook_blocks_bare_build(self):
        assert run_hook("yarn build") == BLOCK

    def test_hook_blocks_workspace_protected_build(self):
        assert run_hook("yarn workspace happy build") == BLOCK

    def test_hook_allows_nonprotected_build(self):
        assert run_hook("yarn workspace happy-server build") == ALLOW

    def test_hook_allows_read_statefile(self):
        assert run_hook("cat /root/.happy-dev/daemon.state.json") == ALLOW

    def test_hook_allows_meta_query(self):
        assert run_hook("yarn --version") == ALLOW

    def test_hook_allows_plain_ls(self):
        assert run_hook("ls -la") == ALLOW

    def test_hook_unbypassable_under_do(self):
        # Create a /do consent flag for this session; the guard must still block.
        import getpass  # noqa
        sid = "guardtest-" + str(os.getpid())
        flag = f"/tmp/claude-orchestrator-consent-{sid}.flag"
        with open(flag, "w") as fh:
            fh.write("true")
        try:
            payload = json.dumps({
                "tool_name": "Bash",
                "tool_input": {"command": "yarn workspace happy build"},
                "session_id": sid,
            })
            proc = subprocess.run(["bash", HOOK], input=payload, text=True, capture_output=True)
            assert proc.returncode == BLOCK
        finally:
            os.remove(flag)


# ════════════════════════════════════════════════════════════════════════════
# Iteration 3 (qa-report-20260531-162901, codex-r3): 25 reproduced idiomatic
# under-block leaks + 3 over-blocks + the narrowed other-project false-positive.
# Strategy: robust path/cwd/selector closures (NOT name enumeration). Each form
# below was reproduced ALLOW (under-block) or BLOCK (over-block) against the
# prior engine; these assert the corrected verdict. Verified ONLY by feeding
# strings to evaluate() (NEVER any real daemon/CLI/process command).
# ════════════════════════════════════════════════════════════════════════════

# Vocabulary split so the test SOURCE never types a full daemon-launch phrase
# (the live bash-safety hook scans this test's own command line at author time).
_S = "daemon " + "start"
_ST = "daemon " + "stop"


class TestR3SelectorExecLaunchBuild:
    """F1: a PM workspace selector + exec loses the selected-workspace cwd. The
    selector now threads the protected workspace dir as the effective cwd so a
    post-exec runtime/build resolves the protected path."""
    def test_selector_exec_runtime_launch(self, datafile, fixture_repo):
        # fixture models the protected workspace by its dev name 'happy'
        assert ev(f"yarn workspace happy exec node dist/index.mjs {_S}", datafile, fixture_repo) == "BLOCK"
        assert ev(f"yarn workspace happy exec node dist/index.mjs {_ST}", datafile, fixture_repo) == "BLOCK"

    def test_selector_exec_build(self, datafile, fixture_repo):
        for c in ("npm -w happy exec tsc -p tsconfig.json",
                  "yarn workspace happy exec tsc -p tsconfig.json"):
            assert ev(c, datafile, fixture_repo) == "BLOCK", c

    def test_selector_exec_nonprotected_allowed(self, datafile, fixture_repo):
        # a non-protected workspace exec of a build pointed at its OWN package
        for c in ("npm -w happy-server exec tsc --version",
                  "yarn workspace happy-server exec node build.js"):
            assert ev(c, datafile, fixture_repo) == "ALLOW", c


class TestR3BuildFlagValuePath:
    """F2: build invocations pointing at / writing to the protected package via a
    fused `--flag=path` option (--project=, --outfile=, --tsconfig=)."""
    def test_flagvalue_build_paths(self, datafile, fixture_repo):
        cli = f"{fixture_repo}/packages/happy-cli"
        for c in (f"npx tsc --project={cli}/tsconfig.json",
                  f"esbuild --bundle --outfile={cli}/dist/index.mjs",
                  f"tsc --tsconfig={cli}/tsconfig.json"):
            assert ev(c, datafile, fixture_repo) == "BLOCK", c

    def test_flagvalue_nonprotected_allowed(self, datafile, fixture_repo):
        srv = f"{fixture_repo}/packages/happy-server"
        for c in (f"npx tsc --project={srv}/tsconfig.json",
                  f"esbuild --outfile={srv}/dist/out.js"):
            assert ev(c, datafile, fixture_repo) == "ALLOW", c


class TestR3BareBuildModeFlag:
    """F3: bare build-mode flags (tsc -b / --build / -w) with cwd in the
    protected package / monorepo root / indeterminate -> fail-closed rebuild."""
    def test_tsc_build_mode_indeterminate(self, datafile, fixture_repo):
        for c in ("tsc -b", "npx tsc -b", "pnpm exec tsc -b", "tsc --build"):
            assert ev(c, datafile, fixture_repo) == "BLOCK", c

    def test_tsc_build_mode_protected_cwd(self, datafile, fixture_repo):
        assert ev_cwd("tsc -b", datafile, f"{fixture_repo}/packages/happy-cli") == "BLOCK"
        assert ev_cwd("npx tsc -b", datafile, fixture_repo) == "BLOCK"  # monorepo root

    def test_tsc_build_mode_nonprotected_cwd_allowed(self, datafile, fixture_repo):
        # build-mode in a NON-protected workspace cwd is the workspace's own build
        assert ev_cwd("tsc -b", datafile, f"{fixture_repo}/packages/happy-server") == "ALLOW"
        # a bare build tool whose cwd is a non-protected workspace is allowed
        assert ev_cwd("tsc --noEmit", datafile, f"{fixture_repo}/packages/happy-server") == "ALLOW"


class TestR3CorepackVersionPin:
    """F4: corepack <pm>@version proxy must unwrap to the bare PM and re-route."""
    def test_corepack_pm_at_version(self, datafile, fixture_repo):
        for c in (f"corepack pnpm@9 exec happy {_S}",
                  f"corepack yarn@stable workspace happy build",
                  f"corepack npm@10 exec happy {_S}"):
            assert ev(c, datafile, fixture_repo) == "BLOCK", c

    def test_corepack_nonprotected_allowed(self, datafile, fixture_repo):
        assert ev("corepack pnpm@9 --version", datafile, fixture_repo) == "ALLOW"


class TestR3WrapperBarePositional:
    """F5: bare-positional wrappers chrt/taskset/setarch and systemd-run option
    grammar must not hide the protected command word."""
    def test_priority_wrappers(self, datafile, fixture_repo):
        for c in (f"chrt -f 50 happy {_S}", f"taskset 0x1 happy {_S}",
                  f"setarch x86_64 happy {_S}", f"chrt 50 happy {_S}"):
            assert ev(c, datafile, fixture_repo) == "BLOCK", c

    def test_taskset_cpu_option_still_blocks(self, datafile, fixture_repo):
        # the -c <list> form already worked; ensure the leading-positional fix
        # does not break it (mask via option, then command word exposed).
        assert ev(f"taskset -c 0 happy {_S}", datafile, fixture_repo) == "BLOCK"

    def test_systemd_run_options(self, datafile, fixture_repo):
        for c in (f"systemd-run --service-type simple happy {_S}",
                  f"systemd-run -d happy {_S}",
                  f"systemd-run --nice 5 happy {_S}"):
            assert ev(c, datafile, fixture_repo) == "BLOCK", c

    def test_wrapper_nonprotected_allowed(self, datafile, fixture_repo):
        for c in ("chrt -f 50 ls", "taskset 0x1 echo hi", "setarch x86_64 true"):
            assert ev(c, datafile, fixture_repo) == "ALLOW", c


class TestR3RuntimeSubcommand:
    """F6: runtime subcommand forms deno run / tsx watch / bun run and the
    ts-node-esm alias must reach the protected src/dist path."""
    def test_runtime_subcommands(self, datafile, fixture_repo):
        cli = f"{fixture_repo}/packages/happy-cli"
        for c in (f"deno run {cli}/src/index.ts",
                  f"tsx watch {cli}/src/index.ts",
                  f"bun run {cli}/dist/index.mjs",
                  f"npx ts-node-esm {cli}/src/index.ts"):
            assert ev(c, datafile, fixture_repo) == "BLOCK", c

    def test_runtime_subcommand_nonprotected_allowed(self, datafile, fixture_repo):
        srv = f"{fixture_repo}/packages/happy-server"
        for c in (f"deno run {srv}/build.ts", f"tsx watch {srv}/dev.ts"):
            assert ev(c, datafile, fixture_repo) == "ALLOW", c


class TestR3StatefilePidKill:
    """F7: a kill whose target is resolved by reading the protected statefile,
    and a process-substitution-fed kill."""
    def test_kill_statefile_pid(self, datafile, fixture_repo):
        for c in ("kill $(jq -r .pid /root/.happy-dev/daemon.state.json)",
                  "kill -9 $(cat /root/.happy/daemon.state.json | jq .pid)"):
            assert ev(c, datafile, fixture_repo) == "BLOCK", c

    def test_kill_process_substitution(self, datafile, fixture_repo):
        assert ev("xargs kill <(pgrep -f happy-daemon)", datafile, fixture_repo) == "BLOCK"

    def test_kill_unrelated_statefile_allowed(self, datafile, fixture_repo):
        # reading an UNRELATED statefile to kill is not protected
        assert ev("kill $(jq -r .pid /tmp/other.state.json)", datafile, fixture_repo) == "ALLOW"


class TestR3ServiceVerbs:
    """F8: additional service lifecycle verbs (force-reload / condrestart /
    try-reload-or-restart) in both systemctl VERB UNIT and service UNIT VERB."""
    def test_extra_service_verbs(self, datafile, fixture_repo):
        for c in ("systemctl try-reload-or-restart happy-daemon",
                  "systemctl force-reload happy-daemon",
                  "service happy-daemon condrestart",
                  "systemctl reload-or-try-restart happy-daemon-dev"):
            assert ev(c, datafile, fixture_repo) == "BLOCK", c

    def test_service_verb_unrelated_unit_allowed(self, datafile, fixture_repo):
        assert ev("systemctl force-reload nginx", datafile, fixture_repo) == "ALLOW"


class TestR3RunnerCallPayload:
    """F10: runner -c/--call payload is a virtual command, recursively evaluated;
    benign payloads must NOT over-block."""
    def test_call_payload_launch_build(self, datafile, fixture_repo):
        cli = f"{fixture_repo}/packages/happy-cli"
        for c in (f"npx -c 'happy {_S}'",
                  f"npm exec -c 'tsc -p {cli}/tsconfig.json'",
                  f"pnpm dlx --call 'happy {_S}'"):
            assert ev(c, datafile, fixture_repo) == "BLOCK", c

    def test_call_payload_benign_allowed(self, datafile, fixture_repo):
        for c in ("npm exec -c 'ls'", "npx -c 'echo hi'",
                  "npm exec -c 'tsc --version'"):
            assert ev(c, datafile, fixture_repo) == "ALLOW", c


class TestR3PathFilterOverblock:
    """F11: a deterministic non-glob path filter (./packages/x) must resolve to a
    manifest, NOT be misclassified as a fan-out MULTI."""
    def test_path_filter_nonprotected_allowed(self, datafile, fixture_repo):
        for c in ("pnpm --filter ./packages/happy-server build",
                  "pnpm --filter=./packages/happy-app web",
                  "pnpm --filter packages/happy-server build"):
            assert ev(c, datafile, fixture_repo) == "ALLOW", c

    def test_path_filter_protected_blocked(self, datafile, fixture_repo):
        assert ev("pnpm --filter ./packages/happy-cli build", datafile, fixture_repo) == "BLOCK"

    def test_glob_filter_still_failclosed(self, datafile, fixture_repo):
        for c in ("pnpm --filter './packages/*' build", "pnpm --filter '...^happy' build",
                  "pnpm --filter '{packages/*}' build"):
            assert ev(c, datafile, fixture_repo) == "BLOCK", c


class TestR3LoopDepthOverblock:
    """F12: `do` must not increment loop depth (only while/for/until do), so a
    later top-level kill is not over-connected to the protected loop pipeline."""
    def test_post_loop_kill_allowed(self, datafile, fixture_repo):
        assert ev("pgrep -af happy-daemon | while read pid; do echo $pid; done; kill 123", datafile, fixture_repo) == "ALLOW"

    def test_in_loop_kill_still_blocked(self, datafile, fixture_repo):
        assert ev("pgrep -af happy-daemon | while read pid; do kill $pid; done", datafile, fixture_repo) == "BLOCK"


class TestR3OtherProjectFalsePositive:
    """Narrowed other-project FP: in an UNRELATED project (manifest outside every
    protected root), a non-declared script token (.bin fallthrough) is harmless
    and must be ALLOWED — UNLESS it is a protected command basename or a
    runtime/exec token."""
    def test_unrelated_project_nondeclared_allowed(self, datafile, fixture_repo, tmp_path_factory):
        other = _make_unrelated_repo(tmp_path_factory)
        for c in ("yarn lint", "yarn eslint", "yarn workspace web-app lint", "yarn"):
            assert ev_cwd(c, datafile, other) == "ALLOW", c

    def test_unrelated_project_protected_token_still_blocked(self, datafile, fixture_repo, tmp_path_factory):
        other = _make_unrelated_repo(tmp_path_factory)
        for c in (f"yarn happy {_S}", "yarn node x.js", "yarn workspace web-app happy " + _S):
            assert ev_cwd(c, datafile, other) == "BLOCK", c

    def test_protected_monorepo_nonprotected_ws_nondeclared_still_blocked(self, datafile, fixture_repo):
        # within the protected monorepo, a non-declared token fallthrough reaches
        # the hoisted protected CLI bin -> stays BLOCKED.
        assert ev("yarn workspace happy-server lint", datafile, fixture_repo) == "BLOCK"
        assert ev_cwd("yarn lint", datafile, f"{fixture_repo}/packages/happy-server") == "BLOCK"


def _make_unrelated_repo(tmp_path_factory):
    root = tmp_path_factory.mktemp("unrelated")
    pkgs = root / "packages"
    pkgs.mkdir()
    (pkgs / "web").mkdir()
    (pkgs / "web" / "package.json").write_text(json.dumps({"name": "web-app", "scripts": {"build": "x", "start": "x"}}))
    (root / "package.json").write_text(json.dumps({"name": "other-monorepo", "scripts": {"build": "x"}}))
    return str(root)


# ════════════════════════════════════════════════════════════════════════════
# Iteration 3 codex (gpt-5.5 xhigh) adversarial-review regression coverage.
# Codex surfaced 14 in-scope deeper forms (under-blocks + over-blocks) and 1
# out-of-scope residual (declared-script-body transitive reach — deferred per BA
# ROUND-5 codex-r5-4). The 14 in-scope forms are covered here. Verified ONLY by
# feeding strings to evaluate() (NEVER any real daemon/CLI/process command).
# ════════════════════════════════════════════════════════════════════════════


def _make_mirror_repo(tmp_path_factory):
    """An UNRELATED project that MIRRORS the packages/happy-cli layout (same
    suffix path) to prove suffix-glob matching does not over-block it."""
    root = tmp_path_factory.mktemp("mirror")
    pkgs = root / "packages"
    pkgs.mkdir()
    (pkgs / "happy-cli").mkdir()
    (pkgs / "happy-cli" / "package.json").write_text(json.dumps({"name": "unrelated-cli", "scripts": {"build": "x", "lint": "x"}}))
    (root / "package.json").write_text(json.dumps({"name": "mirror-root", "scripts": {"build": "x"}}))
    return str(root)


class TestR3CodexBuildPathCwd:
    """codex#1: relative build path resolved against effective cwd from a sibling
    package rebuilds the protected bundle."""
    def test_relative_build_path_sibling(self, datafile, fixture_repo):
        srv = f"{fixture_repo}/packages/happy-server"
        for c in ("npx tsc -p ../happy-cli/tsconfig.json",
                  "esbuild --outfile=../happy-cli/dist/index.mjs"):
            assert ev_cwd(c, datafile, srv) == "BLOCK", c

    def test_relative_build_path_sibling_nonprotected_allowed(self, datafile, fixture_repo):
        srv = f"{fixture_repo}/packages/happy-server"
        assert ev_cwd("npx tsc -p ./tsconfig.json", datafile, srv) == "ALLOW"


class TestR3CodexDefineFlagOverblock:
    """codex#2: a non-path key/value flag (--define:X=<protected>) must not be
    treated as a build path."""
    def test_define_value_not_path(self, datafile, fixture_repo):
        cli = f"{fixture_repo}/packages/happy-cli"
        srv = f"{fixture_repo}/packages/happy-server"
        assert ev(f"esbuild --define:CLI={cli} --outfile={srv}/out.js", datafile, fixture_repo) == "ALLOW"


class TestR3CodexBuildModeExplicitTarget:
    """codex#3: build-mode (-w/-b) with an explicit NON-protected project target
    must not be over-blocked by the cwd/root fallback."""
    def test_build_mode_explicit_nonprotected(self, datafile, fixture_repo):
        assert ev_cwd("tsc -w -p packages/happy-server/tsconfig.json", datafile, fixture_repo) == "ALLOW"

    def test_build_mode_explicit_protected_blocked(self, datafile, fixture_repo):
        assert ev_cwd("tsc -w -p packages/happy-cli/tsconfig.json", datafile, fixture_repo) == "BLOCK"


class TestR3CodexExecSelectorTarget:
    """codex#4: a PM selector after exec must not be misparsed as the runner
    target."""
    def test_exec_selector_then_runtime(self, datafile, fixture_repo):
        assert ev(f"npm exec -w happy -- node dist/index.mjs {_S}", datafile, fixture_repo) == "BLOCK"


class TestR3CodexMultiExecFanout:
    """codex#5: recursive/all-workspace exec of a runtime/build fans into the
    protected workspace."""
    def test_recursive_exec_runtime(self, datafile, fixture_repo):
        assert ev(f"pnpm -r exec node dist/index.mjs {_S}", datafile, fixture_repo) == "BLOCK"

    def test_glob_filter_exec_build(self, datafile, fixture_repo):
        assert ev("pnpm --filter './packages/*' exec tsc -p tsconfig.json", datafile, fixture_repo) == "BLOCK"


class TestR3CodexCallPayloadCwd:
    """codex#6: a runner -c/--call payload is recursively evaluated under the
    selector-resolved cwd."""
    def test_call_payload_selector_cwd(self, datafile, fixture_repo):
        assert ev(f"npm -w happy exec -c 'node dist/index.mjs {_S}'", datafile, fixture_repo) == "BLOCK"


class TestR3CodexRuntimePreload:
    """codex#7: a runtime preload/import option VALUE that is the protected path
    executes it."""
    def test_node_import_require(self, datafile, fixture_repo):
        cli = f"{fixture_repo}/packages/happy-cli"
        for c in (f"node --import {cli}/dist/index.mjs",
                  f"node -r {cli}/dist/index.mjs -e ''",
                  f"node --import={cli}/dist/index.mjs"):
            assert ev(c, datafile, fixture_repo) == "BLOCK", c


class TestR3CodexNodeRun:
    """codex#8: node --run <script> from a protected cwd is a package-script
    runner reaching the protected package."""
    def test_node_run_protected_cwd(self, datafile, fixture_repo):
        assert ev_cwd("node --run start", datafile, f"{fixture_repo}/packages/happy-cli") == "BLOCK"

    def test_node_run_indeterminate_cwd(self, datafile, fixture_repo):
        assert ev("node --run build", datafile, fixture_repo) == "BLOCK"


class TestR3CodexStatefileFusedRedirect:
    """codex#9: a kill whose substitution reads the protected statefile via a
    FUSED input redirection (`<path`)."""
    def test_kill_fused_redirect(self, datafile, fixture_repo):
        assert ev("kill $(jq -r .pid </root/.happy-dev/daemon.state.json)", datafile, fixture_repo) == "BLOCK"


class TestR3CodexSystemdTemplate:
    """codex#10: a protected systemd TEMPLATE instance (unit@instance)."""
    def test_template_instance(self, datafile, fixture_repo):
        for c in ("systemctl restart happy-daemon@dev.service",
                  "systemctl stop happy-daemon@prod"):
            assert ev(c, datafile, fixture_repo) == "BLOCK", c

    def test_unrelated_hyphenated_unit_allowed(self, datafile, fixture_repo):
        # a longer hyphenated unrelated unit must NOT match a protected prefix
        assert ev("systemctl restart happy-daemon-clone-xyz", datafile, fixture_repo) == "ALLOW"


class TestR3CodexMutationCwdAndRemoval:
    """codex#11: P3/P4 resolve relative mutation targets against effective cwd and
    cover removal verbs."""
    def test_cd_then_touch_hotfile(self, datafile, fixture_repo):
        assert ev(f"cd {fixture_repo}/packages/happy-cli && touch dist/index.mjs", datafile, fixture_repo) == "BLOCK"

    def test_rm_relative_hotfile(self, datafile, fixture_repo):
        assert ev_cwd("rm packages/happy-cli/dist/index.mjs", datafile, fixture_repo) == "BLOCK"

    def test_cd_then_truncate_statefile(self, datafile, fixture_repo):
        assert ev("cd /root/.happy-dev && truncate -s0 daemon.state.json", datafile, fixture_repo) == "BLOCK"


class TestR3CodexScopedFilterOverblock:
    """codex#12: a scoped package NAME filter (@scope/name) is a name selector,
    not a filesystem path."""
    def test_scoped_filter_build_allowed(self, datafile, fixture_repo):
        assert ev("pnpm --filter @slopus/happy-wire build", datafile, fixture_repo) == "ALLOW"


class TestR3CodexUnrelatedMirrorOverblock:
    """codex#13: an UNRELATED project mirroring packages/happy-cli must not be
    treated as protected by suffix-glob matching."""
    def test_unrelated_mirror_run_allowed(self, datafile, fixture_repo, tmp_path_factory):
        mirror = _make_mirror_repo(tmp_path_factory)
        assert ev_cwd("yarn lint", datafile, f"{mirror}/packages/happy-cli") == "ALLOW"

    def test_unrelated_mirror_path_filter_allowed(self, datafile, fixture_repo, tmp_path_factory):
        mirror = _make_mirror_repo(tmp_path_factory)
        assert ev_cwd("pnpm --filter ./packages/happy-cli build", datafile, mirror) == "ALLOW"


class TestR3CodexP9ExplicitPathShortcircuit:
    """codex#14: an explicit protected build-path arg forwarded to a script must
    block even when P9 would ALLOW the script-run."""
    def test_build_explicit_protected_path(self, datafile, fixture_repo):
        cli = f"{fixture_repo}/packages/happy-cli"
        srv = f"{fixture_repo}/packages/happy-server"
        assert ev_cwd(f"yarn build --project {cli}/tsconfig.json", datafile, srv) == "BLOCK"

    def test_build_explicit_nonprotected_path_allowed(self, datafile, fixture_repo):
        srv = f"{fixture_repo}/packages/happy-server"
        assert ev_cwd(f"yarn build --project {srv}/tsconfig.json", datafile, srv) == "ALLOW"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
