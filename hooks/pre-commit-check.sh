#!/bin/bash
# pre-commit-check.sh - Detect untracked files before commit
# Part of Claude Code git tracking solution
# Location: ~/.claude/hooks/pre-commit-check.sh

# Configuration (from environment variables)
AUTO_STAGE=${GIT_AUTO_STAGE_ALL:-0}
BLOCK_MODE=${GIT_BLOCK_ON_UNTRACKED:-0}
WARN_MODE=${GIT_WARN_UNTRACKED:-1}

# Colors for terminal output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Detect untracked files (respecting .gitignore)
UNTRACKED=$(git ls-files --others --exclude-standard 2>/dev/null)

# Exit early if no untracked files
if [ -z "$UNTRACKED" ]; then
  exit 0
fi

# Count untracked files (more robust method)
COUNT=$(echo "$UNTRACKED" | grep -c '^' || echo "1")

# Auto-stage mode - automatically add all files
if [ "$AUTO_STAGE" = "1" ]; then
  echo -e "${BLUE}🔄 Auto-staging all files...${NC}"
  echo ""
  echo "Adding:"
  echo "$UNTRACKED" | sed 's/^/   - /'
  echo ""
  # Honour the explicit GIT_AUTO_STAGE_ALL=1 opt-in, but still hard-exclude
  # transient framework/runtime junk via the shared smart-staging-resolver
  # (autostage mode). Temp file + rc check so a crashed resolver does not
  # silently stage nothing; fallback 'git add .' still honours .gitignore.
  RESOLVER="$HOME/.claude/scripts/smart-staging-resolver.py"
  VENV_ACTIVATE="$HOME/.claude/venv/bin/activate"
  STAGE_RC=0
  # use-source-venv: invoke python3 against the resolver ONLY when BOTH the resolver
  # AND the framework venv activation file exist. A bare interpreter run (no activated
  # venv) violates the use-source-venv standard, so a missing venv must take the plain
  # stage-all fallback rather than fall through to a bare invocation (closes fail-open).
  if [ -f "$RESOLVER" ] && [ -f "$VENV_ACTIVATE" ] && command -v python3 >/dev/null 2>&1; then
    SSR_TMP=$(mktemp)
    # Activate the framework venv FIRST, then invoke the interpreter. The entry guard
    # already proved the activation file exists; '|| true' keeps a sourcing hiccup from
    # aborting the hook while still taking the resolver branch.
    . "$VENV_ACTIVATE" || true
    if python3 "$RESOLVER" --repo "$PWD" autostage -z >"$SSR_TMP" 2>/dev/null; then
      xargs -0 -r git add -- <"$SSR_TMP"; STAGE_RC=$?
    else
      echo -e "${YELLOW}⚠️  resolver failed; falling back to gitignore-respecting 'git add .'${NC}"
      git add .; STAGE_RC=$?
    fi
    rm -f "$SSR_TMP"
  else
    # Resolver or framework venv unavailable: plain 'git add .' STILL honours .gitignore.
    git add .; STAGE_RC=$?
  fi
  if [ "$STAGE_RC" -eq 0 ]; then
    echo -e "${GREEN}✅ All files staged automatically (transient junk excluded)${NC}"
    echo ""
    echo "Note: Auto-staged all files minus transient junk (GIT_AUTO_STAGE_ALL=1)"
  else
    echo -e "${RED}❌ Error staging files${NC}"
    exit 2
  fi
  exit 0
fi

# Block mode - prevent commit if untracked files exist
if [ "$BLOCK_MODE" = "1" ]; then
  echo -e "${RED}❌ ERROR: Untracked files detected!${NC}"
  echo ""
  echo "The following $COUNT file(s) are not tracked by git:"
  echo "$UNTRACKED" | sed 's/^/   - /'
  echo ""
  echo "Commit blocked. Please:"
  echo "  1. Add files: git add <file>"
  echo "  2. Or ignore: echo 'filename' >> .gitignore"
  echo "  3. Or stage all: git add ."
  echo ""
  echo "To bypass: git commit --no-verify"
  exit 1
fi

# Warn mode (default) - show warning but allow commit
if [ "$WARN_MODE" = "1" ]; then
  echo -e "${YELLOW}⚠️  Warning: $COUNT untracked file(s) detected:${NC}"
  echo "$UNTRACKED" | sed 's/^/   - /'
  echo ""
  echo "Commit will proceed without these files."
  echo "Run 'git add .' to include them, or use /push command."
  echo ""
fi

exit 0
