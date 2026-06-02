#!/usr/bin/env python3
"""Generic protected-runtime guard engine for pretool-bash-safety.sh.

This module contains ZERO project identifiers. Every project-specific name
(command basenames, workspace names, service units, file globs, monorepo roots)
lives ONLY in the machine-local data file whose path is the single hardcoded
constant below — a generic filesystem path, not a project name.

Decision contract:
  evaluate(command) -> ("BLOCK", primitive, reason) | ("ALLOW", None, None)

The hook invokes evaluate() BEFORE its /do, /allow, and sentinel bypass logic,
so a BLOCK here is unbypassable.

Ordering (mandatory):
  STEP 0  config self-protection  — runs BEFORE config load (hardcoded path patterns)
  STEP 1  load config; on missing/unreadable/malformed/wrong-schema -> indeterminate
          policy (fail-closed verb-family block)
  STEP 2  P1..P9 generic primitives, patterns sourced from the data file

Self-contained: does NOT depend on any context-stripped command form computed
later in the hook. It performs its own conservative tokenization.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from typing import Optional, Tuple

# ── The single hardcoded constant: the generic data-file path ────────────────
# Overridable for tests via env so the live machine file is never mutated by a
# test run. The path is generic; it carries no project identity.
DATA_FILE_PATH = os.environ.get(
    "CLAUDE_PROTECTED_RUNTIME_FILE",
    "/root/.config/claude/protected-runtime.json",
)

MAX_COMMAND_CHARS = int(os.environ.get("CLAUDE_GUARD_MAX_CHARS", "262144"))

Verdict = Tuple[str, Optional[str], Optional[str]]
ALLOW: Verdict = ("ALLOW", None, None)


def _block(primitive: str, reason: str) -> Verdict:
    return ("BLOCK", primitive, reason)


# ── Generic verb / keyword vocabularies (no project names) ───────────────────
PKG_MANAGERS = frozenset({"yarn", "npm", "pnpm", "bun"})
# Generic command wrappers that prefix the real command. After consuming a
# wrapper (and its own operands) the real command word follows. Includes
# process-handoff wrappers (setsid/systemd-run/daemonize) so a launch through
# them still reaches the runtime/protected command word.
ENV_WRAPPERS = frozenset({
    "env", "sudo", "command", "nohup", "time", "timeout", "doas",
    "stdbuf", "nice", "ionice", "setsid", "systemd-run", "daemonize",
    "chrt", "taskset", "setarch", "eatmydata", "exec",
})
# `exec [-cl] [-a name] command` — only -a consumes an operand; -c/-l do not.
_EXEC_OPTS_WITH_ARG = frozenset({"-a"})
# Wrapper -> set of options that consume ONE following operand (value).
_WRAPPER_OPTS_WITH_ARG = {
    "timeout": frozenset({"-s", "--signal", "-k", "--kill-after"}),
    "nice": frozenset({"-n", "--adjustment"}),
    "ionice": frozenset({"-c", "--class", "-n", "--classdata", "-p", "--pid"}),
    "stdbuf": frozenset({"-i", "-o", "-e"}),
    "systemd-run": frozenset({
        "--unit", "-u", "--property", "-p", "--slice", "--description",
        "--on-active", "--on-calendar", "--uid", "--gid", "--setenv", "-E",
        "--working-directory", "--service-type", "--nice", "-H", "--host",
        "-M", "--machine", "--on-boot", "--on-startup", "--on-unit-active",
        "--on-unit-inactive", "--timer-property",
        # NOTE: -d/--scope/-G/--pty/-t/--quiet are NO-ARG (must NOT consume an
        # operand); they are intentionally absent here.
    }),
    "chrt": frozenset({"-p"}),
    "taskset": frozenset({"-p", "-c", "--cpu-list"}),
    "setarch": frozenset(),
    "env": frozenset({"-C", "--chdir", "-u", "--unset", "-S", "--split-string"}),
    "doas": frozenset({"-u", "-C"}),
    "sudo": frozenset({"-u", "--user", "-g", "--group", "-C", "--close-from", "-D", "--chdir", "-p", "--prompt", "-U", "--other-user", "-r", "--role", "-t", "--type"}),
    "exec": _EXEC_OPTS_WITH_ARG,
}
# Wrappers that take ONE leading positional operand before the real command
# word: timeout DURATION; chrt PRIORITY; taskset MASK; setarch ARCH. For
# chrt/taskset the operand may instead be supplied via a value option
# (taskset -c <list>, chrt -p <pid>), so the leading positional is consumed
# only when no such value option already supplied it (tracked at parse time).
# setarch's ARCH is always positional; timeout's DURATION is always positional.
_WRAPPER_LEADING_POSITIONAL = frozenset({"timeout", "chrt", "taskset", "setarch"})
# Subset whose leading positional is SUPPRESSED if a value option already
# consumed an operand (so `taskset -c 0 <cmd>` exposes <cmd>, not skips it).
_WRAPPER_POSITIONAL_OPTIONAL = frozenset({"chrt", "taskset"})
RUNTIMES = frozenset({"node", "nodejs", "tsx", "bun", "deno", "ts-node", "ts-node-esm"})
# Per-runtime leading SUBCOMMANDS that precede the script positional and must be
# skipped so `deno run <path>`, `tsx watch <path>`, `bun run <path>` reach the
# protected path. These tokens are not the script; the script follows them.
_RUNTIME_SUBCOMMANDS = frozenset({"run", "watch"})
# Runtime flags that consume one following value (so the script positional is
# not mistaken for the value, and a value is not mistaken for the script).
_RUNTIME_OPTS_WITH_ARG = frozenset({
    "-r", "--require", "--loader", "--experimental-loader", "--import",
    "--env-file", "--conditions", "-C", "--cpu-prof-dir", "--heap-prof-dir",
    "--tsconfig", "--inspect-brk", "--max-old-space-size",
})
# Tokens that, after a workspace selector, must route a launch decision to P1.
EXEC_RUNNER_TOKENS = frozenset({"node", "nodejs", "tsx", "ts-node", "bun", "deno", "exec", "dlx", "npx", "bunx", "x", "run-script"})
DEP_BUILTINS = frozenset({
    "install", "i", "ci", "add", "remove", "rm", "uninstall", "un",
    "up", "upgrade", "update", "dedupe", "why", "info", "list", "ls",
    "outdated", "link", "unlink", "audit", "prune", "import",
})
MUTATION_VERBS = frozenset({
    "cp", "mv", "touch", "truncate", "dd", "install", "rsync", "tee",
    "unzip", "rename",
})
# Verbs that actually terminate a process. lsof and bare fuser are READ-ONLY
# (they list/inspect) and must NOT be treated as kills; only `fuser -k` kills.
KILL_VERBS = frozenset({"kill", "pkill", "killall"})
SERVICE_VERBS = frozenset({
    "start", "stop", "restart", "try-restart", "reload",
    "reload-or-restart", "kill", "disable", "mask", "enable",
    # additional lifecycle verbs that reload/restart a running unit
    "try-reload-or-restart", "reload-or-try-restart", "force-reload",
    "condrestart", "condreload",
})
# Generic build verbs / tool basenames for fail-closed + bare-build family.
BUILD_TOOL_BASENAMES = frozenset({"tsc", "pkgroll", "tsup", "rollup", "esbuild", "vite", "webpack"})
# Generic script tokens treated as bare-build-family verbs (no project names).
BARE_BUILD_SCRIPT_TOKENS = frozenset({
    "build", "test", "start", "dev", "prepublishOnly", "prepublish",
    "dev:local-server", "compile", "bundle",
})
DEP_SHORTHAND_NPM = frozenset({"start", "stop", "restart", "test"})

# ── Read / inspection / edit ALLOWLIST (the ONLY fixed head list) ────────────
# The anchor primitive (_p0_anchor) is HEAD-AGNOSTIC: it does NOT decide based on
# the leading program / wrapper name. The single fixed list it consults is this
# small, stable set of read / search / listing / stat / diff / pager / text-editor
# operations. A simple command whose HEAD basename is in this set is treated as a
# data/inspection command — its arguments are DATA (a protected path/command named
# as a grep pattern, an echo argument, a cat target, a diff operand) and the anchor
# scan is skipped for it (so read/inspect/edit of a protected path still ALLOWS).
# Any head OUTSIDE this set is a potential exec front-end / wrapper / launcher, so
# its WHOLE argv is scanned for a protected anchor in executable position. This is
# a denylist-free design: novel exec/process wrappers are never enumerated — they
# simply are NOT in the read/inspect allowlist, so their trailing protected
# launch/build/kill is analyzed regardless of the wrapper's name.
READ_INSPECT_EDIT_ALLOWLIST = frozenset({
    # file reading / dumping / paging
    "cat", "bat", "less", "more", "head", "tail", "tac", "nl", "zcat", "zless",
    "xxd", "od", "hexdump", "strings", "view",
    # search
    "grep", "egrep", "fgrep", "rg", "ag", "ack", "ripgrep",
    # listing / stat / metadata
    "ls", "ll", "dir", "tree", "stat", "file", "wc", "du", "df", "readlink",
    "realpath", "basename", "dirname", "pwd", "find", "fd", "locate",
    "namei", "lsattr", "getfattr",
    # diff / compare
    "diff", "colordiff", "cmp", "comm", "sdiff", "delta", "difft",
    # text transform / print (DATA emitters — never an exec launcher)
    "echo", "printf", "print", "yes", "seq", "cut", "sort", "uniq", "tr",
    "rev", "fold", "fmt", "column", "paste", "join", "expand", "unexpand",
    "jq", "yq", "awk", "gawk", "sed",
    # text editors (open a file for editing; not a launcher of the protected cmd)
    "vi", "vim", "nvim", "nano", "emacs", "ed", "code", "subl", "micro", "pico",
    # checksum / encode (read-only over file contents)
    "md5sum", "sha1sum", "sha256sum", "sha512sum", "cksum", "b2sum",
    "base64", "base32", "xargs0",
    # process / open-file inspection (read-only listing of a path/ident as DATA).
    # NOTE: the kill variants (`fuser -k`, `xargs kill`) are NOT exempted here —
    # they are caught by the cross-segment P6 process-kill guard, which inspects
    # `fuser -k` / `xargs kill` regardless of this allowlist.
    "lsof", "fuser", "ps", "pgrep", "pidof", "pstree", "top", "htop",
    # git read/inspection subset (the head is git; the verb is checked separately
    # below — git is intentionally NOT blanket-allowlisted because `git` can also
    # be a benign VCS op; handled by _git_is_readonly).
})

# git subcommands that are read-only / inspection (when head == 'git'). A git
# command with one of these verbs is treated as inspection (anchor scan skipped).
_GIT_READONLY_SUBCMDS = frozenset({
    "status", "log", "show", "diff", "blame", "ls-tree", "ls-files", "cat-file",
    "rev-parse", "describe", "branch", "tag", "remote", "config", "shortlog",
    "reflog", "grep", "whatchanged", "annotate", "for-each-ref", "rev-list",
})


# ── Generic exec-front-end profiles (recursive execution-tail) ───────────────
# A documented pass-through exec front-end is a wrapper that, after consuming its
# OWN options/operands, exec()s a TRAILING command (its "execution tail"). Unlike
# the ENV_WRAPPERS set above — which the command-word scanner folds away in place
# under a fixed handful of option grammars — these profiles drive a RECURSIVE
# pre-pass: the front-end is peeled off and the remaining tail is re-analyzed by
# the full primitive set (P1/P2/P6/P8/P9). This makes launch/kill/build detection
# wrapper-AGNOSTIC: an UNKNOWN binary is NOT a front-end (so a benign tail stays
# allowed), but every documented routine front-end exposes its trailing command
# to the guard so a protected launch/kill behind it can no longer hide.
#
# A profile is a dict:
#   opts_with_arg : frozenset of options that consume ONE following operand.
#   leading_positionals : count of bare positional operands the front-end takes
#                         BEFORE the tail command (e.g. flock LOCKFILE; nsenter
#                         has none positional — its target is opt-supplied).
#   payload_opt : option whose VALUE is a SHELL STRING the front-end runs via a
#                 shell (flock -c / su -c / runuser -c). The value is recursed
#                 through evaluate(), not treated as an argv tail.
#   joins_tail_as_shell : True when the front-end joins its WHOLE trailing argv
#                         into a single shell-evaluated string (watch <cmd...>),
#                         so the joined tail is recursed through evaluate().
# Options not listed are treated as no-arg flags (skipped). Unknown long opts of
# the `--opt=value` fused form are single tokens. A fused short opt (`-fXYZ`) is
# a single token. `--` ends option scanning; the next token starts the tail.
EXEC_FRONTEND_PROFILES = {
    # singleton-daemon launcher: `flock [opts] LOCKFILE cmd...` OR `flock -c 'str'`
    "flock": {
        "opts_with_arg": frozenset({"-w", "--timeout", "-E", "--conflict-exit-code"}),
        "leading_positionals": 1,
        "payload_opts": frozenset({"-c", "--command"}),
    },
    # sandbox: `firejail [opts] cmd...` (its own opts are mostly --opt=value)
    "firejail": {"opts_with_arg": frozenset(), "leading_positionals": 0},
    # namespace: `unshare [opts] cmd...`. `--wd <dir>` chdirs the wrapped cmd.
    "unshare": {
        "opts_with_arg": frozenset({
            "--map-user", "--map-group", "--setgroups", "--wd", "--wd=",
            "--mount", "--propagation", "-S", "--setuid", "-G", "--setgid",
        }),
        "leading_positionals": 0,
        "cwd_opts": frozenset({"--wd"}),
    },
    # enter ns: `nsenter [opts] cmd...`
    "nsenter": {
        "opts_with_arg": frozenset({
            "-t", "--target", "-S", "--setuid", "-G", "--setgid",
            "--wd", "--wdns", "-T", "--timens",
        }),
        "leading_positionals": 0,
    },
    # privilege switch: `runuser -u USER -- cmd...` OR `runuser [opts] USER -c 'str'`
    # runuser also accepts the USER as an optional LEADING positional (the form
    # without -u): `runuser root -c 'str'`. Treat a bare positional before the
    # payload/tail as the user operand (consume_user_positional).
    "runuser": {
        "opts_with_arg": frozenset({"-u", "--user", "-g", "--group", "-G", "--supp-group", "-s", "--shell"}),
        "leading_positionals": 0,
        "consume_user_positional": True,
        "payload_opts": frozenset({"-c", "--command", "--session-command"}),
    },
    # privilege switch: `su [opts] [USER] -c 'str'` OR `su USER cmd?`. The USER is
    # an optional leading positional; -c/--command/--session-command may appear
    # before OR after it. Consume one bare positional as the user before the tail.
    "su": {
        "opts_with_arg": frozenset({"-g", "--group", "-G", "--supp-group", "-s", "--shell"}),
        "leading_positionals": 0,
        "consume_user_positional": True,
        "payload_opts": frozenset({"-c", "--command", "--session-command"}),
    },
    # trace: `strace [opts] cmd...`
    "strace": {
        "opts_with_arg": frozenset({"-o", "-p", "-e", "-s", "-a", "-E", "-P", "-S", "-u", "-I", "-b", "-x"}),
        "leading_positionals": 0,
    },
    "ltrace": {
        "opts_with_arg": frozenset({"-o", "-p", "-e", "-s", "-a", "-E", "-l", "-u", "-n"}),
        "leading_positionals": 0,
    },
    # repeat-watch: `watch [opts] cmd...` (joins tail into a shell-evaluated str)
    "watch": {
        "opts_with_arg": frozenset({"-n", "--interval", "-d", "--differences"}),
        "leading_positionals": 0,
        "joins_tail_as_shell": True,
    },
    # cpu cap: `cpulimit [opts] -- cmd...`
    "cpulimit": {
        "opts_with_arg": frozenset({"-l", "--limit", "-p", "--pid", "-e", "--exe", "-c", "--cpu"}),
        "leading_positionals": 0,
    },
    # privilege drop: `setpriv [opts] cmd...`
    "setpriv": {
        "opts_with_arg": frozenset({
            "--reuid", "--regid", "--groups", "--inh-caps", "--ambient-caps",
            "--bounding-set", "--securebits", "--selinux-label", "--apparmor-profile",
        }),
        "leading_positionals": 0,
    },
    # resource limit: `prlimit [opts] cmd...`
    "prlimit": {
        "opts_with_arg": frozenset({"-p", "--pid"}),
        "leading_positionals": 0,
    },
    # perf: `perf <subcmd> [opts] cmd...` — its subcmd (stat/record/trace) is a
    # leading positional; opts before the tail are mostly --opt=value or no-arg.
    "perf": {
        "opts_with_arg": frozenset({"-o", "--output", "-p", "--pid", "-e", "--event", "-C", "--cpu"}),
        "leading_positionals": 1,
    },
    # valgrind: `valgrind [opts] cmd...` (opts are --opt=value)
    "valgrind": {"opts_with_arg": frozenset(), "leading_positionals": 0},
    # record-replay: `rr record cmd...` / `rr cmd...` — subcmd is a leading pos.
    "rr": {
        "opts_with_arg": frozenset({"-o", "--output-trace-dir"}),
        "leading_positionals": 1,
    },
    # bubblewrap: `bwrap [opts] cmd...`. `--chdir <dir>` chdirs the wrapped cmd.
    "bwrap": {
        "opts_with_arg": frozenset({
            "--bind", "--ro-bind", "--dev-bind", "--chdir", "--setenv",
            "--unsetenv", "--uid", "--gid", "--hostname", "--proc", "--dev", "--tmpfs",
        }),
        "leading_positionals": 0,
        "cwd_opts": frozenset({"--chdir"}),
    },
    # chroot: `chroot [opts] NEWROOT cmd...` (NEWROOT relocates the fs root — a
    # protected RELATIVE tail under it cannot be proven non-protected; the
    # leading-positional consumption + tail re-analysis stays conservative).
    "chroot": {
        "opts_with_arg": frozenset({"--userspec", "--groups"}),
        "leading_positionals": 1,
    },
    # proot: `proot [opts] cmd...`. `-w/--cwd <dir>` chdirs the wrapped cmd.
    "proot": {
        "opts_with_arg": frozenset({"-r", "--rootfs", "-w", "--cwd", "-b", "--bind", "-q", "--qemu", "-k", "--kernel-release"}),
        "leading_positionals": 0,
        "cwd_opts": frozenset({"-w", "--cwd"}),
    },
    # virtual X server: `xvfb-run [opts] cmd...`
    "xvfb-run": {
        "opts_with_arg": frozenset({"-n", "--server-num", "-s", "--server-args", "-f", "--auth-file", "-e", "--error-file", "-w", "--wait"}),
        "leading_positionals": 0,
    },
    # dbus session: `dbus-run-session [opts] -- cmd...`
    "dbus-run-session": {
        "opts_with_arg": frozenset({"--config-file", "--dbus-daemon"}),
        "leading_positionals": 0,
    },
    # gdb: `gdb [opts] --args cmd...` — the tail begins ONLY after `--args`.
    "gdb": {"opts_with_arg": frozenset({"-x", "--command", "-ex", "--eval-command"}), "leading_positionals": 0, "args_marker": "--args"},
    # lock-while-running variants of repeat: `repeat`/`timeout` already in
    # ENV_WRAPPERS; do not duplicate here.
}


# ── Tokenization that preserves redirections (> >> ) which shlex eats ────────

def _split_pipeline(command: str) -> list:
    """Split a bash command into simple commands across ; && || | and newlines.

    Conservative: operates on the raw text but only at unquoted top level by a
    cheap quote-aware scan. Returns a list of raw simple-command strings.
    """
    parts = []
    buf = []
    i = 0
    n = len(command)
    quote = None
    subst_depth = 0   # inside $(...) command substitution
    backtick = False  # inside `...` command substitution
    while i < n:
        c = command[i]
        if quote == "'":
            # single quotes: no escaping inside; only a matching ' ends it.
            buf.append(c)
            if c == "'":
                quote = None
            i += 1
            continue
        if quote == '"':
            # double quotes: backslash escapes ", \, $, `, newline — those do
            # NOT terminate the quote. Any other char (incl. an escaped ;/&/|)
            # stays inside the quote, so a quoted separator never splits.
            if c == "\\" and i + 1 < n and command[i + 1] in ('"', "\\", "$", "`", "\n"):
                buf.append(c); buf.append(command[i + 1]); i += 2; continue
            buf.append(c)
            if c == '"':
                quote = None
            i += 1
            continue
        # unquoted context
        if c in ("'", '"'):
            quote = c
            buf.append(c)
            i += 1
            continue
        if c == "\\" and i + 1 < n:
            buf.append(c)
            buf.append(command[i + 1])
            i += 2
            continue
        # command-substitution tracking: separators inside $()/`` do NOT split
        # the OUTER simple command (the whole substitution belongs to it).
        if c == "`":
            backtick = not backtick
            buf.append(c); i += 1; continue
        if command[i:i + 2] in ("$(", "<(", ">("):
            subst_depth += 1
            buf.append(command[i:i + 2]); i += 2; continue
        if c == ")" and subst_depth > 0:
            subst_depth -= 1
            buf.append(c); i += 1; continue
        if subst_depth > 0 or backtick:
            buf.append(c); i += 1; continue
        # fd-redirection `&` (2>&1, >&, &>, &>>, >&2) is NOT a separator.
        if c == "&" and _is_redirect_amp(command, i):
            buf.append(c); i += 1; continue
        two = command[i:i + 2]
        if two in ("&&", "||", "|&"):
            parts.append("".join(buf)); buf = []; i += 2; continue
        if c in (";", "|", "\n", "&"):
            parts.append("".join(buf)); buf = []; i += 1; continue
        buf.append(c)
        i += 1
    parts.append("".join(buf))
    return [p.strip() for p in parts if p.strip()]


def _is_redirect_amp(command: str, i: int) -> bool:
    """True if the `&` at index i is part of an fd redirection, not a separator.

    Forms: `>&`, `<&`, `&>`, `&>>`, `2>&1`, `>&2`. Heuristic: preceded by a
    redirection operator (`>`/`<` possibly with a leading fd digit) OR followed
    by `>`/a digit/`-` (the `&>file` / `&>>file` form). `&&` is handled earlier.
    """
    n = len(command)
    nxt = command[i + 1] if i + 1 < n else ""
    if nxt == "&":
        return False  # `&&` control operator
    # &>file / &>>file / &- forms
    if nxt in (">", "-") or nxt.isdigit():
        return True
    # preceding char is a redirection operator (>& / <&), optionally fd-prefixed
    j = i - 1
    while j >= 0 and command[j] == " ":
        j -= 1
    if j >= 0 and command[j] in (">", "<"):
        return True
    return False


def _strip_compound_delims(command: str) -> str:
    """Neutralize shell compound-group delimiters `( ) { }` at the UNQUOTED top
    level by replacing them with a `;` separator, so a grouped launch/build
    (`(cd x && npx tsc)`, `{ cd x; node y; }`) decomposes into ordinary simple
    commands the splitters already handle. Conservative for a security guard:
    turning a group boundary into a separator can only split MORE (never hide a
    command word), so it cannot cause under-blocking. Quote/escape aware.
    """
    out = []
    i = 0
    n = len(command)
    quote = None
    subst_depth = 0  # `$(` depth — its `)` must be preserved, not neutralized
    brace_expr_depth = 0  # `${` depth — its `}` must be preserved
    while i < n:
        c = command[i]
        if quote == "'":
            out.append(c)
            if c == "'":
                quote = None
            i += 1
            continue
        if quote == '"':
            if c == "\\" and i + 1 < n and command[i + 1] in ('"', "\\", "$", "`", "\n"):
                out.append(c); out.append(command[i + 1]); i += 2; continue
            out.append(c)
            if c == '"':
                quote = None
            i += 1
            continue
        if c in ("'", '"'):
            quote = c
            out.append(c)
            i += 1
            continue
        if c == "\\" and i + 1 < n:
            out.append(c); out.append(command[i + 1]); i += 2; continue
        # `$(` command substitution and `${` parameter expansion are preserved
        # intact (their closing `)`/`}` is NOT a compound-group delimiter).
        # Process substitutions `<(...)` / `>(...)` are likewise preserved so a
        # kill/xargs fed by `<(pgrep -f <ident>)` keeps the inner pipeline intact
        # for P6 connectivity analysis.
        if command[i:i + 2] in ("<(", ">("):
            subst_depth += 1
            out.append(command[i:i + 2]); i += 2; continue
        if command[i:i + 2] == "$(":
            subst_depth += 1
            out.append("$("); i += 2; continue
        if command[i:i + 2] == "${":
            brace_expr_depth += 1
            out.append("${"); i += 2; continue
        if c == ")" and subst_depth > 0:
            subst_depth -= 1
            out.append(c); i += 1; continue
        if c == "}" and brace_expr_depth > 0:
            brace_expr_depth -= 1
            out.append(c); i += 1; continue
        if subst_depth > 0 or brace_expr_depth > 0:
            out.append(c); i += 1; continue
        # Parentheses are always sub-shell group delimiters → `;`.
        if c in ("(", ")"):
            out.append(" ; "); i += 1; continue
        # Braces are a command GROUP only as standalone `{`/`}` words:
        # `{ cmd; }`. An adjacent `{}` (xargs replstr), `{a,b}` brace expansion,
        # or `-I{}` must be left intact (mangling them breaks legitimate parsing
        # and can hide an xargs placeholder). Treat `{` as a group open only when
        # followed by whitespace, and `}` as a group close only when preceded by
        # whitespace or `;`.
        if c == "{" and i + 1 < n and command[i + 1] in (" ", "\t"):
            out.append(" ; "); i += 1; continue
        if c == "}" and out and out[-1] in (" ", "\t", ";"):
            out.append(" ; "); i += 1; continue
        out.append(c)
        i += 1
    return "".join(out)


def _has_redirect_to(simple_cmd: str) -> Optional[str]:
    """Return the redirect target path if the simple command writes via > / >>.

    Best-effort: finds an unquoted > or >> and returns the next bareword token.
    """
    m = re.search(r"(?<![0-9<>])>>?\s*([^\s;&|<>]+)", simple_cmd)
    if m:
        return _strip_quotes(m.group(1))
    return None


def _strip_quotes(tok: str) -> str:
    if len(tok) >= 2 and tok[0] == tok[-1] and tok[0] in ("'", '"'):
        return tok[1:-1]
    return tok


def _safe_shlex(simple_cmd: str) -> list:
    try:
        return shlex.split(simple_cmd, comments=False)
    except ValueError:
        # Unbalanced quotes etc. — fall back to whitespace split.
        return [t for t in re.split(r"\s+", simple_cmd) if t]


# ── Path normalization + segment-boundary suffix matching ────────────────────

def _normalize_path(raw: str) -> str:
    p = _strip_quotes(raw)
    if p.startswith("~"):
        p = os.path.expanduser(p)
    # collapse ./ and ../ logically without touching the filesystem
    p = os.path.normpath(p)
    return p


def _glob_to_segment_regex(glob: str) -> re.Pattern:
    """Translate a data-file glob into a segment-boundary SUFFIX regex.

    `**/a/b` matches any path ending in segments .../a/b (absolute or relative).
    `*` matches within a single segment (no /). `**` matches across segments.
    A leading absolute glob (/usr/bin/x*) anchors at string start.
    """
    g = glob
    anchored = g.startswith("/")
    # Tokenize the glob into literal/star chunks.
    out = []
    i = 0
    n = len(g)
    while i < n:
        if g[i:i + 2] == "**":
            # ** -> match anything including /
            out.append(".*")
            i += 2
            # swallow a following slash so **/x doesn't force a leading /
            if i < n and g[i] == "/":
                out.append("/?")
                i += 1
        elif g[i] == "*":
            out.append("[^/]*")
            i += 1
        else:
            out.append(re.escape(g[i]))
            i += 1
    body = "".join(out)
    if anchored:
        pattern = "^" + body + "$"
    else:
        # suffix match at a segment boundary: start of string OR after a '/'
        pattern = "(^|/)" + body + "$"
    return re.compile(pattern)


def _path_matches_any(path: str, globs: list) -> bool:
    norm = _normalize_path(path)
    candidates = {norm, path, _strip_quotes(path)}
    real = None
    try:
        if os.path.exists(norm):
            real = os.path.realpath(norm)
            candidates.add(real)
    except OSError:
        pass
    for glob in globs:
        rx = _glob_to_segment_regex(glob)
        for cand in candidates:
            if rx.search(cand):
                return True
    return False


def _any_token_path_matches(tokens: list, globs: list) -> bool:
    for tok in tokens:
        st = _strip_quotes(tok)
        if not st or st.startswith("-"):
            continue
        if _path_matches_any(st, globs):
            return True
    return False


def _path_under_any(path: str, dir_globs: list) -> bool:
    """True if `path` equals OR is located under a directory matching a dir glob.

    A build-path glob like `**/packages/<pkg>` is a DIRECTORY; a token such as
    `packages/<pkg>/tsconfig.json` lives under it and must match.
    """
    norm = _normalize_path(path)
    parts = norm.split("/")
    # test the path itself and each ancestor against the dir globs as a suffix
    for i in range(len(parts), 0, -1):
        prefix = "/".join(parts[:i])
        if not prefix:
            continue
        if _path_matches_any(prefix, dir_globs):
            return True
    return False


def _any_token_under(tokens: list, dir_globs: list) -> bool:
    for tok in tokens:
        st = _strip_quotes(tok)
        if not st or st.startswith("-"):
            continue
        if _path_under_any(st, dir_globs):
            return True
    return False


# Build-tool option flags whose VALUE is a path the build reads/writes. Only
# these path-valued flags have their RHS inspected for protected paths — a
# generic key/value flag (`--define:X=...`, `--mode`, `--env.X=...`) carries an
# arbitrary value, not a build target, and must NOT trigger a path match.
_PATH_VALUED_BUILD_FLAGS = frozenset({
    "--project", "-p", "--tsconfig", "--config", "-c", "--outfile", "-o",
    "--outdir", "--out-dir", "--out", "--build", "-b", "--rootdir", "--rootDir",
    "--declarationDir", "--tsBuildInfoFile",
})


def _flagvalue_path_candidates(tokens: list) -> list:
    """Yield path RHS values of a `--flag=value` option ONLY when the flag is a
    known path-valued build flag (so `--project=<path>`, `--outfile=<path>`,
    `--tsconfig=<path>` are inspected, but `--define:X=<anything>` is not)."""
    out = []
    for tok in tokens:
        st = _strip_quotes(tok)
        if st.startswith("-") and "=" in st:
            flag, val = st.split("=", 1)
            if val and flag in _PATH_VALUED_BUILD_FLAGS:
                out.append(val)
    return out


def _resolve_rel(val: str, cwd: Optional[str], cwd_det: bool) -> list:
    """Return path candidates for a token: itself, plus its resolution against a
    determinate effective cwd (so a relative `../<pkg>/tsconfig.json` from a
    sibling package resolves to the protected build path)."""
    cands = [val]
    st = _strip_quotes(val)
    if cwd and cwd_det and st and not os.path.isabs(st):
        cands.append(os.path.normpath(os.path.join(cwd, st)))
    return cands


def _path_is_protected_build(path: str, cfg: dict) -> bool:
    """True if `path` is under a protected build path. A RELATIVE build-path glob
    (`**/packages/<pkg>`) is suffix-matching and would also match an UNRELATED
    project's identically-named dir, so it is honored only when the resolved path
    is under a protected monorepo root. An ABSOLUTE glob is honored as-is."""
    bpaths = cfg.get("protected_build_paths", [])
    abs_globs = [g for g in bpaths if g.startswith("/")]
    rel_globs = [g for g in bpaths if not g.startswith("/")]
    if abs_globs and (_path_under_any(path, abs_globs) or _path_matches_any(path, abs_globs)):
        return True
    if rel_globs and (_path_under_any(path, rel_globs) or _path_matches_any(path, rel_globs)):
        # A relative-glob match on an ABSOLUTE path could be an unrelated
        # project's same-named dir → require it under a protected root. A
        # RELATIVE path (cwd unknown / repo-relative) cannot be disambiguated →
        # fail CLOSED (treat as protected); only an ABSOLUTE path OUTSIDE every
        # protected root is exonerated.
        if os.path.isabs(os.path.normpath(path)):
            return _dir_under_any_root(path, cfg)
        return True
    return False


def _any_token_under_incl_flagvalue(tokens: list, cfg: dict,
                                    cwd: Optional[str] = None, cwd_det: bool = False) -> bool:
    """Match any bare path token OR known path-valued `--flag=value` RHS against
    the (root-qualified) protected build paths, resolving relative paths against
    the effective cwd (covers `tsc -p ../<pkg>/tsconfig.json` from a sibling
    package) while NOT matching an unrelated project's same-named dir."""
    for tok in tokens:
        st = _strip_quotes(tok)
        if not st or st.startswith("-"):
            continue
        for cand in _resolve_rel(st, cwd, cwd_det):
            if _path_is_protected_build(cand, cfg):
                return True
    for val in _flagvalue_path_candidates(tokens):
        for cand in _resolve_rel(val, cwd, cwd_det):
            if _path_is_protected_build(cand, cfg):
                return True
    return False


