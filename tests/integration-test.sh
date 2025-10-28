#!/bin/bash
# integration-test.sh - Integration tests for git tracking solution
# Location: ~/.claude/tests/integration-test.sh
#
# Tests core scenarios that QA identified as gaps:
# 1. Initial commit (no prior history)
# 2. /push command workflow
# 3. Detached HEAD handling
# 4. Special characters in filenames
# 5. Pre-commit hook modes

# Note: Not using set -e because we test failure cases

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Test results
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_TOTAL=0

# Helper functions
print_header() {
  echo ""
  echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${CYAN}$1${NC}"
  echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo ""
}

test_pass() {
  TESTS_PASSED=$((TESTS_PASSED + 1))
  TESTS_TOTAL=$((TESTS_TOTAL + 1))
  echo -e "${GREEN}✅ PASS${NC}: $1"
}

test_fail() {
  TESTS_FAILED=$((TESTS_FAILED + 1))
  TESTS_TOTAL=$((TESTS_TOTAL + 1))
  echo -e "${RED}❌ FAIL${NC}: $1"
  echo -e "${RED}   Error: $2${NC}"
}

cleanup_test_repo() {
  if [ -d "/tmp/git-test-repo" ]; then
    rm -rf /tmp/git-test-repo
  fi
}

create_test_repo() {
  cleanup_test_repo
  mkdir -p /tmp/git-test-repo
  cd /tmp/git-test-repo
  git init -q
  git config user.email "test@example.com"
  git config user.name "Test User"
}

# ============================================================================
# Test 1: Initial Commit (No Prior History)
# ============================================================================
test_initial_commit() {
  print_header "Test 1: Initial Commit (No Prior History)"

  create_test_repo

  # Install pre-commit hook
  bash ~/.claude/hooks/install-git-hooks.sh /tmp/git-test-repo > /dev/null 2>&1

  # Create a file
  echo "test content" > test.txt

  # Try to commit (should show warning about untracked file)
  git add test.txt

  # Create another untracked file
  echo "untracked" > untracked.txt

  # Export environment variables for warn mode
  export GIT_WARN_UNTRACKED=1
  export GIT_AUTO_STAGE_ALL=0
  export GIT_BLOCK_ON_UNTRACKED=0

  # Run pre-commit hook manually
  OUTPUT=$(bash ~/.claude/hooks/pre-commit-check.sh 2>&1)
  EXIT_CODE=$?

  if [ $EXIT_CODE -eq 0 ] && echo "$OUTPUT" | grep -q "untracked.txt"; then
    test_pass "Pre-commit hook detects untracked files on initial commit"
  else
    test_fail "Pre-commit hook on initial commit" "Exit code: $EXIT_CODE, Output: $OUTPUT"
  fi

  # Now commit successfully
  git commit -m "Initial commit" > /dev/null 2>&1

  if [ $? -eq 0 ]; then
    test_pass "Initial commit completes successfully"
  else
    test_fail "Initial commit" "Commit failed"
  fi

  # Verify post-commit warning
  OUTPUT=$(bash ~/.claude/hooks/post-commit-warn.sh 2>&1)

  if echo "$OUTPUT" | grep -q "untracked.txt"; then
    test_pass "Post-commit warning shows untracked files after initial commit"
  else
    test_fail "Post-commit warning" "Did not detect untracked.txt"
  fi
}

# ============================================================================
# Test 2: Detached HEAD Handling
# ============================================================================
test_detached_head() {
  print_header "Test 2: Detached HEAD Handling"

  create_test_repo

  # Create initial commit
  echo "initial" > file.txt
  git add file.txt
  git commit -m "Initial" > /dev/null 2>&1

  # Create second commit
  echo "second" >> file.txt
  git add file.txt
  git commit -m "Second" > /dev/null 2>&1

  # Get first commit hash
  FIRST_COMMIT=$(git rev-list --max-parents=0 HEAD)

  # Checkout first commit (detached HEAD)
  git checkout $FIRST_COMMIT > /dev/null 2>&1

  # Verify we're in detached HEAD state
  if ! git symbolic-ref HEAD > /dev/null 2>&1; then
    test_pass "Successfully entered detached HEAD state"
  else
    test_fail "Detached HEAD setup" "Still on a branch"
    return
  fi

  # Create untracked file
  echo "detached" > detached.txt

  # Test pre-commit hook in detached HEAD
  export GIT_WARN_UNTRACKED=1
  OUTPUT=$(bash ~/.claude/hooks/pre-commit-check.sh 2>&1)
  EXIT_CODE=$?

  if [ $EXIT_CODE -eq 0 ]; then
    test_pass "Pre-commit hook works in detached HEAD state"
  else
    test_fail "Pre-commit hook in detached HEAD" "Exit code: $EXIT_CODE"
  fi
}

