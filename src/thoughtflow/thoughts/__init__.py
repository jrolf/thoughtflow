"""
ThoughtFlow THOUGHT Subclasses.

Specialized thought primitives that extend the base THOUGHT class
for specific cognitive tasks.

Classes:
    - DECIDE: Constrained decision-making from finite choices
    - PLAN: Structured multi-step execution planning
"""

from __future__ import annotations

from thoughtflow.thoughts.decide import DECIDE
from thoughtflow.thoughts.plan import PLAN

__all__ = [
    "DECIDE",
    "PLAN",
]