def _explicit_nonprotected_build_target(tokens: list, cfg: dict,
                                        cwd: Optional[str], cwd_det: bool) -> bool:
    """True if a path-valued build flag points DETERMINATELY at a target OUTSIDE
    every protected build path (so a build-mode fallback must not over-block a
    `tsc -w -p packages/<non-protected>/tsconfig.json` at the monorepo root)."""
    vals = list(_flagvalue_path_candidates(tokens))
    # also the space-separated `-p <path>` / `--project <path>` form
    i = 0
    while i < len(tokens):
        t = _strip_quotes(tokens[i])
        if t in _PATH_VALUED_BUILD_FLAGS and i + 1 < len(tokens):
            nv = _strip_quotes(tokens[i + 1])
            if not nv.startswith("-"):
                vals.append(nv)
            i += 2
            continue
        i += 1
    if not vals:
        return False
    for v in vals:
        # if ANY explicit target resolves under a protected path -> not exempt
        for cand in _resolve_rel(v, cwd, cwd_det):
            if _path_is_protected_build(cand, cfg):
                return False
        # an unresolvable relative target -> cannot prove non-protected
        if not os.path.isabs(_strip_quotes(v)) and not (cwd and cwd_det):
            return False
    return True


# ── Command-word position scanning ───────────────────────────────────────────

def _command_words(tokens: list) -> list:
    """Return the effective command-word of a simple command after consuming
    VAR=val env-prefixes and wrapper commands.
    Returns a list with one tuple (head_index, head_basename, args_after_head)
    where args_after_head EXCLUDES the head token itself.
    """
    i = 0
    n = len(tokens)
    # Skip leading shell keywords that introduce a command (`do`, `then`,
    # `else`, `;`-separated loop bodies) so the real command word in a loop /
    # conditional body is reached (`do kill $pid` → head 'kill').
    while i < n and _strip_quotes(tokens[i]) in ("do", "then", "else", "{", "!"):
        i += 1
    # Skip VAR=val env assignments.
    while i < n and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[i]):
        i += 1
    # Skip wrapper commands (env/sudo/command/nohup/timeout/setsid/...), each
    # with its own operand schema, until the real command word is reached.
    while i < n:
        base = os.path.basename(_strip_quotes(tokens[i]))
        if base not in ENV_WRAPPERS:
            break
        opts_with_arg = _WRAPPER_OPTS_WITH_ARG.get(base, frozenset())
        i += 1
        value_opt_seen = False
        # consume this wrapper's options (and their operands) and env VAR=val.
        while i < n:
            t = tokens[i]
            if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", t):
                i += 1
                continue
            if t == "--":
                i += 1
                break
            if t in opts_with_arg:
                value_opt_seen = True
                i += 2
                continue
            if "=" in t and t.startswith("-"):
                # --opt=value form: single token
                i += 1
                continue
            if t.startswith("-"):
                i += 1
                continue
            break
        # consume a single leading positional operand for wrappers that take one
        # (timeout DURATION, chrt PRIORITY, taskset MASK, setarch ARCH). For the
        # optional-positional wrappers (chrt/taskset) skip the consumption when a
        # value option already supplied the operand, so `taskset -c 0 <cmd>`
        # still exposes <cmd> as the command word.
        if base in _WRAPPER_LEADING_POSITIONAL and i < n:
            if not (base in _WRAPPER_POSITIONAL_OPTIONAL and value_opt_seen):
                i += 1
    if i >= n:
        return []
    return [(i, os.path.basename(_strip_quotes(tokens[i])), tokens[i + 1:])]


