"""
ThoughtFlow Action Primitives.

Elemental actions that agents use to interact with the world.
All actions use only Python standard library - no external dependencies.

Categories:
    - Communication: SAY, ASK, NOTIFY
    - Information Retrieval: SEARCH, FETCH, SCRAPE, READ
    - Persistence: WRITE, POST
    - Temporal Control: SLEEP, WAIT, NOOP
    - Execution: RUN, CALL
"""

from __future__ import annotations

# Phase 1: Foundation
from thoughtflow.actions.noop import NOOP
from thoughtflow.actions.sleep import SLEEP
from thoughtflow.actions.say import SAY
from thoughtflow.actions.read_file import READ
from thoughtflow.actions.write_file import WRITE

# Phase 2: Network
from thoughtflow.actions.fetch import FETCH
from thoughtflow.actions.post import POST
from thoughtflow.actions.search import SEARCH
from thoughtflow.actions.scrape import SCRAPE

# Phase 3: Interaction
from thoughtflow.actions.ask import ASK
from thoughtflow.actions.wait import WAIT
from thoughtflow.actions.notify import NOTIFY

# Phase 4: Execution
from thoughtflow.actions.run import RUN
from thoughtflow.actions.call import CALL

__all__ = [
    # Communication
    "SAY",
    "ASK",
    "NOTIFY",
    # Information Retrieval
    "SEARCH",
    "FETCH",
    "SCRAPE",
    "READ",
    # Persistence
    "WRITE",
    "POST",
    # Temporal Control
    "SLEEP",
    "WAIT",
    "NOOP",
    # Execution
    "RUN",
    "CALL",
]
