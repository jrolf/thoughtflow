"""
Unit tests for the Agent module.

NOTE: The Agent class has been deprecated in favor of THOUGHT.
These tests verify the deprecation behavior.
"""

from __future__ import annotations

import warnings
import pytest

from thoughtflow.agent import Agent


class TestAgentDeprecation:
    """Tests for Agent deprecation behavior."""

    def test_agent_raises_deprecation_warning(self) -> None:
        """
        Agent initialization should raise DeprecationWarning.
        
        This alerts users that Agent is deprecated and they
        should migrate to THOUGHT instead.
        
        Remove this test if: We remove the Agent class entirely.
        """
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            try:
                Agent()
            except NotImplementedError:
                pass  # Expected
            
            # Check that DeprecationWarning was raised
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "deprecated" in str(w[0].message).lower()

    def test_agent_raises_not_implemented_error(self) -> None:
        """
        Agent should raise NotImplementedError after deprecation warning.
        
        This prevents accidental usage of the deprecated class.
        
        Remove this test if: We remove the Agent class entirely.
        """
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # Ignore the deprecation warning
            with pytest.raises(NotImplementedError, match="deprecated"):
                Agent()

    def test_agent_deprecation_message_mentions_thought(self) -> None:
        """
        Agent deprecation message should mention THOUGHT as replacement.
        
        This helps users understand what to migrate to.
        
        Remove this test if: We change the migration path.
        """
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            try:
                Agent()
            except NotImplementedError:
                pass
            
            warning_msg = str(w[0].message).lower()
            assert "thought" in warning_msg