# Wrapper options that set the working directory (chdir) for the wrapped command.
# env -C/--chdir, sudo -D/--chdir, doas -C, systemd-run --working-directory.
_WRAPPER_CWD_OPTS = frozenset({"-C", "--chdir", "-D", "--working-directory"})
# Short cwd opts that may FUSE their value (env -C<dir>, sudo -D<dir>).
_WRAPPER_CWD_SHORT_FUSABLE = ("-C", "-D")


def _wrapper_cwd(tokens: list):
    """Extract a chdir directory set by a leading env/sudo/doas wrapper.

    Returns (dir|None, determinate). `env -C <dir>`, `env --chdir <dir>`,
    `sudo -D <dir>`, `sudo --chdir <dir>`, `doas -C <dir>` all change the
    working directory of the wrapped command. A dynamic operand ($/`/glob)
    yields (None, False) so callers fail closed for protected verb families.
    """
    i = 0
    n = len(tokens)
    while i < n and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[i]):
        i += 1
    found = None
    determinate = True
    while i < n:
        base = os.path.basename(_strip_quotes(tokens[i]))
        if base not in ENV_WRAPPERS:
            break
        i += 1
        value_opt_seen = False
        while i < n:
            t = tokens[i]
            if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", t):
                i += 1
                continue
            if t == "--":
                i += 1
                break
            if t in _WRAPPER_CWD_OPTS and i + 1 < n:
                val = _strip_quotes(tokens[i + 1])
                if any(ch in val for ch in ("$", "`", "*", "?")):
                    determinate = False
                else:
                    found = val
                i += 2
                continue
            _fused = None
            for opt in _WRAPPER_CWD_OPTS:
                if t.startswith(opt + "="):
                    _fused = t.split("=", 1)[1]
                    break
            if _fused is None:
                # short fused form: env -C<dir> / sudo -D<dir> (no separator)
                for opt in _WRAPPER_CWD_SHORT_FUSABLE:
                    if t.startswith(opt) and len(t) > len(opt) and not t[len(opt)] == "=":
                        _fused = t[len(opt):]
                        break
            if _fused is not None:
                val = _strip_quotes(_fused)
                if any(ch in val for ch in ("$", "`", "*", "?")):
                    determinate = False
                else:
                    found = val
                i += 1
                continue
            opts_with_arg = _WRAPPER_OPTS_WITH_ARG.get(base, frozenset())
            if t in opts_with_arg:
                value_opt_seen = True
                i += 2
                continue
            if "=" in t and t.startswith("-"):
                i += 1
                continue
            if t.startswith("-"):
                i += 1
                continue
            break
        if base in _WRAPPER_LEADING_POSITIONAL and i < n:
            if not (base in _WRAPPER_POSITIONAL_OPTIONAL and value_opt_seen):
                i += 1
    return (found, determinate)


def _fold_wrapper_cwd(cwd: Optional[str], cwd_det: bool, tokens: list):
    """Fold a leading wrapper chdir (env -C/sudo --chdir) into the effective cwd."""
    wdir, wdet = _wrapper_cwd(tokens)
    if not wdet:
        return (cwd, False)
    if wdir is None:
        return (cwd, cwd_det)
    if os.path.isabs(wdir):
        return (os.path.normpath(wdir), True)
    if cwd:
        return (os.path.normpath(os.path.join(cwd, wdir)), cwd_det)
    return (os.path.normpath(wdir), False)


# ── command-substitution extraction ──────────────────────────────────────────

def _command_substitutions(text: str) -> list:
    """Return the inner text of every $(...) command substitution (top level and
    nested, flattened) and every `...` backtick substitution found in `text`.

    Used so a kill executor whose argument list is computed by an embedded
    pipeline — e.g. `kill $(ps aux | grep <ident> | awk '{print $2}')` — can be
    inspected for a protected identifier inside the substitution.
    """
    out = []
    n = len(text)
    i = 0
    while i < n:
        # $(...) command substitution and <(...) / >(...) process substitution
        if (text[i] in ("$", "<", ">")) and i + 1 < n and text[i + 1] == "(":
            depth = 1
            j = i + 2
            start = j
            while j < n and depth > 0:
                if text[j] == "(":
                    depth += 1
                elif text[j] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            inner = text[start:j]
            out.append(inner)
            # recurse for nested $(...) inside this one
            out.extend(_command_substitutions(inner))
            i = j + 1
            continue
        if text[i] == "`":
            j = i + 1
            while j < n and text[j] != "`":
                j += 1
            out.append(text[i + 1:j])
            i = j + 1
            continue
        i += 1
    return out


# ── pipeline-group splitting (preserve | connectivity) ───────────────────────

def _pipeline_groups(command: str) -> list:
    """Split a command into pipeline GROUPS.

    Segments joined by `|` / `|&` belong to the SAME group (data flows between
    them); `;`, `&&`, `||`, `&`, and newlines separate groups. Each group is a
    list of its raw simple-command strings, in order. This preserves the
    upstream→downstream connectivity that cross-segment primitives (P5 endpoint,
    P6 prockill) need, which the flat `_split_pipeline` discards.
    """
    groups = []
    cur = []
    buf = []
    i = 0
    n = len(command)
    quote = None
    loop_depth = 0  # inside a do..done loop body fed by an upstream pipe
    subst_depth = 0
    backtick = False

    def flush_simple():
        nonlocal loop_depth
        s = "".join(buf).strip()
        if s:
            cur.append(s)
            # track loop nesting so `;`/newline inside a do..done body do NOT
            # break the pipe connectivity (`pgrep … | while read x; do kill x;
            # done` must stay ONE group for P6).
            words = s.split()
            for w in words:
                # increment ONLY on a loop OPENER (while/for/until); `do` is the
                # body marker of the SAME loop, not a new nesting level, so
                # counting it double-closes late and over-connects a later
                # top-level command (e.g. a trailing `; kill 123`) to the group.
                if w in ("while", "for", "until"):
                    loop_depth += 1
                elif w == "done":
                    loop_depth = max(0, loop_depth - 1)

    def flush_group():
        flush_simple()
        if cur:
            groups.append(list(cur))

    while i < n:
        c = command[i]
        if quote == "'":
            buf.append(c)
            if c == "'":
                quote = None
            i += 1
            continue
        if quote == '"':
            if c == "\\" and i + 1 < n and command[i + 1] in ('"', "\\", "$", "`", "\n"):
                buf.append(c); buf.append(command[i + 1]); i += 2; continue
            buf.append(c)
            if c == '"':
                quote = None
            i += 1
            continue
        if c in ("'", '"'):
            quote = c
            buf.append(c)
            i += 1
            continue
        if c == "\\" and i + 1 < n:
            buf.append(c); buf.append(command[i + 1]); i += 2; continue
        # command-substitution: keep `$(...)`/`` `...` `` intact within ONE
        # simple command so a kill-substitution's pipeline isn't split.
        if c == "`":
            backtick = not backtick
            buf.append(c); i += 1; continue
        if command[i:i + 2] in ("$(", "<(", ">("):
            subst_depth += 1
            buf.append(command[i:i + 2]); i += 2; continue
        if c == ")" and subst_depth > 0:
            subst_depth -= 1
            buf.append(c); i += 1; continue
        if subst_depth > 0 or backtick:
            buf.append(c); i += 1; continue
        # fd-redirection `&` is not a group separator.
        if c == "&" and _is_redirect_amp(command, i):
            buf.append(c); i += 1; continue
        two = command[i:i + 2]
        if two in ("&&", "||", "|&"):
            if two == "|&":
                # |& pipes stdout+stderr: stays within the SAME group
                flush_simple(); buf = []; i += 2; continue
            if loop_depth > 0:
                # &&/|| inside a loop body do not break pipe connectivity
                flush_simple(); buf = []; i += 2; continue
            flush_group(); cur = []; buf = []; i += 2; continue
        if c == "|":
            flush_simple(); buf = []; i += 1; continue
        if c in (";", "\n", "&"):
            flush_simple()
            if loop_depth <= 0:
                # outside a loop body: a real group separator
                if cur:
                    groups.append(list(cur)); cur = []
            buf = []; i += 1; continue
        buf.append(c)
        i += 1
    flush_group()
    return groups


# ── effective cwd tracking across a pipeline ──────────────────────────────────

def _cd_target(args: list) -> Optional[str]:
    """First real directory operand of a cd/pushd, skipping options.

    `cd [-L|-P|-e|-@] [--] DIR`. Returns None when no directory operand is
    present (e.g. bare `cd`, or `pushd +N`/`-N` stack rotation which is not a
    path change we model). The `--` terminator forces the next token as the dir.
    """
    i = 0
    n = len(args)
    while i < n:
        t = _strip_quotes(args[i])
        if t == "--":
            return _strip_quotes(args[i + 1]) if i + 1 < n else None
        if t.startswith("-") and re.match(r"^-[LPe@]+$", t):
            i += 1
            continue
        if t.startswith("-"):
            # pushd +N / -N stack rotation or an unknown flag: not a dir change
            return None
        return t
    return None


def _effective_cwd_after(simple_cmds: list, upto_index: int, cwd_base: Optional[str] = None):
    """Compute effective cwd from a known base cwd plus leading cd/pushd in the
    SAME chain.

    `cwd_base` seeds the resolution from the payload's reported cwd (or the
    process cwd). If a cd target is dynamic/unresolvable, determinate=False
    (caller fails closed). With a known base, a relative cd is resolvable.
    """
    cwd = os.path.normpath(cwd_base) if cwd_base else None
    determinate = True
    for j in range(upto_index):
        toks = _safe_shlex(simple_cmds[j])
        if not toks:
            continue
        base = os.path.basename(_strip_quotes(toks[0]))
        if base in ("cd", "pushd"):
            target = _cd_target(toks[1:])
            if target is None:
                continue
            if any(ch in target for ch in ("$", "`", "*", "?")):
                determinate = False
                continue
            if os.path.isabs(target):
                cwd = os.path.normpath(target)
            elif cwd:
                cwd = os.path.normpath(os.path.join(cwd, target))
            else:
                # relative cd with unknown base cwd -> best-effort, indeterminate
                cwd = os.path.normpath(target)
                determinate = False
    return cwd, determinate


# ── Config loading ───────────────────────────────────────────────────────────

REQUIRED_KEYS = (
    "protected_cmds", "protected_launch_paths", "protected_services",
    "protected_hotfiles", "protected_statefiles", "protected_endpoint_paths",
    "protected_proc_idents", "protected_global_bins",
    "protected_build_workspaces", "protected_build_paths",
)


def _load_config():
    """Return (config_dict | None). None means indeterminate (fail-closed)."""
    try:
        with open(DATA_FILE_PATH, "r", encoding="utf-8") as fh:
            cfg = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(cfg, dict):
        return None
    if cfg.get("schema_version") != 1:
        return None
    for k in REQUIRED_KEYS:
        if k not in cfg or not isinstance(cfg[k], list):
            return None
    return cfg


# ── STEP 0: config self-protection (hardcoded, generic path) ─────────────────

def _config_path_variants() -> set:
    p = DATA_FILE_PATH
    variants = {p, os.path.normpath(p)}
    if p.startswith("/root/"):
        variants.add(p.replace("/root/", "~/", 1))
    return variants


def _targets_config_file(simple_cmd: str, tokens: list) -> bool:
    cfg_variants = {_normalize_path(v) for v in _config_path_variants()}
    cfg_dir = os.path.dirname(DATA_FILE_PATH)
    # redirect to the config path
    rt = _has_redirect_to(simple_cmd)
    if rt and _normalize_path(rt) in cfg_variants:
        return True
    # any bareword token equal to the config path (cp/mv/rm/tee/sed -i/chmod/chown/truncate/ln)
    for tok in tokens:
        st = _strip_quotes(tok)
        if not st:
            continue
        norm = _normalize_path(st)
        if norm in cfg_variants:
            return True
        # mutation of the containing directory entry
        if norm == os.path.normpath(cfg_dir) and tokens and os.path.basename(_strip_quotes(tokens[0])) in (
            "rm", "rmdir", "mv", "chmod", "chown"
        ):
            return True
    return False


CONFIG_MUTATION_HEADS = frozenset({
    "cp", "mv", "rm", "tee", "truncate", "dd", "install", "ln", "chmod",
    "chown", "rename", "rsync", "shred", "unlink",
})


def _step0_self_protection(simple_cmds: list) -> Optional[Verdict]:
    for sc in simple_cmds:
        tokens = _safe_shlex(sc)
        if not tokens:
            continue
        cw = _command_words(tokens)
        head = cw[0][1] if cw else os.path.basename(_strip_quotes(tokens[0]))
        # redirect write to the config path (any head)
        rt = _has_redirect_to(sc)
        if rt and _normalize_path(rt) in {_normalize_path(v) for v in _config_path_variants()}:
            return _block("STEP0", "config self-protection: redirect to data file")
        # sed -i / perl -i targeting the config path
        if head in ("sed", "perl") and ("-i" in tokens or any(t.startswith("-i") for t in tokens)):
            if _targets_config_file(sc, tokens):
                return _block("STEP0", "config self-protection: in-place edit of data file")
        # mutation heads with the config path as an argument
        if head in CONFIG_MUTATION_HEADS and _targets_config_file(sc, tokens):
            return _block("STEP0", "config self-protection: mutation of data file")
    return None


# ── STEP 1: fail-closed indeterminate-policy verb families ───────────────────

def _step1_indeterminate(simple_cmds: list) -> Verdict:
    """When config is unavailable, block protected verb FAMILIES generically.
    Allow commands clearly outside those families.
    """
    for sc in simple_cmds:
        tokens = _safe_shlex(sc)
        if not tokens:
            continue
        cw = _command_words(tokens)
        if not cw:
            continue
        _, head, rest = cw[0]
        rest_bases = [os.path.basename(_strip_quotes(t)) for t in rest]
        # service control
        if head in ("systemctl", "service", "initctl"):
            if any(v in rest_bases for v in SERVICE_VERBS) or any(v in tokens for v in SERVICE_VERBS):
                return _block("STEP1", "indeterminate policy: service-control verb")
        # kill / proc control
        if head in KILL_VERBS:
            return _block("STEP1", "indeterminate policy: process-kill verb")
        if head == "xargs" and any(b in KILL_VERBS for b in rest_bases):
            return _block("STEP1", "indeterminate policy: xargs kill")
        # package-manager script-run / build / global install
        if head in PKG_MANAGERS:
            if any("-g" == t or "--global" == t for t in rest):
                return _block("STEP1", "indeterminate policy: global package op")
            # any non-meta pm invocation is fail-closed (build/launch family)
            if not _is_meta_query(head, rest):
                return _block("STEP1", "indeterminate policy: package-manager invocation")
        # bare build tools
        if head in BUILD_TOOL_BASENAMES:
            return _block("STEP1", "indeterminate policy: build tool")
        # runtime launch (node/tsx/bun ... .mjs/.ts) — ambiguous launch
        if head in RUNTIMES:
            return _block("STEP1", "indeterminate policy: runtime launch")
        # package runners
        if head in ("npx", "bunx"):
            return _block("STEP1", "indeterminate policy: package runner")
        # ── HEAD-AGNOSTIC fail-closed tail scan ──────────────────────────────
        # Behind a novel exec front-end (an undocumented process/exec wrapper) the
        # head is the wrapper, so the head-keyed checks above miss the danger
        # family in the tail. When the head is NOT a read/inspect/edit operation,
        # scan ALL exec-position tokens for the generic danger families so a
        # front-end-wrapped build/runtime/kill/service/pm invocation still blocks
        # under an absent/corrupt config (the leak must not survive fail-closed).
        if not _is_inspection_command(head, rest):
            exec_bases = [os.path.basename(_strip_quotes(t)) for _i, t in _anchor_exec_tokens(tokens)]
            if any(b in KILL_VERBS for b in exec_bases):
                return _block("STEP1", "indeterminate policy: process-kill verb (tail)")
            if any(b in ("systemctl", "service", "initctl") for b in exec_bases) and (
                    any(v in [os.path.basename(_strip_quotes(t)) for t in tokens] for v in SERVICE_VERBS)):
                return _block("STEP1", "indeterminate policy: service-control verb (tail)")
            if any(b in PKG_MANAGERS for b in exec_bases):
                return _block("STEP1", "indeterminate policy: package-manager invocation (tail)")
            if any(b in BUILD_TOOL_BASENAMES for b in exec_bases):
                return _block("STEP1", "indeterminate policy: build tool (tail)")
            if any(b in RUNTIMES for b in exec_bases):
                return _block("STEP1", "indeterminate policy: runtime launch (tail)")
            if any(b in ("npx", "bunx") for b in exec_bases):
                return _block("STEP1", "indeterminate policy: package runner (tail)")
    return ALLOW


# ── P1 LAUNCH_GUARD ──────────────────────────────────────────────────────────

def _is_meta_query(pm_head: str, rest: list) -> bool:
    """A meta query has ONLY a version/help flag and no script token/subcommand."""
    nonflag = [t for t in rest if not t.startswith("-")]
    flags = [t for t in rest if t.startswith("-")]
    if nonflag:
        return False
    meta = {"--version", "-v", "--help", "-h", "-V"}
    return all(f in meta for f in flags) and len(flags) >= 1


