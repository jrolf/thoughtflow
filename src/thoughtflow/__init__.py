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
    - ACTION: External operation wrapper with consistent logging

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
from thoughtflow.memory.base import MEMORY
from thoughtflow.thought import THOUGHT
from thoughtflow.action import ACTION

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

# Deprecated (for backward compatibility)
from thoughtflow.agent import Agent, TracedAgent

# Keep message types for potential utility
from thoughtflow.message import Message, MessageList

# Submodule access (keep tools, trace, eval for advanced usage)
from thoughtflow import tools
from thoughtflow import memory
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
    "ACTION",
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
    # Deprecated
    "Agent",
    "TracedAgent",
    # Submodules
    "tools",
    "memory",
    "trace",
    "eval",
    # Metadata
    "__version__",
]