# ============================================================================
# Test 3: Block Mode
# ============================================================================
test_block_mode() {
  print_header "Test 3: Block Mode (Prevent Commit with Untracked Files)"

  create_test_repo

  # Create initial commit
  echo "initial" > file.txt
  git add file.txt
  git commit -m "Initial" > /dev/null 2>&1

  # Create untracked file
  echo "untracked" > untracked.txt

  # Enable block mode
  export GIT_WARN_UNTRACKED=1
  export GIT_AUTO_STAGE_ALL=0
  export GIT_BLOCK_ON_UNTRACKED=1

  # Run pre-commit hook
  OUTPUT=$(bash ~/.claude/hooks/pre-commit-check.sh 2>&1)
  EXIT_CODE=$?

  if [ $EXIT_CODE -eq 1 ] && echo "$OUTPUT" | grep -q "Commit blocked"; then
    test_pass "Block mode prevents commit with untracked files"
  else
    test_fail "Block mode" "Exit code: $EXIT_CODE (expected 1)"
  fi

  # Verify error message contains helpful suggestions
  if echo "$OUTPUT" | grep -q "git add"; then
    test_pass "Block mode provides helpful suggestions"
  else
    test_fail "Block mode suggestions" "No 'git add' suggestion found"
  fi
}

# ============================================================================
# Test 4: Auto-Stage Mode
# ============================================================================
test_auto_stage_mode() {
  print_header "Test 4: Auto-Stage Mode"

  create_test_repo

  # Create initial commit
  echo "initial" > file.txt
  git add file.txt
  git commit -m "Initial" > /dev/null 2>&1

  # Create untracked files
  echo "untracked1" > untracked1.txt
  echo "untracked2" > untracked2.txt

  # Enable auto-stage mode
  export GIT_WARN_UNTRACKED=1
  export GIT_AUTO_STAGE_ALL=1
  export GIT_BLOCK_ON_UNTRACKED=0

  # Run pre-commit hook
  OUTPUT=$(bash ~/.claude/hooks/pre-commit-check.sh 2>&1)
  EXIT_CODE=$?

  if [ $EXIT_CODE -eq 0 ] && echo "$OUTPUT" | grep -q "Auto-staging"; then
    test_pass "Auto-stage mode runs without error"
  else
    test_fail "Auto-stage mode execution" "Exit code: $EXIT_CODE"
  fi

  # Verify files were staged
  if git diff --cached --name-only | grep -q "untracked1.txt"; then
    test_pass "Auto-stage mode stages untracked files"
  else
    test_fail "Auto-stage staging" "Files not staged"
  fi
}

# ============================================================================
# Test 5: Special Characters in Filenames
# ============================================================================
test_special_characters() {
  print_header "Test 5: Special Characters in Filenames"

  create_test_repo

  # Create initial commit
  echo "initial" > file.txt
  git add file.txt
  git commit -m "Initial" > /dev/null 2>&1

  # Create files with special characters
  echo "test" > "file with spaces.txt"
  echo "test" > "file-with-dashes.txt"
  echo "test" > "file_with_underscores.txt"

  # Enable warn mode
  export GIT_WARN_UNTRACKED=1
  export GIT_AUTO_STAGE_ALL=0
  export GIT_BLOCK_ON_UNTRACKED=0

  # Run pre-commit hook
  OUTPUT=$(bash ~/.claude/hooks/pre-commit-check.sh 2>&1)
  EXIT_CODE=$?

  if [ $EXIT_CODE -eq 0 ]; then
    test_pass "Pre-commit hook handles special characters in filenames"
  else
    test_fail "Special characters handling" "Exit code: $EXIT_CODE"
  fi

  # Verify all special files are detected
  if echo "$OUTPUT" | grep -q "file with spaces.txt"; then
    test_pass "Detects files with spaces"
  else
    test_fail "Files with spaces detection" "Not detected"
  fi
}