def _path_matches_cwd(raw: str, globs: list, cwd: Optional[str], cwd_det: bool) -> bool:
    """Match a token against globs as itself AND, if relative and cwd known,
    resolved against the effective cwd. Drops a leading ./ for the relative case.
    """
    if _path_matches_any(raw, globs):
        return True
    st = _strip_quotes(raw)
    if cwd and cwd_det and not os.path.isabs(st):
        resolved = os.path.normpath(os.path.join(cwd, st))
        if _path_matches_any(resolved, globs):
            return True
    return False


def _runtime_target(rest: list) -> Optional[str]:
    """Find the first real script positional after a runtime's options.
    Skips runtime flags that consume a value (--loader X, -r X, etc.) and a
    single leading runtime subcommand (deno run / tsx watch / bun run) that
    precedes the script positional."""
    i = 0
    n = len(rest)
    subcmd_skipped = False
    while i < n:
        t = rest[i]
        if t == "--":
            i += 1
            continue
        if t in _RUNTIME_OPTS_WITH_ARG:
            i += 2
            continue
        if t.startswith("-"):
            # --opt=value or a value-less flag: single token
            i += 1
            continue
        st = _strip_quotes(t)
        # Skip ONE leading runtime subcommand (run/watch) — a bare word with no
        # path separator/extension — so the protected script positional after it
        # is reached. Never skips a real filename.
        if (not subcmd_skipped and st in _RUNTIME_SUBCOMMANDS
                and i + 1 < n and "/" not in st and "." not in st):
            subcmd_skipped = True
            i += 1
            continue
        return st
    return None


# Runtime options whose VALUE is a module that is preloaded/executed (so the
# protected bundle/src can run without being the script positional).
_RUNTIME_PRELOAD_OPTS = frozenset({"-r", "--require", "--import", "--loader", "--experimental-loader"})


def _runtime_preload_hits(rest: list, launch_paths: list, cwd: Optional[str], cwd_det: bool) -> bool:
    i = 0
    n = len(rest)
    while i < n:
        t = rest[i]
        if t in _RUNTIME_PRELOAD_OPTS and i + 1 < n:
            if _path_matches_cwd(_strip_quotes(rest[i + 1]), launch_paths, cwd, cwd_det):
                return True
            i += 2
            continue
        for opt in _RUNTIME_PRELOAD_OPTS:
            if t.startswith(opt + "="):
                if _path_matches_cwd(_strip_quotes(t.split("=", 1)[1]), launch_paths, cwd, cwd_det):
                    return True
        i += 1
    return False


def _node_run_script(rest: list) -> Optional[str]:
    """Return the script token of `node --run <script>` / `node --run=<script>`
    (Node 22+ package-script runner), else None."""
    for i, t in enumerate(rest):
        st = _strip_quotes(t)
        if st == "--run" and i + 1 < len(rest):
            return _strip_quotes(rest[i + 1])
        if st.startswith("--run="):
            return _strip_quotes(st.split("=", 1)[1])
    return None


def _upstream_text_in_group(groups: list, sc: str) -> str:
    """Return the concatenated text of segments UPSTREAM of `sc` within the
    pipeline group that contains it (empty if not found or first in group).

    An xargs/while-read consumer's argv is sourced from the upstream segments'
    stdout, so a protected launch path or command emitted upstream feeds the
    consumer even though it never appears in the consumer's own tokens.
    """
    target = sc.strip()
    for group in groups:
        for k, seg in enumerate(group):
            if seg.strip() == target:
                return " ".join(group[:k])
    return ""


def _selector_cwd(head: str, rest: list, cfg: dict, cwd: Optional[str], cwd_det: bool):
    """If a PM workspace selector (yarn workspace <ws> / -w / --filter / pnpm -C)
    is present, resolve it to the selected workspace's manifest dir so a
    subsequent exec'd runtime/build resolves relative protected paths against the
    SELECTED workspace (not the shell cwd). Returns (cwd, cwd_det) updated.

    A determinate resolution to a known workspace dir threads that dir as the
    effective cwd. An unresolvable selector leaves cwd_det False (fail-closed for
    relative-path families). Non-PM heads or no selector return cwd unchanged.
    """
    if head not in PKG_MANAGERS:
        return (cwd, cwd_det)
    sel = _explicit_workspace_selector(head, rest)
    if sel is None or sel == "<MULTI>":
        return (cwd, cwd_det)
    man_dir, _is_protected, _scripts, det = _resolve_workspace_manifest(sel, cfg, cwd)
    if det and man_dir:
        return (os.path.normpath(man_dir), True)
    # selector named but unresolvable -> indeterminate for relative resolution
    return (cwd, False)


def _exec_subcommand_after_selector(head: str, rest: list):
    """For a PM `<sel> exec <runner> [args]` form, return (runner_basename,
    args_after_runner) so the post-exec launch can be routed through P1 with the
    selector-resolved cwd. Returns (None, []) if there is no exec/runner form."""
    # find an exec/dlx/x keyword AFTER the selector token; the selector value was
    # already consumed by _explicit_workspace_selector, so scan all of rest.
    i = 0
    while i < len(rest):
        if rest[i] in ("exec", "dlx", "x"):
            toks = rest[i + 1:]
            j = 0
            while j < len(toks):
                t = toks[j]
                if t == "--":
                    j += 1
                    continue
                if t in ("-w", "--workspace", "--filter", "-F", "--prefix", "-C", "--dir", "--cwd") and j + 1 < len(toks):
                    j += 2
                    continue
                if any(t.startswith(f + "=") for f in ("--workspace", "--filter", "-F", "--prefix", "-C", "--dir", "--cwd", "-w")):
                    j += 1
                    continue
                if t in _RUNNER_OPTS_WITH_ARG:
                    j += 2
                    continue
                if t.startswith("-"):
                    j += 1
                    continue
                return (os.path.basename(_strip_quotes(t)), toks[j + 1:])
            return (None, [])
        i += 1
    return (None, [])


def _p1_launch(simple_cmds: list, cfg: dict, cwd_base: Optional[str] = None,
               groups: Optional[list] = None) -> Optional[Verdict]:
    cmds = set(cfg.get("protected_cmds", []))
    launch_paths = cfg.get("protected_launch_paths", [])
    groups = groups or []
    for idx, sc in enumerate(simple_cmds):
        tokens = _safe_shlex(sc)
        if not tokens:
            continue
        cw = _command_words(tokens)
        if not cw:
            continue
        tok_idx, head, rest = cw[0]
        # effective cwd for relative-path resolution (cd/pushd in the chain),
        # then fold any leading wrapper chdir (env -C/sudo --chdir) into it.
        cwd, cwd_det = _effective_cwd_after(simple_cmds, idx, cwd_base)
        cwd, cwd_det = _fold_wrapper_cwd(cwd, cwd_det, tokens)
        # fold a PM workspace selector's resolved dir into the effective cwd so a
        # `yarn workspace <ws> exec node dist/index.mjs ...` resolves the relative
        # protected path against the SELECTED workspace.
        cwd, cwd_det = _selector_cwd(head, rest, cfg, cwd, cwd_det)
        # PM `<selector> exec <runtime> <path> …` — route the post-exec runner
        # through the launch logic with the selector-resolved cwd.
        ex_runner, ex_args = _exec_subcommand_after_selector(head, rest)
        if ex_runner is not None:
            if ex_runner in cmds:
                return _block("P1", f"workspace-selected exec of protected command '{ex_runner}'")
            # a recursive/all-workspace (`-r`/`--filter '*'`) exec fans out into
            # EVERY workspace incl. the protected one — fail closed when the exec
            # target is a runtime / build tool (it would run in the protected pkg).
            if (head in PKG_MANAGERS and _explicit_workspace_selector(head, rest) == "<MULTI>"
                    and (ex_runner in RUNTIMES or ex_runner in BUILD_TOOL_BASENAMES)):
                return _block("P1", "recursive/all-workspace exec of a runtime/build (fans into protected workspace)")
            if ex_runner in RUNTIMES:
                ex_pos = _runtime_target(ex_args)
                if ex_pos is not None and _path_matches_cwd(ex_pos, launch_paths, cwd, cwd_det):
                    return _block("P1", "workspace-selected exec runtime launch of protected path")
            if _path_matches_cwd(ex_runner, launch_paths, cwd, cwd_det):
                return _block("P1", "workspace-selected exec of protected launch path")
        # direct basename launch
        if head in cmds:
            return _block("P1", f"launch of protected command '{head}'")
        # runtime launching a protected path: node [opts] <path>
        if head in RUNTIMES:
            tgt = _runtime_target(rest)
            if tgt is not None and _path_matches_cwd(tgt, launch_paths, cwd, cwd_det):
                return _block("P1", "runtime launch of protected path")
            # a preload/execute option VALUE (`--import <path>`, `-r <path>`,
            # `--require=<path>`) executes the protected module even without a
            # script positional (`node --import <protected> -e ""`).
            if _runtime_preload_hits(rest, launch_paths, cwd, cwd_det):
                return _block("P1", "runtime preload/import of protected path")
            # `node --run <script>` (Node script runner) routes to the package
            # script of the effective cwd — treat as a bare script-run via P9/P8.
            nrun = _node_run_script(rest)
            if nrun is not None and head in ("node", "nodejs"):
                if _cwd_in_protected_build_scope(cwd, cwd_det, cfg) or cwd is None or not cwd_det:
                    return _block("P1", "node --run in a protected/indeterminate cwd")
        # direct path execution (./...mjs) — the head IS the path
        full_head = _strip_quotes(tokens[tok_idx]) if tok_idx < len(tokens) else head
        if _path_matches_cwd(full_head, launch_paths, cwd, cwd_det):
            return _block("P1", "direct execution of protected launch path")
        # package-runner exec targets: npx/bunx <cmd>; npm exec/pnpm dlx/etc.
        runner_target, runner_args = _package_runner_invocation(head, rest)
        if runner_target is not None:
            if runner_target in cmds:
                return _block("P1", f"package-runner launch of protected command '{runner_target}'")
            # runner invoking a RUNTIME against a protected path:
            # `npx tsx packages/<cli>/src/index.ts`, `npm exec -- tsx <src>`.
            if runner_target in RUNTIMES:
                rpos = _runtime_target(runner_args)
                if rpos is not None and _path_matches_cwd(rpos, launch_paths, cwd, cwd_det):
                    return _block("P1", "package-runner runtime launch of protected path")
        # xargs executor: `... | xargs [opts] <cmd> [args]` runs <cmd> with the
        # piped input appended as arguments. Treat <cmd> as a virtual launch
        # command-word (basename against protected_cmds; runtime → protected
        # path positional). Covers `echo <subcmd> | xargs <protected-cmd>` and
        # `printf '<protected-path> <subcmd>' | xargs node`.
        if head == "xargs":
            xbase, xargs_after, uses_ph, _det = _xargs_effective_command(rest)
            upstream = _upstream_text_in_group(groups, sc)
            # `xargs -I{} {}` (or bare placeholder): the command is whatever the
            # upstream segment emits — scan upstream for a protected command or
            # launch path.
            if uses_ph:
                if upstream and (_text_carries_protected_cmd(upstream, cmds)
                                 or _text_carries_launch_path(upstream, launch_paths, cwd, cwd_det)):
                    return _block("P1", "xargs placeholder launch of an upstream-piped protected command/path")
            if xbase is not None:
                if xbase in cmds:
                    return _block("P1", f"xargs launch of protected command '{xbase}'")
                if xbase in RUNTIMES:
                    xpos = _runtime_target(xargs_after)
                    if xpos is not None and _path_matches_cwd(xpos, launch_paths, cwd, cwd_det):
                        return _block("P1", "xargs runtime launch of protected path")
                    # `printf '<protected-path> ...' | xargs [env] node` — path
                    # arrives via stdin from the upstream segment.
                    if upstream and _text_carries_launch_path(upstream, launch_paths, cwd, cwd_det):
                        return _block("P1", "xargs runtime launch of an upstream-piped protected path")
                # the xargs target itself is a protected launch path
                if _path_matches_cwd(xbase, launch_paths, cwd, cwd_det):
                    return _block("P1", "xargs execution of protected launch path")
                for a in xargs_after:
                    if _path_matches_cwd(_strip_quotes(a), launch_paths, cwd, cwd_det):
                        return _block("P1", "xargs execution of protected launch path arg")
    return None


def _text_carries_protected_cmd(text: str, cmds: set) -> bool:
    """True if any whitespace token of `text` is a protected command basename."""
    for raw in re.split(r"\s+", text):
        st = os.path.basename(_strip_quotes(raw.strip("'\"")))
        if st in cmds:
            return True
    return False


def _text_carries_launch_path(text: str, launch_paths: list, cwd: Optional[str], cwd_det: bool) -> bool:
    """True if any whitespace-delimited token inside `text` matches a protected
    launch path (absolute, or relative resolved against the effective cwd)."""
    for raw in re.split(r"\s+", text):
        st = _strip_quotes(raw.strip("'\""))
        if not st or st.startswith("-"):
            continue
        if _path_matches_cwd(st, launch_paths, cwd, cwd_det):
            return True
    return False


def _xargs_target(rest: list):
    """Return (index_in_rest, target_command) for `xargs [opts] <cmd> ...`.

    Skips xargs's own options, consuming the operand of those that take one
    (-I/-n/-P/-d/-E/-s/--max-args/etc.). Returns (None, None) if no target
    command word follows (then xargs defaults to echo — not a launch).
    """
    opts_with_arg = frozenset({
        "-I", "-i", "--replace", "-n", "--max-args", "-L", "--max-lines",
        "-P", "--max-procs", "-d", "--delimiter", "-E", "-e", "--eof",
        "-s", "--max-chars", "-a", "--arg-file",
    })
    i = 0
    n = len(rest)
    while i < n:
        t = rest[i]
        st = _strip_quotes(t)
        if t == "--":
            i += 1
            continue
        if t in opts_with_arg:
            i += 2
            continue
        if t.startswith("-") and "=" in t:
            i += 1
            continue
        if t.startswith("-"):
            # bareword flags like -r, -t, -0, -I{} (replace-str fused), -p
            # -I may fuse its replstr: -I{} ; treat as single token
            i += 1
            continue
        return (i, st)
    return (None, None)


_XARGS_REPLSTR_RE = re.compile(r"\{\}")


def _xargs_effective_command(rest: list):
    """Resolve the EFFECTIVE command an `xargs` segment runs.

    Returns (head_basename|None, args_after_head, uses_placeholder, det) where:
      • head_basename is the real command after unwrapping wrapper prefixes
        (sudo/env/nice/…) on the xargs TARGET (so `xargs sudo kill` → 'kill',
        `xargs env node <path>` → 'node');
      • args_after_head EXCLUDES the head;
      • uses_placeholder is True when the target IS the `-I` replacement string
        (e.g. `xargs -I{} {}`) — the command then comes entirely from upstream
        stdin content, so callers must scan the upstream pipeline text.
    """
    xidx, xtgt = _xargs_target(rest)
    if xtgt is None:
        return (None, [], False, True)
    # `-I{}` replacement placeholder used as the command word.
    if _XARGS_REPLSTR_RE.fullmatch(xtgt) or xtgt in ("{}",):
        return (None, [], True, True)
    target_tokens = rest[xidx:]
    cw = _command_words(target_tokens)
    if not cw:
        return (os.path.basename(_strip_quotes(xtgt)), [], False, True)
    _, head, args = cw[0]
    return (head, args, False, True)


# Package-runner options that consume one following operand (so the runner's
# target command is not mistaken for the operand).
_RUNNER_OPTS_WITH_ARG = frozenset({
    "-p", "--package", "-c", "--call", "--node-options", "--node-arg",
})


def _package_runner_invocation(head: str, rest: list):
    """Resolve a package-runner exec/dlx form to (target_basename, args_after).

    Handles npx/bunx and `npm exec`/`pnpm exec|dlx`/`yarn exec|dlx`/`bun x`.
    Consumes runner options that take an operand (e.g. `--package <pkg>`) and the
    `--` terminator, so `npx --package typescript tsc -p x` resolves target=tsc
    (not 'typescript'). Returns (None, []) if not a runner form / no target.
    """
    toks = None
    if head in ("npx", "bunx"):
        toks = rest
    elif head in PKG_MANAGERS:
        i = 0
        while i < len(rest):
            t = rest[i]
            if t in ("exec", "dlx", "x"):
                toks = rest[i + 1:]
                break
            if t in ("run", "run-script"):
                return (None, [])
            i += 1
    if toks is None:
        return (None, [])
    i = 0
    n = len(toks)
    while i < n:
        t = toks[i]
        if t == "--":
            i += 1
            continue
        # PM selector / cwd flags AFTER exec (`npm exec -w cli -- node …`) take a
        # value and are NOT the runner target — consume the flag and its operand.
        if t in ("-w", "--workspace", "--filter", "-F", "--prefix", "-C", "--dir", "--cwd") and i + 1 < n:
            i += 2
            continue
        if any(t.startswith(f + "=") for f in ("--workspace", "--filter", "-F", "--prefix", "-C", "--dir", "--cwd", "-w")):
            i += 1
            continue
        if t in _RUNNER_OPTS_WITH_ARG:
            i += 2
            continue
        if t.startswith("-"):
            i += 1
            continue
        return (os.path.basename(_strip_quotes(t)), toks[i + 1:])
    return (None, [])


def _package_runner_target(head: str, rest: list) -> Optional[str]:
    """Return the first real command after a package-runner keyword, else None."""
    tgt, _args = _package_runner_invocation(head, rest)
    return tgt


# ── P2 SERVICE_GUARD ─────────────────────────────────────────────────────────

def _p2_service(simple_cmds: list, cfg: dict) -> Optional[Verdict]:
    services = cfg.get("protected_services", [])
    if not services:
        return None
    # match `unit`, `unit.service`, and the template-instance form
    # `unit@instance` / `unit@instance.service` (without matching a longer
    # hyphenated unrelated unit name — the boundary after the instance enforces).
    svc_re = [re.compile(r"(^|[\s=])" + re.escape(s) + r"(@[^\s.=/]*)?(\.service)?(\s|$|\.|=)") for s in services]
    for sc in simple_cmds:
        tokens = _safe_shlex(sc)
        if not tokens:
            continue
        cw = _command_words(tokens)
        if not cw:
            continue
        _, head, rest = cw[0]
        if head not in ("systemctl", "service", "initctl"):
            continue
        if not (any(v in rest for v in SERVICE_VERBS)):
            continue
        joined = " " + " ".join(_strip_quotes(t) for t in rest) + " "
        for rx in svc_re:
            if rx.search(joined):
                return _block("P2", "service-control of a protected unit")
    return None


