"""
Evaluation utilities for ThoughtFlow.

Deterministic evaluation is a first-class constraint in ThoughtFlow.
This module provides utilities for:
- Record/replay workflows
- Golden tests (expected response shape/constraints)
- Prompt/version pinning
- Stable metrics extraction from traces

Example:
    >>> from thoughtflow.eval import Replay, Harness
    >>>
    >>> # Record a session
    >>> session = agent.call(messages, record=True)
    >>> session.save("golden.json")
    >>>
    >>> # Replay and compare
    >>> replay = Replay.load("golden.json")
    >>> results = replay.run(agent)
    >>> assert results.matches_expected()
"""

from __future__ import annotations

from thoughtflow.eval.replay import Replay
from thoughtflow.eval.harness import Harness, TestCase, TestResult

__all__ = [
    "Replay",
    "Harness",
    "TestCase",
    "TestResult",
]
