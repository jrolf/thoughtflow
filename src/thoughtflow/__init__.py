"""
ThoughtFlow: A minimal, explicit, Pythonic substrate for LLM and agent systems.

Core Philosophy:
    - Tiny surface area: Few powerful primitives over many specialized classes
    - Explicit state: All state is visible, serializable, and replayable
    - Portability: Works across OpenAI, Anthropic, local models, serverless
    - Deterministic testing: Record/replay workflows, stable sessions

Core Primitives:
    - LLM: Multi-provider interface for language model calls
    - MEMORY: Event-sourced state container (messages, logs, reflections, variables)
    - THOUGHT: Unit of cognition (Prompt + Context + LLM + Parsing + Validation)
    - DECIDE: Constrained decisions from finite choices (subclass of THOUGHT)
    - PLAN: Structured multi-step execution plans (subclass of THOUGHT)
    - ACTION: External operation wrapper with consistent logging

Action Primitives (elemental agent verbs):
    - Communication: SAY, ASK, NOTIFY
    - Information Retrieval: SEARCH, FETCH, SCRAPE, READ
    - Persistence: WRITE, POST
    - Temporal Control: SLEEP, WAIT, NOOP
    - Execution: RUN, CALL

Basic Usage:
    >>> from thoughtflow import LLM, MEMORY, THOUGHT
    >>>
    >>> llm = LLM("openai:gpt-4o", key="your-api-key")
    >>> memory = MEMORY()
    >>> memory.add_msg("user", "Hello!")
    >>>
    >>> thought = THOUGHT(
    ...     name="respond",
    ...     llm=llm,
    ...     prompt="Respond to the user message: {last_user_msg}"
    ... )
    >>> memory = thought(memory)
    >>> result = memory.get_var("respond_result")
"""

from __future__ import annotations

# Core primitives
from thoughtflow.llm import LLM
from thoughtflow.memory import MEMORY
from thoughtflow.thought import THOUGHT
from thoughtflow.thoughts import DECIDE, PLAN
from thoughtflow.action import ACTION

# Action primitives
from thoughtflow.actions import (
    # Communication
    SAY,
    ASK,
    NOTIFY,
    # Information Retrieval
    SEARCH,
    FETCH,
    SCRAPE,
    READ,
    # Persistence
    WRITE,
    POST,
    # Temporal Control
    SLEEP,
    WAIT,
    NOOP,
    # Execution
    RUN,
    CALL,
)

# Utilities
from thoughtflow._util import (
    EventStamp,
    event_stamp,
    hashify,
    construct_prompt,
    construct_msgs,
    valid_extract,
    ValidExtractError,
)

# Keep message types for potential utility
from thoughtflow.message import Message, MessageList

# Submodule access (trace, eval for advanced usage)
from thoughtflow import trace
from thoughtflow import eval

# Version
try:
    from importlib.metadata import version as _get_version

    __version__ = _get_version("thoughtflow")
except Exception:
    __version__ = "0.0.0"

# Public API
__all__ = [
    # Core Primitives
    "LLM",
    "MEMORY",
    "THOUGHT",
    "DECIDE",
    "PLAN",
    "ACTION",
    # Action Primitives - Communication
    "SAY",
    "ASK",
    "NOTIFY",
    # Action Primitives - Information Retrieval
    "SEARCH",
    "FETCH",
    "SCRAPE",
    "READ",
    # Action Primitives - Persistence
    "WRITE",
    "POST",
    # Action Primitives - Temporal Control
    "SLEEP",
    "WAIT",
    "NOOP",
    # Action Primitives - Execution
    "RUN",
    "CALL",
    # Utilities
    "EventStamp",
    "event_stamp",
    "hashify",
    "construct_prompt",
    "construct_msgs",
    "valid_extract",
    "ValidExtractError",
    # Types
    "Message",
    "MessageList",
    # Submodules
    "trace",
    "eval",
    # Metadata
    "__version__",
]
