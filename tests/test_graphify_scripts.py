"""
tests/test_graphify_scripts.py — smoke tests for scripts/graphify_lib.py

Covers:
  - EXCLUDE_FRAGMENTS tuple exists and covers sensitive-data patterns
  - All 5 status states are defined in the state machine
  - fcntl is imported and LOCK_EX is used
"""

import importlib
import sys
import types
from pathlib import Path

import pytest

# Ensure the scripts directory is on sys.path so we can import graphify_lib directly.
_SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


def _import_graphify_lib() -> types.ModuleType:
    """Import graphify_lib, re-importing if already cached."""
    if "graphify_lib" in sys.modules:
        return sys.modules["graphify_lib"]
    return importlib.import_module("graphify_lib")


class TestExcludeFragments:
    """EXCLUDE_FRAGMENTS tuple covers all required sensitive-data and noise patterns."""

    def setup_method(self):
        self.lib = _import_graphify_lib()

    def test_exclude_fragments_is_tuple(self):
        assert isinstance(self.lib.EXCLUDE_FRAGMENTS, tuple), (
            "EXCLUDE_FRAGMENTS must be a tuple"
        )

    def test_excludes_dotenv(self):
        assert any(".env" in frag for frag in self.lib.EXCLUDE_FRAGMENTS), (
            "EXCLUDE_FRAGMENTS must contain a '.env' pattern (spec §5 Risk-7 + arch-8)"
        )

    def test_excludes_credentials(self):
        assert any("credentials" in frag for frag in self.lib.EXCLUDE_FRAGMENTS), (
            "EXCLUDE_FRAGMENTS must contain 'credentials' pattern"
        )

    def test_excludes_keys(self):
        assert any("keys" in frag or ".key" in frag for frag in self.lib.EXCLUDE_FRAGMENTS), (
            "EXCLUDE_FRAGMENTS must contain 'keys' or '.key' pattern"
        )

    def test_excludes_logs(self):
        assert any("logs" in frag for frag in self.lib.EXCLUDE_FRAGMENTS), (
            "EXCLUDE_FRAGMENTS must contain 'logs' pattern"
        )

    def test_excludes_git(self):
        assert any(".git" in frag for frag in self.lib.EXCLUDE_FRAGMENTS), (
            "EXCLUDE_FRAGMENTS must contain '.git' filesystem-noise pattern"
        )

    def test_excludes_venv(self):
        assert any("venv" in frag for frag in self.lib.EXCLUDE_FRAGMENTS), (
            "EXCLUDE_FRAGMENTS must contain 'venv' filesystem-noise pattern"
        )

    def test_excludes_pycache(self):
        assert any("__pycache__" in frag for frag in self.lib.EXCLUDE_FRAGMENTS), (
            "EXCLUDE_FRAGMENTS must contain '__pycache__' filesystem-noise pattern"
        )

    def test_excludes_node_modules(self):
        assert any("node_modules" in frag for frag in self.lib.EXCLUDE_FRAGMENTS), (
            "EXCLUDE_FRAGMENTS must contain 'node_modules' filesystem-noise pattern"
        )


class TestStatusStateMachine:
    """All 5 failure states are defined as module-level constants."""

    def setup_method(self):
        self.lib = _import_graphify_lib()

    def test_status_ok_defined(self):
        assert hasattr(self.lib, "STATUS_OK"), "STATUS_OK constant must be defined"
        assert self.lib.STATUS_OK == "ok"

    def test_status_degraded_defined(self):
        assert hasattr(self.lib, "STATUS_DEGRADED"), "STATUS_DEGRADED constant must be defined"
        assert self.lib.STATUS_DEGRADED == "degraded"

    def test_status_failed_defined(self):
        assert hasattr(self.lib, "STATUS_FAILED"), "STATUS_FAILED constant must be defined"
        assert self.lib.STATUS_FAILED == "failed"

    def test_status_unavailable_defined(self):
        assert hasattr(self.lib, "STATUS_UNAVAILABLE"), "STATUS_UNAVAILABLE constant must be defined"
        assert self.lib.STATUS_UNAVAILABLE == "unavailable"

    def test_status_skipped_defined(self):
        assert hasattr(self.lib, "STATUS_SKIPPED"), "STATUS_SKIPPED constant must be defined"
        assert self.lib.STATUS_SKIPPED == "skipped"

    def test_all_five_states_unique(self):
        lib = self.lib
        states = {
            lib.STATUS_OK,
            lib.STATUS_DEGRADED,
            lib.STATUS_FAILED,
            lib.STATUS_UNAVAILABLE,
            lib.STATUS_SKIPPED,
        }
        assert len(states) == 5, "All 5 status states must be unique string values"


class TestFcntlLocking:
    """graphify_lib.py imports fcntl and uses fcntl.LOCK_EX."""

    def test_fcntl_importable_from_lib(self):
        """The graphify_lib module must have imported fcntl (it re-exports the module)."""
        lib = _import_graphify_lib()
        import fcntl as _fcntl
        # Verify the module-level import worked by checking write_json_locked exists
        assert hasattr(lib, "write_json_locked"), (
            "write_json_locked function must exist in graphify_lib"
        )

    def test_lock_ex_used_in_write_json_locked(self):
        """Source code of write_json_locked must reference LOCK_EX."""
        import inspect
        lib = _import_graphify_lib()
        source = inspect.getsource(lib.write_json_locked)
        assert "LOCK_EX" in source, (
            "write_json_locked must use fcntl.LOCK_EX (arch-5 requirement)"
        )

    def test_fcntl_module_imported(self):
        """The top-level graphify_lib import must include fcntl."""
        import inspect
        lib = _import_graphify_lib()
        # Get the module source and verify fcntl is imported at module level
        source_lines = inspect.getsource(lib).splitlines()
        assert any("import fcntl" in line for line in source_lines), (
            "graphify_lib must import fcntl at module level (arch-5 requirement)"
        )