# ── P3 / P4 mutation guards ──────────────────────────────────────────────────

def _mutation_targets(simple_cmd: str, tokens: list) -> list:
    """Return candidate mutation TARGET paths in a simple command."""
    targets = []
    rt = _has_redirect_to(simple_cmd)
    if rt:
        targets.append(rt)
    if not tokens:
        return targets
    cw = _command_words(tokens)
    if not cw:
        return targets
    _, head, rest = cw[0]
    args = list(rest)
    if head in ("cp", "mv", "rsync", "install"):
        # last bareword non-flag is destination
        barewords = [t for t in args if not t.startswith("-")]
        if barewords:
            targets.append(barewords[-1])
    elif head in ("touch", "truncate", "dd", "tee", "unzip", "rename",
                  "rm", "unlink", "shred"):
        targets.extend([t for t in args if not t.startswith("-")])
    elif head in ("sed", "perl") and ("-i" in args or any(a.startswith("-i") for a in args)):
        targets.extend([t for t in args if not t.startswith("-")])
    elif head == "ln":
        barewords = [t for t in args if not t.startswith("-")]
        if barewords:
            targets.append(barewords[-1])
    elif head in ("tar",):
        if any(a.startswith("-x") or a == "--extract" or ("x" in a and a.startswith("-")) for a in args):
            barewords = [t for t in args if not t.startswith("-")]
            targets.extend(barewords)
    return targets


def _mutation_target_hits(simple_cmds: list, idx: int, sc: str, tokens: list,
                          globs: list, cwd_base: Optional[str]) -> bool:
    """True if any mutation target of `sc` matches a protected glob, resolving a
    relative target against the effective cwd (cd chain + wrapper chdir) so
    `cd <protected> && touch dist/index.mjs` and `rm <rel>/dist/index.mjs` hit."""
    cwd, cwd_det = _effective_cwd_after(simple_cmds, idx, cwd_base)
    cwd, cwd_det = _fold_wrapper_cwd(cwd, cwd_det, tokens)
    for tgt in _mutation_targets(sc, tokens):
        for cand in _resolve_rel(tgt, cwd, cwd_det):
            if _path_matches_any(cand, globs):
                return True
    return False


def _p3_hotfile(simple_cmds: list, cfg: dict, cwd_base: Optional[str] = None) -> Optional[Verdict]:
    hot = cfg.get("protected_hotfiles", [])
    if not hot:
        return None
    for idx, sc in enumerate(simple_cmds):
        tokens = _safe_shlex(sc)
        if _mutation_target_hits(simple_cmds, idx, sc, tokens, hot, cwd_base):
            return _block("P3", "mutation of protected hot-watched bundle")
    return None


def _p4_statefile(simple_cmds: list, cfg: dict, cwd_base: Optional[str] = None) -> Optional[Verdict]:
    state = cfg.get("protected_statefiles", [])
    if not state:
        return None
    for idx, sc in enumerate(simple_cmds):
        tokens = _safe_shlex(sc)
        if _mutation_target_hits(simple_cmds, idx, sc, tokens, state, cwd_base):
            return _block("P4", "mutation of protected state file")
    return None


# ── P5 ENDPOINT_GUARD ────────────────────────────────────────────────────────

LOOPBACK_RE = re.compile(r"(127\.0\.0\.1|localhost|\[::1\]|::1)", re.IGNORECASE)
# Raw byte-stream clients: the request line (incl. the control path) is supplied
# on STDIN, so the path legitimately arrives from an UPSTREAM pipeline segment.
RAW_SOCKET_HEADS = frozenset({"nc", "ncat", "netcat", "socat", "telnet"})
# Structured HTTP clients: the request path is part of the client's OWN argv (a
# URL or a stdin-body flag), NOT merely co-present somewhere in the pipeline.
HTTP_CLIENT_HEADS = frozenset({"curl", "wget", "http", "https", "httpie"})
NET_HEADS = RAW_SOCKET_HEADS | HTTP_CLIENT_HEADS


def _endpoint_path_in(text: str, paths: list) -> bool:
    for ep in paths:
        if re.search(re.escape(ep) + r"(\b|/|\"|'|\s|$)", text):
            return True
    return False


def _http_reads_stdin_body(sc: str) -> bool:
    """True if an HTTP client is told to read its request body from stdin, so a
    control path piped in upstream would actually be sent."""
    return bool(re.search(r"(--data-binary|--data|-d)\s+@-|--data-binary\s+@/dev/stdin", sc))


def _p5_endpoint(groups: list, cfg: dict) -> Optional[Verdict]:
    """Pipeline-group + segment-ORDER aware control-endpoint guard.

    A loopback control shutdown can be split across pipeline segments — the
    control path travels in one segment's content (e.g. `printf 'POST /stop'`)
    and a raw byte-stream client (nc/ncat/netcat/socat/telnet) in a connected
    DOWNSTREAM segment (`| nc 127.0.0.1 <port>`) sends it via stdin. BLOCK when,
    within ONE pipeline group:
      • a RAW socket client to a loopback host has the protected endpoint path
        in ITS OWN segment OR in an UPSTREAM segment (stdin source), OR
      • an HTTP client to a loopback host carries the protected endpoint path in
        its OWN argv, OR is told to read its body from stdin while the path is
        present upstream.
    This is order-aware so a benign `curl …/health | grep /stop` (endpoint text
    only DOWNSTREAM, never sent) and `grep /stop file | curl …/health` (endpoint
    text in an unrelated upstream filter, HTTP client argv clean) stay ALLOWED.
    """
    paths = cfg.get("protected_endpoint_paths", [])
    if not paths:
        return None
    for group in groups:
        if not _endpoint_path_in(" ".join(group), paths):
            continue
        for k, sc in enumerate(group):
            tokens = _safe_shlex(sc)
            if not tokens:
                continue
            cw = _command_words(tokens)
            if not cw:
                continue
            _, head, _rest = cw[0]
            if head not in NET_HEADS or not LOOPBACK_RE.search(sc):
                continue
            upstream_text = " ".join(group[:k])
            own_has_ep = _endpoint_path_in(sc, paths)
            upstream_has_ep = _endpoint_path_in(upstream_text, paths)
            if head in RAW_SOCKET_HEADS:
                # stdin-fed: endpoint in this segment or any upstream segment
                if own_has_ep or upstream_has_ep:
                    return _block("P5", "loopback request to a protected control path")
            else:  # HTTP client
                if own_has_ep:
                    return _block("P5", "loopback request to a protected control path")
                if upstream_has_ep and _http_reads_stdin_body(sc):
                    return _block("P5", "loopback request to a protected control path (stdin body)")
    return None


# ── P6 PROCKILL_GUARD ────────────────────────────────────────────────────────

def _is_kill_executor(head: str, rest: list) -> bool:
    """True if this simple command terminates processes."""
    if head in KILL_VERBS:
        return True
    # `xargs [opts] [wrapper] kill|pkill|killall ...` — unwrap wrappers on the
    # xargs target so `xargs sudo kill` / `xargs env kill` resolve to 'kill'.
    if head == "xargs":
        xbase, _xa, uses_ph, _det = _xargs_effective_command(rest)
        if xbase is not None and xbase in KILL_VERBS:
            return True
        # `xargs -I{} kill {}` style placeholder kill — the literal kill verb is
        # in the args even when the target parse lands on the placeholder.
        if uses_ph and any(os.path.basename(_strip_quotes(t)) in KILL_VERBS for t in rest):
            return True
    # `fuser -k`
    if head == "fuser" and ("-k" in rest or any(t.startswith("-") and "k" in t for t in rest)):
        return True
    return False


def _p6_prockill(groups: list, cfg: dict) -> Optional[Verdict]:
    """Pipeline-group + command-substitution aware process-kill guard.

    The canonical daemon-kill idioms split the protected identifier and the kill
    executor across pipeline segments or a command substitution:
      ps aux | grep <ident> | awk '{print $2}' | xargs kill
      pgrep -f <ident> | xargs pkill
      kill $(ps aux | grep <ident> | awk '{print $2}')
    BLOCK when, within ONE pipeline group, a kill executor is present AND a
    protected identifier appears anywhere connected to it — in any segment of
    the same group, or inside a kill's $()/`` command substitution.
    """
    idents = cfg.get("protected_proc_idents", [])
    statefiles = cfg.get("protected_statefiles", [])
    if not idents and not statefiles:
        return None

    def has_ident(text: str) -> bool:
        return any(ident in text for ident in idents)

    def reads_statefile(text: str) -> bool:
        """True if any whitespace token of `text` resolves to a protected
        statefile path. A kill target derived from `$(jq .pid <statefile>)` is a
        protected-PID kill even though the statefile path is not a proc-ident."""
        if not statefiles:
            return False
        for raw in re.split(r"\s+", text):
            st = _strip_quotes(raw.strip("'\""))
            # strip a leading input-redirection prefix (`<path`, `0<path`, `<<<`)
            # so `jq .pid <PROTECTED_STATEFILE` (fused redirect) is recognized.
            st = re.sub(r"^\d*<+", "", st)
            if not st or st.startswith("-"):
                continue
            if _path_matches_any(st, statefiles):
                return True
        return False

    for group in groups:
        kill_present = False
        kill_subst_carries_ident = False
        for sc in group:
            tokens = _safe_shlex(sc)
            if not tokens:
                continue
            cw = _command_words(tokens)
            if not cw:
                continue
            _, head, rest = cw[0]
            if _is_kill_executor(head, rest):
                kill_present = True
                # `kill $(<pipeline naming ident>)` / `kill $(jq .pid
                # <statefile>)` — inspect this command's substitutions for a
                # protected identifier OR a read of a protected statefile.
                for sub in _command_substitutions(sc):
                    if has_ident(sub) or reads_statefile(sub):
                        kill_subst_carries_ident = True
        if not kill_present:
            continue
        group_text = " ".join(group)
        if has_ident(group_text) or kill_subst_carries_ident or reads_statefile(group_text):
            return _block("P6", "process kill carrying a protected identifier")
    return None


# ── P7 GLOBALBIN_GUARD ───────────────────────────────────────────────────────

def _p7_globalbin(simple_cmds: list, cfg: dict) -> Optional[Verdict]:
    gbins = cfg.get("protected_global_bins", [])
    for sc in simple_cmds:
        tokens = _safe_shlex(sc)
        if not tokens:
            continue
        cw = _command_words(tokens)
        if not cw:
            continue
        _, head, rest = cw[0]
        if head in PKG_MANAGERS:
            is_global = any(t in ("-g", "--global") for t in rest)
            is_link = any(t in ("link", "unlink") for t in rest)
            if is_global or is_link:
                return _block("P7", "global package install/link")
        # writes to protected global bin paths (any mutation head)
        for tgt in _mutation_targets(sc, tokens):
            if gbins and _path_matches_any(tgt, gbins):
                return _block("P7", "write to a protected global bin path")
    return None


# ── P8 BUILD_GUARD ───────────────────────────────────────────────────────────

def _cwd_under_build_path(cwd: Optional[str], cwd_det: bool, bpaths: list) -> bool:
    """True if a determinate effective cwd resolves under a protected build dir."""
    if not cwd or not cwd_det:
        return False
    return _path_under_any(cwd, bpaths)


def _cwd_in_protected_build_scope(cwd: Optional[str], cwd_det: bool, cfg: dict) -> bool:
    """True if a determinate effective cwd is inside a protected build package OR
    at/under a protected monorepo root manifest. A bare build-mode invocation
    (tsc -b) in either scope rebuilds the protected bundle (directly or via
    project references), so it is in-scope for the build guard."""
    if not cwd or not cwd_det:
        return False
    if _path_under_any(cwd, cfg.get("protected_build_paths", [])):
        return True
    # the monorepo ROOT exactly (where a project-referenced `tsc -b` rebuilds the
    # protected package); a non-protected sub-package's own cwd is NOT in scope.
    cwd_n = os.path.normpath(cwd)
    for root in cfg.get("protected_root_manifest_paths", []):
        if cwd_n == os.path.normpath(root):
            return True
    return False


def _p8_build(simple_cmds: list, cfg: dict, cwd_base: Optional[str] = None) -> Optional[Verdict]:
    ws = set(cfg.get("protected_build_workspaces", []))
    bpaths = cfg.get("protected_build_paths", [])
    for idx, sc in enumerate(simple_cmds):
        tokens = _safe_shlex(sc)
        if not tokens:
            continue
        cw = _command_words(tokens)
        if not cw:
            continue
        _, head, rest = cw[0]
        # effective cwd: cd/pushd in the chain + a leading wrapper chdir + a PM
        # workspace selector's resolved dir (so `npm -w <ws> exec tsc -p
        # tsconfig.json` resolves the protected build cwd).
        cwd, cwd_det = _effective_cwd_after(simple_cmds, idx, cwd_base)
        cwd, cwd_det = _fold_wrapper_cwd(cwd, cwd_det, tokens)
        cwd, cwd_det = _selector_cwd(head, rest, cfg, cwd, cwd_det)
        cwd_in_build = _cwd_under_build_path(cwd, cwd_det, bpaths)
        # (a) explicit: build naming a protected workspace
        if head in PKG_MANAGERS and "build" in rest:
            sel = _explicit_workspace_selector(head, rest)
            if sel is not None and sel in ws:
                return _block("P8", "explicit build of a protected workspace")
        # (a) build tool co-occurring with a protected build path (token, fused
        # --flag=path value, or cwd) — relative paths resolved against cwd.
        if head in BUILD_TOOL_BASENAMES:
            if _any_token_under_incl_flagvalue(rest, cfg, cwd, cwd_det) or cwd_in_build:
                return _block("P8", "build tool co-occurring with a protected build path")
            if (_build_mode_flag_present(rest)
                    and not _explicit_nonprotected_build_target(rest, cfg, cwd, cwd_det)
                    and (cwd is None or not cwd_det
                         or _cwd_in_protected_build_scope(cwd, cwd_det, cfg))):
                # bare build-mode (tsc -b / --build / -w) with cwd in a protected
                # package/root or indeterminate cwd -> fail-closed rebuild, UNLESS
                # an explicit project target proves a non-protected build.
                return _block("P8", "build-mode flag with protected/indeterminate cwd")
        if head in PKG_MANAGERS and "build" in rest:
            if _any_token_under_incl_flagvalue(_strip_selector_tokens(rest), cfg, cwd, cwd_det):
                return _block("P8", "build co-occurring with a protected build path")
        # package-runner build: npx/bunx AND npm exec/pnpm exec/yarn exec/bun x
        # running a build tool, against a protected build path (token or cwd).
        rtgt = _package_runner_target(head, rest)
        if rtgt is not None and os.path.basename(rtgt) in BUILD_TOOL_BASENAMES:
            # tokens AFTER the build-tool target (e.g. `-p <path>` for tsc)
            after = _tokens_after_runner_target(head, rest)
            if (_any_token_under_incl_flagvalue(after, cfg, cwd, cwd_det)
                    or _any_token_under_incl_flagvalue(rest, cfg, cwd, cwd_det) or cwd_in_build):
                return _block("P8", "package-runner build co-occurring with a protected build path")
            if (_build_mode_flag_present(after)
                    and not _explicit_nonprotected_build_target(after, cfg, cwd, cwd_det)
                    and (cwd is None or not cwd_det
                         or _cwd_in_protected_build_scope(cwd, cwd_det, cfg))):
                return _block("P8", "package-runner build-mode flag with protected/indeterminate cwd")
    return None


# Build-mode flags that produce/refresh the bundle without an explicit path
# argument (incremental project build / watch). When present, the effective cwd
# decides whether the protected bundle is the target.
_BUILD_MODE_FLAGS = frozenset({"-b", "--build", "-w", "--watch"})


def _build_mode_flag_present(tokens: list) -> bool:
    for t in tokens:
        st = _strip_quotes(t)
        if st in _BUILD_MODE_FLAGS:
            return True
    return False


def _strip_selector_tokens(rest: list) -> list:
    """Drop workspace/filter/cwd SELECTOR flags and their values from a PM arg
    list, so a selector value (`--filter ./packages/<pkg>`) is not mis-scanned as
    a build-path target (the selector dir is folded into the effective cwd
    separately)."""
    out = []
    i = 0
    sel_flags = ("-w", "--workspace", "--filter", "-F", "--prefix", "-C", "--dir", "--cwd")
    while i < len(rest):
        t = rest[i]
        if t in ("workspace", "workspaces") and i + 1 < len(rest):
            i += 2
            continue
        if t in sel_flags and i + 1 < len(rest):
            i += 2
            continue
        if any(t.startswith(f + "=") for f in sel_flags):
            i += 1
            continue
        out.append(t)
        i += 1
    return out


def _p8_explicit_protected_path(simple_cmds: list, cfg: dict, cwd_base: Optional[str] = None) -> Optional[Verdict]:
    """The explicit-path subset of P8: BLOCK only when a build invocation's path
    token or path-valued flag RHS resolves DETERMINATELY under a protected build
    path. No bare-verb / cwd fallback (so this can run after a P9 ALLOW without
    re-introducing over-blocks)."""
    bpaths = cfg.get("protected_build_paths", [])
    if not bpaths:
        return None
    for idx, sc in enumerate(simple_cmds):
        tokens = _safe_shlex(sc)
        if not tokens:
            continue
        cw = _command_words(tokens)
        if not cw:
            continue
        _, head, rest = cw[0]
        cwd, cwd_det = _effective_cwd_after(simple_cmds, idx, cwd_base)
        cwd, cwd_det = _fold_wrapper_cwd(cwd, cwd_det, tokens)
        cwd, cwd_det = _selector_cwd(head, rest, cfg, cwd, cwd_det)
        is_build = (head in BUILD_TOOL_BASENAMES
                    or (head in PKG_MANAGERS and "build" in rest)
                    or (_package_runner_target(head, rest) is not None
                        and os.path.basename(_package_runner_target(head, rest) or "") in BUILD_TOOL_BASENAMES)
                    or "build" in [_strip_quotes(t) for t in rest])
        if not is_build:
            continue
        if _any_token_under_incl_flagvalue(_strip_selector_tokens(rest), cfg, cwd, cwd_det):
            return _block("P8", "explicit protected build-path argument")
    return None


