# Pinned modern-git slot (Option A, M17)

This is the **operator-supplied prerequisite** slot for the git ≥2.46
distribution that gives the overnight reference-transaction keystone its
git-native STRUCTURAL HEAD-switch guarantee. This cycle delivers the **slot
layout + selector wiring + launch self-test + rollback docs** ONLY — it does
**NOT** download or build git (no in-cycle network build; AC-A-prereq).

## Slot location

Default: `<main_root>/.claude/modern-git-slot/`
Override: set `CLAUDE_MODERN_GIT_SLOT=<dir>`.

The repo-tracked copy here (`scripts/modern-git-slot/`) is the template +
documentation. The live slot is created under `.claude/` (git-ignored) by the
operator placing the distribution there.

## Required layout (full distribution, NOT a lone binary)

```
<slot>/bin/git                  # the pinned >=2.46 git binary
<slot>/libexec/git-core/...     # matching helpers (git --exec-path target)
<slot>/manifest.json            # provenance: {version, sha256}
```

`git --exec-path` MUST resolve inside `<slot>/libexec/git-core` so helper
subcommands (`git-checkout`, `git-switch`, …) are the modern ones too
(codex round-2 finding #6 — a lone executable with mismatched system helpers
is rejected by the self-test).

## Provenance manifest (`manifest.json`)

```json
{
  "version": "2.46.0",
  "sha256": "<sha256 of bin/git>",
  "source": "operator-supplied pinned distribution",
  "placed_at": "<ISO-8601>"
}
```

The launch self-test (`scripts/overnight-git-selftest.sh`) verifies
`git --version` ≥ 2.46 AND `git --exec-path` inside the slot AND a functional
keystone-abort test before it lets state record
`guarantee_level=structural_head_switch`.

## REQUIRED git version for the keystone half-a guarantee

The keystone half-a structural HEAD-switch guarantee REQUIRES git **2.54.0**
(installed package `1:2.54.0-0ppa1~ubuntu24.04.1`, supplied from the git-core
PPA at `/etc/apt/sources.list.d/git-core-ubuntu-ppa-noble.sources` →
`https://ppa.launchpadcontent.net/git-core/ppa/ubuntu noble/main`). On git 2.54
the `reference-transaction` hook fires for a main-worktree symref HEAD
branch-switch off master, so the keystone can ABORT it; on git 2.43 that hook
is silent for the symref switch and the keystone gives no structural HEAD-switch
protection.

**Functional check (authoritative):** `scripts/overnight-git-selftest.sh` MUST
report `reference_transaction_selftest_result="structural_head_switch"` (and
`structural_claim_allowed=true`) on the host. That is the single source of truth
for whether half-a is structural — not the version string alone.

**Reversible rollback + its consequence:** downgrade to the pinned
`1:2.43.0-1ubuntu7.3` (still in the apt version table — `apt-cache policy git`
shows both) and remove the `git-core-ubuntu-ppa-noble.sources` PPA. The
CONSEQUENCE of rollback is that half-a DEGRADES from structural to best-effort:
the self-test records `reference_transaction_selftest_result` other than
`structural_head_switch` and `structural_claim_allowed=false`. Isolation,
worktree creation, the bwrap write-half, and the M13 policy-shim / M14a firewall
/ M15 bash-safety defense-in-depth ALL still hold — isolation is NEVER gated on
the git version. "核心加固不得被宿主升级阻断" cuts both ways: the core hardening
must be broken neither by a host upgrade nor by a downgrade.

## How it is used

`scripts/overnight-git/git-selector` (the modern-git PATH selector) is prepended
to the overnight actor's PATH and delegates to `<slot>/bin/git` when the slot is
populated; otherwise it falls through to the system git. The selector is
SEPARATE from the policy shim (`git-policy-shim`) so relaxing policy never drops
the selector.

## Rollback (minimal + reversible — AC-A-prereq)

Removing the slot directory fully reverts the Option-A overlay:

```bash
rm -rf <main_root>/.claude/modern-git-slot
```

After removal the selector falls through to system git, the self-test records
`best_effort_head_switch` / `structural_claim_allowed=false`, and the
compensating layers (M13 policy shim + M14a firewall + M15 bash-safety) carry
the exact-incident block (AC11) unchanged. Nothing else needs to be undone —
the isolation, worktree creation, and master-branch-ref protection are
UNCONDITIONAL and do not depend on the slot.

## Sub-modes (codex round-2 finding #1)

- **A1** (host-wide modern git: PATH `git` AND `/usr/bin/git` AND
  `/usr/lib/git-core/git` all ≥2.46): keystone covers the branch-switch
  structurally on every path; M13/M15 MAY relax to Should-Have.
- **A2** (PATH-pinned only — the current host: old absolute `/usr/bin/git`
  2.43.0 still reachable): M13/M14a/M15 remain MUST and AC11 must pass.

This slot mechanism delivers A2; reaching A1 is an out-of-cycle host-toolchain
choice the operator may make later.
