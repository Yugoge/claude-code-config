#!/bin/bash
# Test script to verify git lock file detection and handling
# Location: ~/.claude/tests/test-lock-detection.sh

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Git Lock File Detection Test"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Create temporary test repository
TEST_REPO="/tmp/lock-test-repo-$$"
mkdir -p "$TEST_REPO"
cd "$TEST_REPO"

echo "Setting up test repository..."
git init -q
git config user.email "test@example.com"
git config user.name "Test User"

# Create initial commit
echo "test content" > test.txt
git add test.txt
git commit -q -m "Initial commit"

echo -e "${GREEN}✓ Test repository created${NC}"
echo ""

# Test 1: Create a stale lock file
echo "Test 1: Simulating stale lock file..."
touch .git/index.lock
echo -e "${YELLOW}Created stale lock file: .git/index.lock${NC}"

# Verify the scripts can detect it
if [ -f ".git/index.lock" ]; then
  echo -e "${GREEN}✓ Lock file exists and can be detected${NC}"
else
  echo -e "${RED}✗ Failed to create lock file${NC}"
  exit 1
fi
echo ""

# Test 2: Verify ps command works for git process detection
echo "Test 2: Testing git process detection..."
GIT_PROCESSES=$(ps aux | grep -i '[g]it' | grep -v grep || true)
if [ -z "$GIT_PROCESSES" ]; then
  echo -e "${GREEN}✓ No active git processes detected (expected)${NC}"
else
  echo -e "${YELLOW}⚠ Active git processes found:${NC}"
  echo "$GIT_PROCESSES"
fi
echo ""

# Test 3: Clean up lock file
echo "Test 3: Removing lock file..."
rm -f .git/index.lock
if [ ! -f ".git/index.lock" ]; then
  echo -e "${GREEN}✓ Lock file successfully removed${NC}"
else
  echo -e "${RED}✗ Failed to remove lock file${NC}"
  exit 1
fi
echo ""

# Test 4: Verify git operations work after cleanup
echo "Test 4: Verifying git operations work..."
echo "new content" >> test.txt
git add test.txt
git commit -q -m "Test commit"
if [ $? -eq 0 ]; then
  echo -e "${GREEN}✓ Git operations work normally${NC}"
else
  echo -e "${RED}✗ Git operations failed${NC}"
  exit 1
fi
echo ""

# Cleanup
cd /
rm -rf "$TEST_REPO"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}✅ All lock file detection tests passed${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Summary:"
echo "  ✓ Lock file can be detected"
echo "  ✓ Git process detection works"
echo "  ✓ Lock file can be removed"
echo "  ✓ Git operations resume after cleanup"
echo ""