def _tokens_after_runner_target(head: str, rest: list) -> list:
    """Tokens following the package-runner's target command word (e.g. after
    `tsc` in `pnpm exec tsc -p <path>`)."""
    if head in ("npx", "bunx"):
        toks = rest
    elif head in PKG_MANAGERS:
        toks = None
        for i, t in enumerate(rest):
            if t in ("exec", "dlx", "x"):
                toks = rest[i + 1:]
                break
        if toks is None:
            return []
    else:
        return []
    # skip flags before the target command word, then return everything after it
    i = 0
    while i < len(toks):
        st = _strip_quotes(toks[i])
        if st.startswith("-") or st == "--":
            i += 1
            continue
        return toks[i + 1:]
    return []


def _p8_bare_build(simple_cmds: list, cfg: dict) -> Optional[Verdict]:
    """Bare-build arm — only reached when P9 has not already DENIED/ALLOWED.
    Kept separate so P9's allow-set (explicit non-protected workspace) wins first.
    """
    bare = bool(cfg.get("bare_build_guard", False))
    if not bare:
        return None
    for sc in simple_cmds:
        tokens = _safe_shlex(sc)
        if not tokens:
            continue
        cw = _command_words(tokens)
        if not cw:
            continue
        _, head, rest = cw[0]
        if head in BUILD_TOOL_BASENAMES and not any(t.startswith("-") and t not in ("-p",) for t in rest):
            # bare pkgroll/tsup/tsc with no explicit non-protected path
            return _block("P8b", "bare build tool")
    return None


# Sentinel prefix marking a selector that is a DETERMINATE filesystem PATH
# filter (`--filter ./packages/x`), resolved to a manifest dir at use sites.
_PATH_FILTER_PREFIX = "<PATH>"


def _classify_filter_value(val: str) -> str:
    """Classify a pnpm/yarn `--filter` value.

    • A genuine glob / ellipsis / brace selector (`*`, `?`, `{`, `...`, trailing
      `^`/`~` dependency selectors) fans out → `<MULTI>` (fail-closed).
    • A deterministic filesystem PATH filter (`./packages/x`, `packages/x`, `.`)
      → `<PATH>./packages/x` so the use site resolves it to a manifest dir.
    • A bare package-NAME filter (`some-pkg`) → returned as-is for name
      resolution.
    """
    if any(ch in val for ch in ("*", "?", "{", "}")) or val.startswith("...") or val.endswith("...") or "..." in val:
        return "<MULTI>"
    # a scoped package NAME (`@scope/name`) contains a slash but is a name, not a
    # filesystem path — classify it as a name selector (resolved via metadata).
    if val.startswith("@") and val.count("/") == 1 and not val.startswith("@/"):
        return val
    # path-like: contains a slash, or is '.'/'..', or starts with './' or '../'
    if "/" in val or val in (".", ".."):
        return _PATH_FILTER_PREFIX + val
    # otherwise a package name (or name with a leading scope '@org/...' which
    # contains '/' and is handled above). A trailing dependency selector ('^'/'~')
    # is a fan-out -> MULTI.
    if val.endswith("^") or val.endswith("~") or val.startswith("^") or val.startswith("~"):
        return "<MULTI>"
    return val


def _explicit_workspace_selector(pm_head: str, rest: list) -> Optional[str]:
    """Return the workspace SELECTOR token if an explicit selector is present.
    Returns None if no explicit single-workspace selector. Returns a sentinel
    '<MULTI>' for recursive/all-workspace forms, or '<PATH>...' for a
    deterministic path filter.
    """
    i = 0
    while i < len(rest):
        t = rest[i]
        if t == "workspace" and i + 1 < len(rest):
            return _strip_quotes(rest[i + 1])
        if t == "workspaces":
            return "<MULTI>"
        if t in ("-w", "--workspace") and i + 1 < len(rest):
            return _strip_quotes(rest[i + 1])
        if t.startswith("--workspace="):
            return _strip_quotes(t.split("=", 1)[1])
        if t in ("--filter", "-F") and i + 1 < len(rest):
            return _classify_filter_value(_strip_quotes(rest[i + 1]))
        if t.startswith("--filter=") or t.startswith("-F="):
            return _classify_filter_value(_strip_quotes(t.split("=", 1)[1]))
        if t in ("--workspaces", "-ws"):
            return "<MULTI>"
        if t in ("-r", "--recursive"):
            return "<MULTI>"
        i += 1
    return None


# ── P9 PKGSCRIPT_GUARD (default-deny) ────────────────────────────────────────

