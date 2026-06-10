"""
Evaluation utilities for ThoughtFlow.

Deterministic evaluation is a first-class constraint in ThoughtFlow, and it
is built from the primitives you already know:

- **Record:** ``llm.record(memory)`` captures every LLM exchange as MEMORY
  events (see thoughtflow.llm).
- **Replay:** ``LLM.replay(memory)`` returns a drop-in LLM that serves the
  recorded responses — flows re-run deterministically, offline.
- **Harness:** a thin runner that executes a flow (any ``memory -> memory``
  callable) against a list of test cases and collects pass/fail results.

Example:
    >>> from thoughtflow import MEMORY
    >>> from thoughtflow.eval import Harness, TestCase
    >>>
    >>> cases = [
    ...     TestCase(
    ...         name="greeting",
    ...         setup=lambda m: m.add_msg("user", "Hello!"),
    ...         check=lambda m: "hello" in (m.last_asst_msg(content_only=True) or "").lower(),
    ...     ),
    ... ]
    >>> results = Harness(cases).run(my_flow)   # my_flow: memory -> memory
    >>> print(results.summary())
"""

from __future__ import annotations

from thoughtflow.eval.harness import Harness, HarnessResults, TestCase, TestResult

__all__ = [
    "Harness",
    "HarnessResults",
    "TestCase",
    "TestResult",
]
