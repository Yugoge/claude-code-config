"""
tests/test_graphify_workflow_contract.py — contract tests for graphify agent registration.

Verifies all three required registration sites for AC5:
  1. 'graphify' in CP_AGENTS (hooks/pretool-cp-checkin.py)
  2. 'graphify' in ALLOWED_AGENTS (scripts/spec-check.py)
  3. 'graphify' in agent_types list (hooks/prompt-workflow.py:~598-603)

These registrations ensure the graphify.json sentinel file is created at
UserPromptSubmit time, enabling the graphify subagent's mandatory FIRST ACTION
Read to succeed (mirroring test-writer precedent).
"""

import ast
import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).parent.parent


def _read_file(relative_path: str) -> str:
    """Read a file relative to the repo root."""
    full_path = _REPO_ROOT / relative_path
    assert full_path.exists(), f"Required file not found: {relative_path}"
    return full_path.read_text(encoding="utf-8")


class TestCPAgentsRegistration:
    """'graphify' must appear in CP_AGENTS in hooks/pretool-cp-checkin.py."""

    def test_graphify_in_cp_agents(self):
        source = _read_file("hooks/pretool-cp-checkin.py")
        # CP_AGENTS is a set literal — check that 'graphify' appears in the file
        assert "graphify" in source, (
            "'graphify' not found in hooks/pretool-cp-checkin.py; "
            "AC5 requires graphify in CP_AGENTS"
        )

    def test_cp_agents_block_contains_graphify(self):
        """The string 'graphify' must appear within the CP_AGENTS definition block."""
        source = _read_file("hooks/pretool-cp-checkin.py")
        # Find the CP_AGENTS block and verify graphify is in it
        cp_agents_idx = source.find("CP_AGENTS")
        assert cp_agents_idx != -1, "CP_AGENTS definition not found in pretool-cp-checkin.py"

        # Extract a window after CP_AGENTS definition to check the set contents
        window = source[cp_agents_idx:cp_agents_idx + 1200]
        assert "graphify" in window, (
            "'graphify' not found within 1200 chars of CP_AGENTS definition; "
            "it must be registered in the CP_AGENTS set"
        )


class TestAllowedAgentsRegistration:
    """'graphify' must appear in ALLOWED_AGENTS in scripts/spec-check.py."""

    def test_graphify_in_allowed_agents(self):
        source = _read_file("scripts/spec-check.py")
        assert "graphify" in source, (
            "'graphify' not found in scripts/spec-check.py; "
            "AC5 requires graphify in ALLOWED_AGENTS"
        )

    def test_allowed_agents_block_contains_graphify(self):
        """The string 'graphify' must appear within the ALLOWED_AGENTS definition block."""
        source = _read_file("scripts/spec-check.py")
        allowed_idx = source.find("ALLOWED_AGENTS")
        assert allowed_idx != -1, "ALLOWED_AGENTS definition not found in scripts/spec-check.py"

        window = source[allowed_idx:allowed_idx + 1200]
        assert "graphify" in window, (
            "'graphify' not found within 1200 chars of ALLOWED_AGENTS definition; "
            "it must be registered in the ALLOWED_AGENTS tuple"
        )


class TestPromptWorkflowRegistration:
    """'graphify' must appear in agent_types list in hooks/prompt-workflow.py."""

    def test_graphify_in_agent_types(self):
        source = _read_file("hooks/prompt-workflow.py")
        assert "graphify" in source, (
            "'graphify' not found in hooks/prompt-workflow.py; "
            "AC5 requires graphify in agent_types list so sentinel file is created"
        )

    def test_agent_types_block_contains_graphify(self):
        """'graphify' must appear within the agent_types definition in prompt-workflow.py."""
        source = _read_file("hooks/prompt-workflow.py")
        agent_types_idx = source.find("agent_types")
        assert agent_types_idx != -1, "agent_types variable not found in prompt-workflow.py"

        window = source[agent_types_idx:agent_types_idx + 1000]
        assert "graphify" in window, (
            "'graphify' not found within 1000 chars of agent_types definition; "
            "it must be in the agent_types list so graphify.json sentinel is created at UserPromptSubmit"
        )


class TestSymmetricRegistration:
    """CP_AGENTS and ALLOWED_AGENTS must both contain 'graphify' (arch-2 symmetry requirement)."""

    def test_both_registration_sites_have_graphify(self):
        checkin_source = _read_file("hooks/pretool-cp-checkin.py")
        spec_check_source = _read_file("scripts/spec-check.py")
        assert "graphify" in checkin_source and "graphify" in spec_check_source, (
            "graphify must be registered symmetrically in BOTH CP_AGENTS and ALLOWED_AGENTS "
            "(arch-2 requirement mirrors test-writer precedent)"
        )