def _resolve_path_filter_manifest(path_val: str, cfg: dict, effective_cwd: Optional[str]):
    """Resolve a `<PATH>` filter value (a directory) to (manifest_dir,
    is_protected, scripts_set, determinate). The directory is resolved against
    the known monorepo roots and the effective cwd, then its package.json is
    read. A protected dir (or one with no resolvable manifest) fails closed."""
    if any(ch in path_val for ch in ("$", "`")):
        return (None, None, None, False)
    # Resolve a relative path filter against the INVOKING cwd FIRST (so `/other`
    # running `--filter ./packages/<pkg>` resolves to /other/..., not a protected
    # root). Fall back to the protected roots only when there is no cwd.
    candidate_bases = []
    if effective_cwd:
        candidate_bases.append(effective_cwd)
    candidate_bases.extend(cfg.get("protected_root_manifest_paths", []))
    tried = []
    if os.path.isabs(path_val):
        tried.append(os.path.normpath(path_val))
    else:
        for base in candidate_bases:
            tried.append(os.path.normpath(os.path.join(base, path_val)))
    for d in tried:
        man = os.path.join(d, "package.json")
        is_protected = (
            _dir_is_protected_pkg(d, cfg)
            or os.path.normpath(d) in [os.path.normpath(p) for p in cfg.get("protected_root_manifest_paths", [])]
        )
        if os.path.isfile(man):
            try:
                with open(man, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
            except (OSError, ValueError):
                data = {}
            name = data.get("name")
            if name is not None:
                is_protected = is_protected or name in set(cfg.get("protected_script_workspaces", []))
            scripts = set((data.get("scripts") or {}).keys())
            return (d, is_protected, scripts, True)
        if is_protected:
            # protected dir even if manifest unreadable -> deny determinately
            return (d, True, set(), True)
    return (None, None, None, False)


def _resolve_workspace_manifest(selector: str, cfg: dict, effective_cwd: Optional[str]):
    """Resolve a workspace selector to (manifest_dir, is_protected, scripts_set,
    determinate). Uses workspace metadata by reading package.json files under the
    known monorepo roots. Returns (None, None, None, False) if unresolvable.
    """
    if selector.startswith(_PATH_FILTER_PREFIX):
        return _resolve_path_filter_manifest(selector[len(_PATH_FILTER_PREFIX):], cfg, effective_cwd)
    roots = cfg.get("protected_root_manifest_paths", [])
    search_roots = list(roots)
    if effective_cwd:
        search_roots.append(effective_cwd)
    seen = set()
    for root in search_roots:
        try:
            pkgs_dir = os.path.join(root, "packages")
            if not os.path.isdir(pkgs_dir):
                continue
            for entry in os.listdir(pkgs_dir):
                man = os.path.join(pkgs_dir, entry, "package.json")
                if man in seen:
                    continue
                seen.add(man)
                try:
                    with open(man, "r", encoding="utf-8") as fh:
                        data = json.load(fh)
                except (OSError, ValueError):
                    continue
                name = data.get("name")
                if name == selector:
                    is_protected = (
                        name in set(cfg.get("protected_script_workspaces", []))
                        or _dir_is_protected_pkg(os.path.dirname(man), cfg)
                    )
                    scripts = set((data.get("scripts") or {}).keys())
                    return (os.path.dirname(man), is_protected, scripts, True)
        except OSError:
            continue
    # selector did not resolve to any known workspace -> indeterminate
    return (None, None, None, False)


def _effective_manifest_for_cwd(cwd: Optional[str], cfg: dict):
    """Walk up from cwd to find the nearest package.json. Returns
    (manifest_dir, is_protected_or_root, scripts_set, determinate)."""
    if not cwd:
        return (None, None, None, False)
    proots = [os.path.normpath(p) for p in cfg.get("protected_root_manifest_paths", [])]
    spaths = cfg.get("protected_script_paths", [])
    d = os.path.normpath(cwd)
    while True:
        man = os.path.join(d, "package.json")
        scripts = None
        exists = os.path.isfile(man)
        if exists:
            try:
                with open(man, "r", encoding="utf-8") as fh:
                    scripts = set((json.load(fh).get("scripts") or {}).keys())
            except (OSError, ValueError):
                scripts = set()
        is_protected_root = d in proots
        is_protected_path = _dir_is_protected_pkg(d, cfg)
        if exists or is_protected_root:
            return (d, (is_protected_root or is_protected_path), scripts or set(), True)
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return (None, None, None, False)


def _p9_pkgscript(simple_cmds: list, cfg: dict, cwd_base: Optional[str] = None) -> Optional[Verdict]:
    if cfg.get("script_run_policy") != "default_deny":
        return None
    non_protected = set(cfg.get("non_protected_workspaces", []))
    safe_allow = set(cfg.get("safe_script_allowlist", []))
    protected_cmds = set(cfg.get("protected_cmds", []))

    for idx, sc in enumerate(simple_cmds):
        tokens = _safe_shlex(sc)
        if not tokens:
            continue
        cw = _command_words(tokens)
        if not cw:
            continue
        _, head, rest = cw[0]
        if head not in PKG_MANAGERS:
            continue
        # (A) head-level meta query -> allow this invocation
        if _is_meta_query(head, rest):
            continue
        # exec/dlx/runner forms -> P1 owns them (resolve protected basename)
        runner_target = _package_runner_target(head, rest)
        if runner_target is not None:
            if runner_target in protected_cmds:
                return _block("P9", "package-runner reaching a protected command")
            # non-protected exec target: not a script-run; allow
            continue
        # A runner keyword (exec/dlx/x) with NO resolvable target (e.g. only a
        # `-c <payload>` form, or selector+exec already handled by P1) is a
        # runner form, NOT a bare script-run — P9 abstains so it is not
        # mis-classified as a protected-cwd script (the `-c` payload is
        # recursively evaluated separately).
        if _first_subcommand(head, rest) in ("exec", "dlx", "x"):
            continue

        # compute effective cwd from cd/pushd in the chain, then fold a leading
        # wrapper chdir (env -C/sudo --chdir) so it participates in manifest
        # resolution like cd/--cwd (else legitimate `env -C <non-protected-ws>
        # yarn <script>` would over-block), then apply pm --cwd flags.
        cwd, cwd_det = _effective_cwd_after(simple_cmds, idx, cwd_base)
        cwd, cwd_det = _fold_wrapper_cwd(cwd, cwd_det, tokens)
        pm_cwd, pm_cwd_det = _pm_cwd_flag(head, rest)
        if pm_cwd is not None:
            if pm_cwd_det:
                if os.path.isabs(pm_cwd):
                    cwd = os.path.normpath(pm_cwd)
                else:
                    cwd = os.path.normpath(os.path.join(cwd, pm_cwd)) if cwd else os.path.normpath(pm_cwd)
            else:
                cwd_det = False

        selector = _explicit_workspace_selector(head, rest)

        # (D) explicit selector present
        if selector is not None:
            if selector == "<MULTI>":
                return _block("P9", "recursive/all-workspace run (no single selector)")
            man_dir, is_protected, scripts, det = _resolve_workspace_manifest(selector, cfg, cwd)
            if not det:
                # selector did not resolve -> fail closed
                return _block("P9", "unresolvable workspace selector")
            if is_protected:
                return _block("P9", "run naming a protected workspace")
            # non-protected workspace: classify the post-selector subcommand
            post = _post_selector_tokens(head, rest)
            verdict = _classify_post_selector(post, scripts, safe_allow, protected_cmds,
                                              _under_protected_monorepo(man_dir, cfg))
            if verdict is not None:
                return verdict
            # allowed
            continue

        # (B)/(E) no explicit selector. Dependency built-in?
        sub = _first_subcommand(head, rest)
        if sub in DEP_BUILTINS:
            # dependency op: allowed unless effective manifest is protected w/o --ignore-scripts
            man_dir, is_protected, scripts, det = _effective_manifest_for_cwd(cwd, cfg)
            if not det:
                # default (repo) cwd unknown — dependency ops at unknown cwd are allowed
                # (they manage node_modules; build/dist rewrite owned by P8, global by P7)
                continue
            if is_protected and "--ignore-scripts" not in rest:
                return _block("P9", "dependency op in a protected manifest without --ignore-scripts")
            continue
        # npm lifecycle shorthand: npm start/stop/restart/test
        if head == "npm" and sub in DEP_SHORTHAND_NPM:
            return _resolve_bare_script(sub, cwd, cwd_det, cfg, safe_allow, protected_cmds)
        # explicit run / run-script keyword
        script_tok = None
        if sub in ("run", "run-script"):
            script_tok = _token_after(rest, sub)
        elif sub is not None and sub not in DEP_BUILTINS and not sub.startswith("-"):
            # bare form: `yarn <script>` / `pnpm <script>` / `bun <script>`
            script_tok = sub
        if script_tok is None:
            # `yarn` alone with no script -> runs default? treat as bare script-run -> fail closed if protected cwd
            return _resolve_bare_script(None, cwd, cwd_det, cfg, safe_allow, protected_cmds)
        return _resolve_bare_script(script_tok, cwd, cwd_det, cfg, safe_allow, protected_cmds)
    return None


def _pm_cwd_flag(head: str, rest: list):
    """Extract a PM cwd flag value. Returns (path|None, determinate)."""
    flags_one = {
        "yarn": ("--cwd",),
        "npm": ("--prefix", "-C"),
        "bun": ("--cwd",),
        "pnpm": ("-C", "--dir"),
    }.get(head, ())
    i = 0
    while i < len(rest):
        t = rest[i]
        for f in flags_one:
            if t == f and i + 1 < len(rest):
                val = _strip_quotes(rest[i + 1])
                if any(ch in val for ch in ("$", "`", "*", "?")):
                    return (None, False)
                return (val, True)
            if t.startswith(f + "="):
                val = _strip_quotes(t.split("=", 1)[1])
                if any(ch in val for ch in ("$", "`", "*", "?")):
                    return (None, False)
                return (val, True)
        i += 1
    return (None, True)


_PM_FLAGS_WITH_VALUE = frozenset({
    "--prefix", "--cwd", "-C", "--dir", "-w", "--workspace", "--filter", "-F",
})


def _first_subcommand(head: str, rest: list) -> Optional[str]:
    i = 0
    n = len(rest)
    while i < n:
        t = rest[i]
        if t in _PM_FLAGS_WITH_VALUE:
            i += 2  # skip the flag and its value
            continue
        if t.startswith("-"):
            i += 1
            continue
        if re.match(r"^[A-Za-z_][A-Za-z0-9_.:-]*=", t):
            i += 1
            continue
        return _strip_quotes(t)
    return None


def _token_after(rest: list, keyword: str) -> Optional[str]:
    for i, t in enumerate(rest):
        if t == keyword:
            for j in range(i + 1, len(rest)):
                if not rest[j].startswith("-"):
                    return _strip_quotes(rest[j])
    return None


def _post_selector_tokens(head: str, rest: list) -> list:
    """Tokens following an explicit workspace/filter selector (its value consumed)."""
    i = 0
    out_start = None
    while i < len(rest):
        t = rest[i]
        if t == "workspace" and i + 1 < len(rest):
            out_start = i + 2
            break
        if t in ("-w", "--workspace", "--filter", "-F") and i + 1 < len(rest):
            out_start = i + 2
            break
        if t.startswith("--workspace=") or t.startswith("--filter=") or t.startswith("-F="):
            out_start = i + 1
            break
        i += 1
    if out_start is None:
        return []
    return rest[out_start:]


def _classify_post_selector(post: list, scripts: set, safe_allow: set, protected_cmds: set,
                            under_monorepo: bool = True) -> Optional[Verdict]:
    """Classify the post-selector subcommand on a NON-protected workspace.
    Returns a BLOCK verdict, or None to ALLOW.

    `under_monorepo` indicates the selected workspace lives inside the protected
    monorepo (where the protected CLI bin is hoisted and a `.bin` fallthrough is
    reachable). When False (an UNRELATED project's workspace) a non-declared
    token fallthrough cannot reach the protected daemon and is allowed.
    """
    # find first meaningful token
    first = None
    for t in post:
        if t.startswith("-"):
            continue
        first = _strip_quotes(t)
        break
    if first is None:
        return None  # nothing to run; allow (e.g. selector + flags only)
    # dependency built-in -> allowed (handled by dependency rule, non-protected ws)
    if first in DEP_BUILTINS:
        return None
    # runtime/exec/runner token -> route through P1 semantics -> DENY
    if first in EXEC_RUNNER_TOKENS:
        return _block("P9", "runtime/exec token after a workspace selector (P1)")
    # consume optional run/run-script keyword
    script_tok = first
    if first in ("run", "run-script"):
        script_tok = None
        for t in post:
            if t in ("run", "run-script"):
                continue
            if t.startswith("-"):
                continue
            script_tok = _strip_quotes(t)
            break
        if script_tok is None:
            return None
    # protected command basename -> DENY (.bin fallthrough)
    if script_tok in protected_cmds:
        return _block("P9", "protected command basename after a workspace selector")
    if script_tok in EXEC_RUNNER_TOKENS:
        return _block("P9", "runtime/exec token after a workspace selector (P1)")
    # declared-script-key gate: token MUST be a declared script of this workspace
    if script_tok in scripts:
        return None  # ALLOW
    if script_tok in safe_allow:
        return None
    # non-declared token: a yarn .bin fallthrough reaches the hoisted protected
    # CLI bin ONLY inside the protected monorepo -> deny there; an unrelated
    # project's tool fallthrough carries no daemon risk -> allow.
    if under_monorepo:
        return _block("P9", "token is not a declared script of the selected workspace (.bin fallthrough)")
    return None


def _dir_under_any_root(d: Optional[str], cfg: dict) -> bool:
    """True if directory `d` is at/under any protected monorepo root."""
    if not d:
        return False
    dn = os.path.normpath(d)
    for root in cfg.get("protected_root_manifest_paths", []):
        rn = os.path.normpath(root)
        if dn == rn or dn.startswith(rn + "/"):
            return True
    return False


def _dir_is_protected_pkg(d: Optional[str], cfg: dict) -> bool:
    """True if `d` is a protected package dir. A relative `protected_script_paths`
    glob (e.g. `**/packages/<pkg>`) is suffix-matching and would also match an
    UNRELATED project's identically-named dir; qualify it by requiring `d` to be
    under a protected monorepo root (an absolute glob is honored as-is)."""
    if not d:
        return False
    spaths = cfg.get("protected_script_paths", [])
    abs_globs = [g for g in spaths if g.startswith("/")]
    rel_globs = [g for g in spaths if not g.startswith("/")]
    if abs_globs and _path_matches_any(d, abs_globs):
        return True
    if rel_globs and _path_matches_any(d, rel_globs) and _dir_under_any_root(d, cfg):
        return True
    return False


def _under_protected_monorepo(man_dir: Optional[str], cfg: dict) -> bool:
    """True if `man_dir` is at/under a protected monorepo root (where the
    protected CLI bin is hoisted into node_modules/.bin and thus reachable as a
    `.bin` fallthrough). A manifest OUTSIDE every protected root belongs to an
    UNRELATED project — a non-declared-token fallthrough there cannot reach the
    protected daemon, so it must not be blocked."""
    if not man_dir:
        return False
    if _dir_under_any_root(man_dir, cfg):
        return True
    # also: a protected package dir reached via an ABSOLUTE glob (root-qualified
    # for relative globs to avoid matching an unrelated project's same-named dir)
    if _dir_is_protected_pkg(man_dir, cfg):
        return True
    return False


def _resolve_bare_script(script_tok: Optional[str], cwd: Optional[str], cwd_det: bool,
                         cfg: dict, safe_allow: set, protected_cmds: set) -> Verdict:
    """Resolve a bare (no-selector) script-run against the effective manifest."""
    if not cwd_det or cwd is None:
        # indeterminate cwd -> fail closed for the script-run family
        return _block("P9", "script-run with indeterminate cwd (fail-closed)")
    man_dir, is_protected, scripts, det = _effective_manifest_for_cwd(cwd, cfg)
    if not det:
        return _block("P9", "script-run with unresolvable effective manifest (fail-closed)")
    if is_protected:
        if script_tok is not None and script_tok in safe_allow:
            return ALLOW
        return _block("P9", "bare script-run reaching a protected workspace/root")
    # non-protected effective manifest: declared-script-key gate
    if script_tok is None:
        # bare PM run with no token in a manifest OUTSIDE the protected monorepo
        # is harmless (an unrelated project's default script); only fail-closed
        # inside the protected monorepo.
        if _under_protected_monorepo(man_dir, cfg):
            return _block("P9", "bare script-run with no script token (fail-closed)")
        return ALLOW
    if script_tok in protected_cmds:
        return _block("P9", "protected command basename in non-protected cwd (.bin fallthrough)")
    if script_tok in EXEC_RUNNER_TOKENS:
        return _block("P9", "runtime/exec token in non-protected cwd (P1)")
    if script_tok in scripts:
        return ALLOW
    if script_tok in safe_allow:
        return ALLOW
    # token is not a declared script of this manifest. Inside the protected
    # monorepo a yarn .bin fallthrough could reach the hoisted protected CLI bin
    # -> deny. In an UNRELATED project (outside every protected root) a tool
    # fallthrough carries no risk to the protected daemon -> allow.
    if _under_protected_monorepo(man_dir, cfg):
        return _block("P9", "token is not a declared script of the non-protected manifest (.bin fallthrough)")
    return ALLOW


# ── corepack re-routing ──────────────────────────────────────────────────────

def _runner_call_payloads(simple_cmds: list, cfg: Optional[dict] = None,
                          cwd_base: Optional[str] = None) -> list:
    """Return (payload, effective_cwd, cwd_det) tuples for any package-runner
    `-c`/`--call` form (`npx -c '<cmd>'`, `npm exec -c '<cmd>'`,
    `pnpm -w <ws> dlx --call '<cmd>'`).

    The payload string is itself a shell command the runner executes, so it is
    recursively evaluated under the SAME effective cwd (cd chain + wrapper chdir +
    PM workspace selector), so a relative daemon-launch / protected build inside
    the payload resolves. A benign payload re-evaluates to ALLOW.
    """
    payloads = []
    for idx, sc in enumerate(simple_cmds):
        toks = _safe_shlex(sc)
        if not toks:
            continue
        cw = _command_words(toks)
        if not cw:
            continue
        _, head, rest = cw[0]
        # locate the runner argv (after npx/bunx, or after exec/dlx/x for a PM)
        runner_args = None
        if head in ("npx", "bunx"):
            runner_args = rest
        elif head in PKG_MANAGERS:
            for i, t in enumerate(rest):
                if t in ("exec", "dlx", "x"):
                    runner_args = rest[i + 1:]
                    break
        if runner_args is None:
            continue
        # effective cwd for the payload: cd chain + wrapper chdir + selector
        cwd, cwd_det = _effective_cwd_after(simple_cmds, idx, cwd_base)
        cwd, cwd_det = _fold_wrapper_cwd(cwd, cwd_det, toks)
        if cfg is not None:
            cwd, cwd_det = _selector_cwd(head, rest, cfg, cwd, cwd_det)
        i = 0
        while i < len(runner_args):
            t = runner_args[i]
            if t in ("-c", "--call") and i + 1 < len(runner_args):
                payloads.append((_strip_quotes(runner_args[i + 1]), cwd, cwd_det))
                i += 2
                continue
            if t.startswith("--call="):
                payloads.append((_strip_quotes(t.split("=", 1)[1]), cwd, cwd_det))
                i += 1
                continue
            i += 1
    return payloads


# ── Generic exec-front-end recursion (wrapper-AGNOSTIC tail analysis) ────────

def _peel_exec_frontend(toks: list):
    """Given the tokens of ONE simple command, if its head (after VAR=val
    env-prefixes and any ENV_WRAPPERS folding) is a DOCUMENTED exec front-end,
    consume the front-end's own options/operands per its profile and return:

        (kind, value)

      kind == "tail"    -> value is the trailing argv list (the wrapped command
                           the front-end exec()s). Re-tokenized as a simple cmd.
      kind == "payload" -> value is a SHELL-STRING the front-end runs via a shell
                           (flock -c / su -c / runuser -c / watch joined-tail).
                           The caller recurses it through evaluate().
      None              -> head is not a documented front-end (leave unchanged).

    Pure parsing; no project names. An unknown head is never a front-end, so a
    benign command with a non-front-end head is untouched (no over-block).
    """
    # Locate the front-end head. A front-end may itself sit behind ENV_WRAPPERS
    # (`env flock …`, `sudo flock …`, `nohup flock …`) and/or VAR=val prefixes —
    # reuse _command_words, which already folds env-prefixes + ENV_WRAPPERS per
    # their own grammar, so the head it reports is the FIRST real command word.
    cw = _command_words(toks)
    if not cw:
        return None
    head_idx, head, _rest = cw[0]
    profile = EXEC_FRONTEND_PROFILES.get(head)
    if profile is None:
        return None
    # the ENV_WRAPPER prefix (everything before the front-end head) is preserved
    # on the rewritten tail so `env -C <dir> flock … node <rel>` keeps its chdir.
    prefix = toks[:head_idx]
    opts_with_arg = profile.get("opts_with_arg", frozenset())
    payload_opts = profile.get("payload_opts", frozenset())
    cwd_opts = profile.get("cwd_opts", frozenset())
    joins = profile.get("joins_tail_as_shell", False)
    args_marker = profile.get("args_marker")
    leading_pos = profile.get("leading_positionals", 0)
    consume_user = profile.get("consume_user_positional", False)
    # options that SUPPLY the user (so no leading user positional is expected).
    _USER_OPTS = frozenset({"-u", "--user"})
    n = len(toks)
    i = head_idx + 1  # consume the front-end head
    consumed_pos = 0
    user_consumed = False
    marker_seen = False
    cwd_dir = None        # chdir directory set by a cwd_opt
    cwd_dynamic = False   # cwd_opt value was dynamic ($/`/glob) -> fail closed
    while i < n:
        t = toks[i]
        if args_marker is not None and not marker_seen:
            # gdb-style: the tail begins ONLY after the explicit --args marker.
            if t == args_marker:
                marker_seen = True
                i += 1
                break
            if t in opts_with_arg and i + 1 < n:
                i += 2
                continue
            i += 1
            continue
        if t == "--":
            i += 1
            break
        # shell-string payload option (flock -c 'str', su -c 'str', --command=)
        if payload_opts:
            if t in payload_opts and i + 1 < n:
                return ("payload", _strip_quotes(toks[i + 1]), prefix, None, False)
            matched = False
            for po in payload_opts:
                if t.startswith(po + "="):
                    return ("payload", _strip_quotes(t.split("=", 1)[1]), prefix, None, False)
            del matched
        # cwd-changing option (unshare --wd, bwrap --chdir, proot -w): capture
        # the directory so the wrapped relative tail resolves against it.
        if cwd_opts:
            if t in cwd_opts and i + 1 < n:
                val = _strip_quotes(toks[i + 1])
                if any(ch in val for ch in ("$", "`", "*", "?")):
                    cwd_dynamic = True
                else:
                    cwd_dir = val
                i += 2
                continue
            fused = None
            for co in cwd_opts:
                if t.startswith(co + "="):
                    fused = t.split("=", 1)[1]
                    break
            if fused is not None:
                val = _strip_quotes(fused)
                if any(ch in val for ch in ("$", "`", "*", "?")):
                    cwd_dynamic = True
                else:
                    cwd_dir = val
                i += 1
                continue
        # value-taking option (separated form)
        if t in opts_with_arg and i + 1 < n:
            if t in _USER_OPTS:
                user_consumed = True  # -u USER supplies the user; no positional
            i += 2
            continue
        # fused long option --opt=value
        if t.startswith("--") and "=" in t:
            if t.split("=", 1)[0] in _USER_OPTS:
                user_consumed = True
            i += 1
            continue
        # any other option flag (no operand)
        if t.startswith("-") and len(t) > 1:
            i += 1
            continue
        # a bare positional operand the front-end consumes before its tail
        if consumed_pos < leading_pos:
            consumed_pos += 1
            i += 1
            continue
        # an optional leading USER positional (su/runuser without -u): consume ONE
        # bare word, then keep scanning for a trailing -c payload or argv tail.
        if consume_user and not user_consumed:
            user_consumed = True
            i += 1
            continue
        # first non-option, non-positional token: the tail starts here.
        break
    if args_marker is not None and not marker_seen:
        # gdb without --args runs no wrapped command tail.
        return None
    tail = toks[i:]
    if not tail:
        return None
    if joins:
        # watch joins its trailing argv into a single shell-evaluated string.
        return ("payload", " ".join(_strip_quotes(x) for x in tail), prefix, cwd_dir, cwd_dynamic)
    return ("tail", tail, prefix, cwd_dir, cwd_dynamic)


def _peel_one(sc: str):
    """Peel a SINGLE simple-command string through documented exec front-ends.

    Returns (rewritten_sc, payloads_for_this_sc) where rewritten_sc is the
    argv-tail form (empty string if the command reduced to a shell-string
    payload) and payloads_for_this_sc is a list of (payload_str, cwd_dir,
    cwd_dynamic) tuples to recurse. Front-ends stack (`flock /l strace node …`),
    so peeling iterates with a bounded depth. A cwd-changing front-end option
    (unshare --wd / bwrap --chdir / proot -w) is folded into the rewritten tail
    as an `env -C <dir> …` prefix so the existing cwd machinery resolves the
    wrapped relative protected path; a DYNAMIC cwd value is rendered as an
    UNRESOLVABLE `env -C <dynamic>` so relative launch/build tails fail closed.
    """
    cur = sc
    payloads = []
    for _ in range(8):
        toks = _safe_shlex(cur)
        if not toks:
            break
        res = _peel_exec_frontend(toks)
        if res is None:
            break
        kind, val, prefix, cwd_dir, cwd_dyn = res
        # render any front-end cwd-opt as an env -C prefix on the rewritten tail.
        cwd_prefix = []
        if cwd_dyn:
            # an unresolvable chdir: emit a value the env -C cwd extractor flags
            # as dynamic ($-bearing) so relative protected-path resolution stays
            # indeterminate (fail-closed for relative launch/build tails).
            cwd_prefix = ["env", "-C", "${__GUARD_DYNAMIC_CWD__}"]
        elif cwd_dir is not None:
            cwd_prefix = ["env", "-C", cwd_dir]
        if kind == "payload":
            payloads.append((val, cwd_dir, cwd_dyn))
            cur = ""
            break
        # kind == "tail": rebuild the simple command, preserving the ENV_WRAPPER
        # prefix (env -C/sudo --chdir cwd handling) + any front-end cwd-opt.
        cur = " ".join(prefix + cwd_prefix + val)
    return (cur, payloads)


def _unwrap_exec_frontends(groups: list, cwd_base: Optional[str] = None):
    """Recursively peel DOCUMENTED exec front-ends off every simple command,
    PRESERVING pipeline-group topology so cross-segment primitives (P5 endpoint,
    P6 prockill) are not falsely connected across `;`/`&&` boundaries.

    Input `groups` is the _pipeline_groups() output (a list of groups, each a
    list of simple-command strings). Returns (peeled_groups, peeled_flat,
    shell_payloads, changed):
      peeled_groups  : same topology with each segment replaced by its argv-tail
                       form (empty-string segments dropped).
      peeled_flat    : the flat list of all non-empty peeled segments (for the
                       segment-oriented primitives P1/P2/P3/P4/P7/P8/P9).
      shell_payloads : (payload_str, cwd, cwd_det) for shell-string forms.
      changed        : True iff any segment was actually rewritten.

    An UNKNOWN head is never a front-end, so a benign tail stays untouched (no
    blanket substring scan, no over-block).
    """
    peeled_groups = []
    peeled_flat = []
    payloads_out = []
    changed = False
    # a flat index over all segments to resolve each segment's effective cwd
    # against the FULL original ordering (cd chains span groups).
    flat_original = [seg for g in groups for seg in g]
    flat_pos = 0
    for g in groups:
        new_g = []
        for seg in g:
            rewritten, seg_payloads = _peel_one(seg)
            if rewritten != seg:
                changed = True
            # resolve effective cwd for any shell-string payload of this segment
            for pval, pcwd_dir, pcwd_dyn in seg_payloads:
                cwd, cwd_det = _effective_cwd_after(flat_original, flat_pos, cwd_base)
                if pcwd_dyn:
                    cwd, cwd_det = (cwd, False)
                elif pcwd_dir is not None:
                    cwd = os.path.normpath(os.path.join(cwd, pcwd_dir)) if (cwd and not os.path.isabs(pcwd_dir)) else os.path.normpath(pcwd_dir)
                    cwd_det = cwd_det if not os.path.isabs(pcwd_dir) else True
                payloads_out.append((pval, cwd, cwd_det))
            flat_pos += 1
            if rewritten:
                new_g.append(rewritten)
                peeled_flat.append(rewritten)
        if new_g:
            peeled_groups.append(new_g)
    return (peeled_groups, peeled_flat, payloads_out, changed)


_PM_AT_VERSION_RE = re.compile(r"^(yarn|pnpm|npm)(@.+)?$")


def _unwrap_corepack(simple_cmds: list) -> list:
    """Rewrite `corepack <pm>[@version] ...` simple commands to `<pm> ...` so
    P1/P8/P9 re-parse. The corepack proxy front-end accepts a pinned version
    (`corepack pnpm@9 exec …`); normalize the proxy token to the bare PM
    basename and preserve the remaining args."""
    out = []
    for sc in simple_cmds:
        toks = _safe_shlex(sc)
        cw = _command_words(toks) if toks else []
        if cw and cw[0][1] == "corepack" and len(cw[0][2]) >= 1:
            rest = cw[0][2]  # args after 'corepack' (head excluded)
            proxy = os.path.basename(_strip_quotes(rest[0]))
            m = _PM_AT_VERSION_RE.match(proxy)
            if m:
                pm = m.group(1)
                out.append(" ".join([pm] + rest[1:]))
                continue
        out.append(sc)
    return out


# ── P0 ANCHOR scan (HEAD-AGNOSTIC, wrapper-name-independent) ─────────────────
# Launch subcommand grammar: a protected command/launch-path is a daemon LAUNCH
# when followed (immediately, after its own flags) by one of these subcommands.
# These are generic process-lifecycle verbs, NOT project names.
_LAUNCH_SUBCMDS = frozenset({
    "daemon", "start", "start-sync", "serve", "run", "up", "spawn", "launch",
})


def _git_inspection_head(head: str, rest: list) -> bool:
    """True if this is a `git <readonly-subcmd> …` inspection command."""
    if head != "git":
        return False
    for t in rest:
        st = _strip_quotes(t)
        if not st or st.startswith("-"):
            continue
        return st in _GIT_READONLY_SUBCMDS
    # bare `git` with no subcommand: treat as inspection (no exec tail)
    return True


def _is_inspection_command(head: str, rest: list) -> bool:
    """A simple command is an inspection/data command (anchor scan skipped) when
    its HEAD basename is in the small read/inspect/edit allowlist, OR it is a
    read-only git invocation. This is the ONLY fixed head list the anchor uses."""
    if head in READ_INSPECT_EDIT_ALLOWLIST:
        return True
    if _git_inspection_head(head, rest):
        return True
    return False


def _anchor_exec_tokens(tokens: list) -> list:
    """Return the list of (index, token) bare EXECUTABLE-position candidate tokens
    for the anchor scan: tokens that are NOT options (no leading '-'), NOT a
    VAR=val env-prefix, and NOT inside a redirection. These are the words that a
    front-end / wrapper chain could exec() or pass to a build/launch. Quoted
    tokens are stripped. This is head-agnostic: it scans the WHOLE argv (the head
    itself is also a candidate, since a bare `<protected-cmd> <launch-subcmd>` has
    the protected command as its head).
    """
    out = []
    skip_next = False
    for i, raw in enumerate(tokens):
        if skip_next:
            skip_next = False
            continue
        st = _strip_quotes(raw)
        if not st:
            continue
        # redirection operators (> >> < 2> &>) and their target are not exec words
        if st in (">", ">>", "<", "2>", "&>", "1>", "2>>", "|", "&", ";"):
            skip_next = st in (">", ">>", "<", "2>", "&>", "1>", "2>>")
            continue
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", st):
            # VAR=val env-prefix
            continue
        if st.startswith("-"):
            continue
        out.append((i, st))
    return out


def _p0_anchor(simple_cmds: list, cfg: dict, cwd_base: Optional[str] = None,
               groups: Optional[list] = None) -> Optional[Verdict]:
    """HEAD-AGNOSTIC anchor scan. For ANY simple command whose head is NOT in the
    small read/inspect/edit allowlist, scan the WHOLE argv for a protected anchor
    in executable position and BLOCK on launch/build/kill grammar — INDEPENDENT of
    the wrapper/front-end head name. This is the load-bearing wrapper-agnostic
    gate: it does NOT enumerate wrappers; a head that is not an inspection command
    is treated as a possible launcher, so the trailing protected launch/build/kill
    can never hide behind a novel front-end of ANY name (no wrapper enumeration).
    """
    cmds = set(cfg.get("protected_cmds", []))
    launch_paths = cfg.get("protected_launch_paths", [])
    bpaths = cfg.get("protected_build_paths", [])
    ws = set(cfg.get("protected_build_workspaces", []))
    idents = cfg.get("protected_proc_idents", [])
    statefiles = cfg.get("protected_statefiles", [])
    groups = groups or []
    for idx, sc in enumerate(simple_cmds):
        tokens = _safe_shlex(sc)
        if not tokens:
            continue
        cw = _command_words(tokens)
        if not cw:
            continue
        _tok_idx, head, rest = cw[0]
        # GATE: inspection/data commands (the allowlist heads) are skipped so a
        # protected path/command named as DATA (grep pattern, echo arg, cat target,
        # diff operand, sed/awk script) still ALLOWS — no blanket substring scan.
        if _is_inspection_command(head, rest):
            continue
        # effective cwd for relative-path resolution + leading wrapper chdir.
        cwd, cwd_det = _effective_cwd_after(simple_cmds, idx, cwd_base)
        cwd, cwd_det = _fold_wrapper_cwd(cwd, cwd_det, tokens)
        exec_toks = _anchor_exec_tokens(tokens)

        # ── W1 LAUNCH-PATH ANCHOR: a protected launch path as a bare exec token ──
        for _i, st in exec_toks:
            if _path_matches_cwd(st, launch_paths, cwd, cwd_det):
                return _block("P0", "protected launch-path anchor behind a front-end")

        # ── W2 COMMAND-BASENAME ANCHOR: a protected command basename as bare token ─
        for _i, st in exec_toks:
            base = os.path.basename(st)
            if base in cmds:
                # The protected command in executable position is itself the launch
                # (e.g. `<wrapper> <protected-cmd> <launch-subcmd>`, including a
                # PID-1 init form `<init> -- <protected-cmd> <launch-subcmd>`).
                # Fail closed on the protected-command anchor regardless of head.
                return _block("P0", f"protected command anchor '{base}' behind a front-end")

        # ── W3 BUILD ANCHOR: build grammar co-occurring with a protected build ──
        # A build is indicated by a build-tool basename / package-manager `build` /
        # a package-runner running a build tool, ANYWHERE in the exec tokens. When
        # so, BLOCK if a protected build path / workspace / cwd is named.
        if _anchor_build_hits_protected(tokens, exec_toks, cfg, cwd, cwd_det, ws, bpaths):
            return _block("P0", "build anchor co-occurring with a protected build target behind a front-end")

        # ── W4 KILL ANCHOR: a kill verb in exec position + protected proc-ident ──
        # P6 already scans pipeline groups by text, but a kill behind an unknown
        # wrapper has head != kill so _is_kill_executor misses it. Detect a kill
        # verb anywhere in the exec tokens + a protected ident/statefile in the sc.
        if idents or statefiles:
            if any(os.path.basename(st) in KILL_VERBS for _i, st in exec_toks):
                sc_text = sc
                if any(ident in sc_text for ident in idents):
                    return _block("P0", "process-kill anchor carrying a protected identifier behind a front-end")
                for raw in re.split(r"\s+", sc_text):
                    s2 = _strip_quotes(raw.strip("'\""))
                    s2 = re.sub(r"^\d*<+", "", s2)
                    if s2 and not s2.startswith("-") and statefiles and _path_matches_any(s2, statefiles):
                        return _block("P0", "process-kill anchor reaching a protected statefile behind a front-end")
                # kill target via command substitution naming the ident
                for sub in _command_substitutions(sc):
                    if any(ident in sub for ident in idents):
                        return _block("P0", "process-kill anchor (subst) carrying a protected identifier behind a front-end")
    return None


def _anchor_build_hits_protected(tokens: list, exec_toks: list, cfg: dict,
                                  cwd: Optional[str], cwd_det: bool,
                                  ws: set, bpaths: list) -> bool:
    """True if the simple command (head-agnostic) indicates a BUILD that targets a
    protected package: a build-tool basename OR a package-manager `build` verb OR
    a package-runner build tool appears in the exec tokens, AND a protected build
    path / workspace selector / protected cwd is named. Conservative: requires an
    explicit protected anchor (path token, fused --flag=path value, workspace
    selector, or a protected effective cwd) — a build naming NO protected target
    is NOT blocked here (residual #1 / non-protected builds stay allowed)."""
    bases = [os.path.basename(st) for _i, st in exec_toks]
    pm_present = any(b in PKG_MANAGERS for b in bases)
    buildtool_present = any(b in BUILD_TOOL_BASENAMES for b in bases)
    runner_present = any(b in ("npx", "bunx") for b in bases)
    has_build_verb = any(st == "build" for _i, st in exec_toks)
    # A build is indicated by: a bare build tool, OR a pm/runner with a 'build'
    # verb, OR a package-runner invoking a build tool.
    build_indicated = (
        buildtool_present
        or (pm_present and has_build_verb)
        or (runner_present and buildtool_present)
        or (runner_present and has_build_verb)
    )
    if not build_indicated:
        return False
    # protected target: explicit workspace selector naming a protected workspace
    for i, raw in enumerate(tokens):
        st = _strip_quotes(raw)
        if st in ("workspace", "workspaces", "--filter", "-F", "-w", "--workspace") and i + 1 < len(tokens):
            sel = os.path.basename(_strip_quotes(tokens[i + 1]).rstrip("/"))
            if sel in ws:
                return True
        for f in ("--filter", "-F", "-w", "--workspace"):
            if st.startswith(f + "="):
                sel = os.path.basename(st.split("=", 1)[1].rstrip("/"))
                if sel in ws:
                    return True
    # protected target: a build path token (bare or fused --flag=path) under a
    # protected build path → always blocks (explicit protected target). Strip the
    # workspace/filter SELECTOR flags only for this path-token scan (so a selector
    # VALUE is not mis-scanned as a build target).
    raw_tokens = [_strip_quotes(x) for x in tokens]
    scan_tokens = _strip_selector_tokens(raw_tokens)
    if bpaths and _any_token_under_incl_flagvalue(scan_tokens, cfg, cwd, cwd_det):
        return True
    # protected target via the effective cwd (build-mode in a protected pkg /
    # monorepo root) — but an EXPLICIT non-protected build target (e.g.
    # `-p packages/<non-protected>/tsconfig.json`) proves the build is NOT of the
    # protected bundle, mirroring P8's exemption so a sibling-package build under
    # a wrapper at the repo root still ALLOWS (no over-block). Use the RAW tokens
    # here (NOT selector-stripped: tsc's `-w` watch flag must not be folded as a
    # workspace selector that swallows the following `-p <path>`).
    if _explicit_nonprotected_build_target(raw_tokens, cfg, cwd, cwd_det):
        return False
    # An EXPLICIT workspace selector naming a KNOWN non-protected workspace proves
    # the build targets that workspace (not the protected bundle), so the
    # cwd-based fallback must not over-block `<wrapper> yarn workspace <non-prot>
    # build` at the monorepo root (mirrors P8's selector handling).
    if _anchor_nonprotected_workspace_selector(tokens, cfg):
        return False
    if _cwd_in_protected_build_scope(cwd, cwd_det, cfg):
        return True
    if bpaths and _cwd_under_build_path(cwd, cwd_det, bpaths):
        return True
    return False


def _anchor_nonprotected_workspace_selector(tokens: list, cfg: dict) -> bool:
    """True if a workspace selector (`workspace <ws>` / `-w <ws>` / `--filter <ws>`)
    names a workspace in the KNOWN non-protected set and NONE names a protected
    one. Used by the build anchor to exempt an explicit non-protected workspace
    build from the cwd-based fallback (so it is not blocked at the monorepo root).
    """
    non_prot = set(cfg.get("non_protected_workspaces", []))
    prot = set(cfg.get("protected_build_workspaces", []))
    if not non_prot:
        return False
    sel_keywords = ("workspace", "workspaces")
    sel_flags = ("-w", "--workspace", "--filter", "-F")
    found_nonprot = False
    for i, raw in enumerate(tokens):
        st = _strip_quotes(raw)
        sel = None
        if st in sel_keywords and i + 1 < len(tokens):
            sel = os.path.basename(_strip_quotes(tokens[i + 1]).rstrip("/"))
        elif st in sel_flags and i + 1 < len(tokens):
            sel = os.path.basename(_strip_quotes(tokens[i + 1]).rstrip("/"))
        else:
            for f in sel_flags:
                if st.startswith(f + "="):
                    sel = os.path.basename(st.split("=", 1)[1].rstrip("/"))
                    break
        if sel is None:
            continue
        if sel in prot:
            return False  # an explicit protected selector → not exempt
        if sel in non_prot:
            found_nonprot = True
    return found_nonprot


# ── Top-level evaluate ───────────────────────────────────────────────────────

def evaluate(command: str, cwd_base: Optional[str] = None) -> Verdict:
    if command is None:
        return ALLOW
    if len(command) > MAX_COMMAND_CHARS:
        # oversized -> fail closed conservatively (treat as indeterminate)
        return _block("STEP1", "oversized command (fail-closed)")
    # Neutralize compound-group delimiters `( ) { }` so grouped launches/builds
    # decompose into ordinary simple commands (bare `$(`/`${` are preserved).
    norm_command = _strip_compound_delims(command)
    simple_cmds = _split_pipeline(norm_command)
    if not simple_cmds:
        return ALLOW
    simple_cmds = _unwrap_corepack(simple_cmds)
    # Pipeline GROUPS preserve `|` connectivity for cross-segment primitives
    # (P5 endpoint, P6 prockill). Command-substitution contents are retained for
    # inspection (the compound-strip leaves `$(...)` intact).
    groups = _pipeline_groups(norm_command)

    # STEP 0 — config self-protection FIRST (before config load). Run against the
    # ORIGINAL simple commands so a self-protection mutation hidden behind a
    # front-end is still seen by STEP0's own path-pattern scan, and additionally
    # against any front-end-peeled tails below.
    v = _step0_self_protection(simple_cmds)
    if v is not None:
        return v

    # ── Generic exec-front-end recursion (wrapper-AGNOSTIC) ──────────────────
    # Peel DOCUMENTED routine exec front-ends (flock/firejail/unshare/nsenter/
    # runuser/su/strace/watch/cpulimit/setpriv/perf/valgrind/...) off each simple
    # command so the protected launch/kill/build they exec() is exposed to the
    # primitive set, regardless of the front-end's NAME — and even behind an
    # ENV_WRAPPER (`env flock …`, `sudo flock …`). Group topology is PRESERVED so
    # P5/P6 are not falsely connected across `;`/`&&`. An UNKNOWN head is NOT a
    # front-end, so a benign tail stays allowed (no blanket substring scan).
    peeled_groups, peeled_flat, frontend_payloads, fe_changed = _unwrap_exec_frontends(groups, cwd_base)
    if fe_changed:
        # re-derive STEP0 against the peeled forms so a self-protection mutation
        # behind a front-end is also analyzed by STEP0's path-pattern scan.
        v = _step0_self_protection(peeled_flat)
        if v is not None:
            return v
        simple_cmds = peeled_flat
        groups = peeled_groups

    # Recurse front-end shell-string payloads (flock -c / su -c / runuser -c /
    # watch joined-tail) through evaluate() under the front-end's effective cwd.
    # Done BEFORE the config-load fail-closed return so a payload-wrapped danger
    # family still blocks even when the data file is absent/corrupt (a benign
    # payload re-evaluates to ALLOW, so this never over-blocks).
    for payload, pcwd, pcwd_det in frontend_payloads:
        if payload and payload not in (command, norm_command):
            pv = evaluate(payload, pcwd if pcwd_det else None)
            if pv[0] == "BLOCK":
                return pv

    # STEP 1 — load config; fail closed if unavailable.
    cfg = _load_config()
    if cfg is None:
        # fail-closed must also see the peeled tails (a front-end-wrapped danger
        # family under an absent/corrupt config still blocks).
        return _step1_indeterminate(simple_cmds)

    # Runner `-c`/`--call` payloads are shell commands the runner executes —
    # recursively evaluate each under the same cwd so a daemon launch / protected
    # build hidden inside the payload is caught (a benign payload re-evaluates to
    # ALLOW, so this does not over-block).
    for payload, pcwd, pcwd_det in _runner_call_payloads(simple_cmds, cfg, cwd_base):
        if payload and payload not in (command, norm_command):
            # recurse under the runner's effective cwd (None when indeterminate,
            # which makes relative launch/build payloads fail closed downstream)
            pv = evaluate(payload, pcwd if pcwd_det else None)
            if pv[0] == "BLOCK":
                return pv

    # STEP 2 — P0 HEAD-AGNOSTIC ANCHOR scan FIRST. This is the load-bearing
    # wrapper-agnostic gate: for any simple command whose head is NOT a read/
    # inspect/edit operation, it scans the WHOLE argv for a protected anchor in
    # executable position + launch/build/kill grammar, INDEPENDENT of the wrapper
    # head name. It catches a protected launch/build/kill behind ANY front-end —
    # documented (peeled above for precision) OR novel (any undocumented wrapper) —
    # without enumerating wrappers. The documented-front-end peel above still runs
    # for cwd/shell-payload precision, but it is no longer the load-bearing gate.
    v = _p0_anchor(simple_cmds, cfg, cwd_base, groups)
    if v is not None:
        return v

    # P1..P9 (order: launch, service, hotfile, statefile, endpoint,
    # prockill, globalbin, then package-script default-deny, then build arms).
    v = _p1_launch(simple_cmds, cfg, cwd_base, groups)
    if v is not None:
        return v
    v = _p2_service(simple_cmds, cfg)
    if v is not None:
        return v
    v = _p3_hotfile(simple_cmds, cfg, cwd_base)
    if v is not None:
        return v
    v = _p4_statefile(simple_cmds, cfg, cwd_base)
    if v is not None:
        return v
    # cross-segment primitives operate on pipeline GROUPS
    v = _p5_endpoint(groups, cfg)
    if v is not None:
        return v
    v = _p6_prockill(groups, cfg)
    if v is not None:
        return v
    v = _p7_globalbin(simple_cmds, cfg)
    if v is not None:
        return v

    # P9 default-deny package-script policy. If it returns a verdict (BLOCK or
    # ALLOW), honor it; only fall through to P8 build arms when P9 abstained.
    v = _p9_pkgscript(simple_cmds, cfg, cwd_base)
    if v is not None:
        if v[0] == "BLOCK":
            return v
        # Even when P9 ALLOWs a (non-protected) script-run, an EXPLICIT protected
        # build-path argument forwarded to that script still rebuilds the
        # protected bundle (`yarn build --project <protected>/tsconfig.json` from
        # a non-protected cwd). Run only the explicit-path subset of P8 before
        # honoring the ALLOW; the bare/cwd build-mode fallback is intentionally
        # skipped (it caused prior over-blocks).
        ev = _p8_explicit_protected_path(simple_cmds, cfg, cwd_base)
        if ev is not None:
            return ev
        return ALLOW

    v = _p8_build(simple_cmds, cfg, cwd_base)
    if v is not None:
        return v
    v = _p8_bare_build(simple_cmds, cfg)
    if v is not None:
        return v
    return ALLOW


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        # No parseable payload -> emit an INDETERMINATE sentinel so the bash
        # glue can fail closed for danger families (the glue, not us, decides).
        print("INDETERMINATE")
        return 0
    if payload.get("tool_name") != "Bash":
        print("ALLOW")
        return 0
    tool_input = payload.get("tool_input") or {}
    command = tool_input.get("command", "")
    # Seed cwd resolution from the payload's reported cwd if present, else the
    # process cwd, so a relative `cd packages/<x>` is resolvable (reduces
    # false-blocks while preserving fail-closed for genuinely-unknown cwds).
    cwd_base = tool_input.get("cwd") or os.environ.get("CLAUDE_GUARD_CWD")
    if not cwd_base:
        try:
            cwd_base = os.getcwd()
        except OSError:
            cwd_base = None
    decision, primitive, reason = evaluate(command, cwd_base)
    if decision == "BLOCK":
        sys.stderr.write(f"[protected-runtime-guard] BLOCK {primitive}: {reason}\n")
        print("BLOCK")
        return 0
    print("ALLOW")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
