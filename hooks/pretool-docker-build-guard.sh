#!/bin/bash
# Hook: PreToolUse:Bash
# Prevents docker build of Dockerfile.webapp without --build-arg HAPPY_SERVER_URL
# This ensures the web app always connects to the correct API server.

COMMAND="$CLAUDE_TOOL_INPUT"

# Check if this is a docker build command for Dockerfile.webapp
if echo "$COMMAND" | grep -q "docker build" && echo "$COMMAND" | grep -q "Dockerfile.webapp"; then
    # Check if --build-arg HAPPY_SERVER_URL is present
    if ! echo "$COMMAND" | grep -q "HAPPY_SERVER_URL"; then
        echo "BLOCKED: docker build for Dockerfile.webapp MUST include --build-arg HAPPY_SERVER_URL=https://api.life-ai.app"
        echo ""
        echo "Without this, the web app defaults to api.cluster-fluster.com (WRONG)."
        echo ""
        echo "Correct command:"
        echo "  docker build -f Dockerfile.webapp --build-arg HAPPY_SERVER_URL=https://api.life-ai.app -t <tag> ."
        exit 1
    fi

    # Also check the URL value is correct (not cluster-fluster)
    if echo "$COMMAND" | grep -q "cluster-fluster"; then
        echo "BLOCKED: HAPPY_SERVER_URL must NOT be api.cluster-fluster.com"
        echo "Use: --build-arg HAPPY_SERVER_URL=https://api.life-ai.app"
        exit 1
    fi
fi

exit 0
