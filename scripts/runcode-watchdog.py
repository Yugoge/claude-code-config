#!/usr/bin/env python3
"""
Watchdog process for browser_run_code timeout enforcement.

Spawned by pretool-runcode-watchdog.py as a detached background process.
Sleeps for the configured timeout, then terminates JavaScript execution
via Chrome DevTools Protocol if the tool has not completed.

Usage: python3 runcode-watchdog.py <timeout_seconds> <pid_file> <cdp_endpoint>

Exit codes:
  0: Normal exit (cancelled by SIGTERM or timeout fired successfully)
  1: Error (invalid args, CDP failure)
"""

import json
import os
import signal
import sys
import time

_cancelled = False


def _sigterm_handler(signum, frame):
    """Handle SIGTERM from PostToolUse hook — tool completed normally."""
    global _cancelled
    _cancelled = True


def _cleanup_pid_file(pid_file: str):
    try:
        stored = int(open(pid_file).read().strip())
        if stored == os.getpid():
            os.unlink(pid_file)
    except (OSError, ValueError):
        pass


def _fetch_ws_url(cdp_endpoint: str) -> str | None:
    """Fetch the WebSocket debugger URL from CDP page list."""
    import urllib.request

    try:
        req = urllib.request.urlopen(f"{cdp_endpoint}/json", timeout=5)
        pages = json.loads(req.read())
    except Exception as e:
        print(f"watchdog: failed to fetch CDP page list: {e}", file=sys.stderr)
        return None

    if not pages:
        print("watchdog: no pages found in CDP", file=sys.stderr)
        return None

    url = pages[0].get("webSocketDebuggerUrl")
    if not url:
        print("watchdog: no webSocketDebuggerUrl in first page", file=sys.stderr)
    return url


def _send_terminate(ws_url: str) -> bool:
    """Connect to CDP via WebSocket and send Runtime.terminateExecution."""
    try:
        import websocket

        ws = websocket.create_connection(ws_url, timeout=5)
        ws.send(json.dumps({"id": 1, "method": "Runtime.terminateExecution"}))
        ws.recv()
        ws.close()
        return True
    except Exception as e:
        print(f"watchdog: CDP WebSocket error: {e}", file=sys.stderr)
        return False


def _write_timeout_marker(pid_file: str):
    """Write marker file indicating timeout fired."""
    try:
        with open(f"{pid_file}.timeout", "w") as f:
            f.write(str(int(time.time())))
    except OSError:
        pass


def _wait_for_timeout(timeout_seconds: int) -> bool:
    """Sleep in small increments, return True if cancelled by SIGTERM."""
    elapsed = 0.0
    while elapsed < timeout_seconds and not _cancelled:
        time.sleep(0.5)
        elapsed += 0.5
    return _cancelled


def main():
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <timeout_seconds> <pid_file> <cdp_endpoint>", file=sys.stderr)
        sys.exit(1)

    timeout_seconds = int(sys.argv[1])
    pid_file = sys.argv[2]
    cdp_endpoint = sys.argv[3]

    signal.signal(signal.SIGTERM, _sigterm_handler)

    with open(pid_file, "w") as f:
        f.write(str(os.getpid()))

    if _wait_for_timeout(timeout_seconds):
        _cleanup_pid_file(pid_file)
        sys.exit(0)

    print(f"watchdog: timeout ({timeout_seconds}s) reached, terminating execution", file=sys.stderr)
    ws_url = _fetch_ws_url(cdp_endpoint)
    if ws_url:
        _send_terminate(ws_url)

    _write_timeout_marker(pid_file)
    _cleanup_pid_file(pid_file)
    sys.exit(0)


if __name__ == "__main__":
    main()