# ============================================================================
# Test 6: .gitignore Respect
# ============================================================================
test_gitignore_respect() {
  print_header "Test 6: .gitignore Respect"

  create_test_repo

  # Create initial commit
  echo "initial" > file.txt
  git add file.txt
  git commit -m "Initial" > /dev/null 2>&1

  # Create .gitignore
  echo "ignored.txt" > .gitignore
  echo "*.log" >> .gitignore
  git add .gitignore
  git commit -m "Add gitignore" > /dev/null 2>&1

  # Create ignored files
  echo "ignored" > ignored.txt
  echo "log" > test.log

  # Create non-ignored file
  echo "tracked" > tracked.txt

  # Enable warn mode
  export GIT_WARN_UNTRACKED=1

  # Run pre-commit hook
  OUTPUT=$(bash ~/.claude/hooks/pre-commit-check.sh 2>&1)

  # Should detect tracked.txt but NOT ignored files
  if echo "$OUTPUT" | grep -q "tracked.txt" && ! echo "$OUTPUT" | grep -q "ignored.txt" && ! echo "$OUTPUT" | grep -q "test.log"; then
    test_pass ".gitignore rules are respected"
  else
    test_fail ".gitignore respect" "Ignored files detected or tracked files missed"
  fi
}

# ============================================================================
# Test 7: Hook Installation
# ============================================================================
test_hook_installation() {
  print_header "Test 7: Hook Installation & Backup"

  create_test_repo

  # Create existing pre-commit hook
  mkdir -p .git/hooks
  echo "#!/bin/bash" > .git/hooks/pre-commit
  echo "echo 'existing hook'" >> .git/hooks/pre-commit
  chmod +x .git/hooks/pre-commit

  # Install our hook
  OUTPUT=$(bash ~/.claude/hooks/install-git-hooks.sh /tmp/git-test-repo 2>&1)

  # Check if backup was created
  if ls .git/hooks/pre-commit.backup.* > /dev/null 2>&1; then
    test_pass "Hook installation creates backup of existing hook"
  else
    test_fail "Hook backup creation" "No backup file found"
  fi

  # Verify new hook is installed
  if [ -x .git/hooks/pre-commit ]; then
    test_pass "New pre-commit hook is executable"
  else
    test_fail "Hook executable" "Hook not executable"
  fi
}

# ============================================================================
# Test 8: File Count Accuracy
# ============================================================================
test_file_count() {
  print_header "Test 8: File Count Accuracy"

  create_test_repo

  # Create initial commit
  echo "initial" > file.txt
  git add file.txt
  git commit -m "Initial" > /dev/null 2>&1

  # Test with 1 file
  echo "one" > one.txt
  export GIT_WARN_UNTRACKED=1
  OUTPUT=$(bash ~/.claude/hooks/pre-commit-check.sh 2>&1)
  if echo "$OUTPUT" | grep -q "1 untracked file(s)"; then
    test_pass "Accurate count for 1 file"
  else
    test_fail "Single file count" "Count mismatch"
  fi

  # Test with multiple files
  echo "two" > two.txt
  echo "three" > three.txt
  OUTPUT=$(bash ~/.claude/hooks/pre-commit-check.sh 2>&1)
  if echo "$OUTPUT" | grep -q "3 untracked file(s)"; then
    test_pass "Accurate count for multiple files"
  else
    test_fail "Multiple files count" "Count mismatch"
  fi
}

# ============================================================================
# Main Execution
# ============================================================================
main() {
  print_header "Git Tracking Solution - Integration Tests"

  echo "Starting integration tests..."
  echo "Test repository: /tmp/git-test-repo"
  echo ""

  # Run all tests
  test_initial_commit
  test_detached_head
  test_block_mode
  test_auto_stage_mode
  test_special_characters
  test_gitignore_respect
  test_hook_installation
  test_file_count

  # Cleanup
  cleanup_test_repo

  # Print summary
  print_header "Test Summary"

  echo "Total Tests: $TESTS_TOTAL"
  echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
  echo -e "${RED}Failed: $TESTS_FAILED${NC}"
  echo ""

  if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}✅ ALL TESTS PASSED${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    exit 0
  else
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${RED}❌ SOME TESTS FAILED${NC}"
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    exit 1
  fi
}

# Run main function
main
