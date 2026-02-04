"""
ThoughtFlow: A minimal, explicit, Pythonic substrate for LLM and agent systems.

Core Philosophy:
    - Tiny surface area: Few powerful primitives over many specialized classes
    - Explicit state: All state is visible, serializable, and replayable
    - Portability: Works across OpenAI, Anthropic, local models, serverless
    - Deterministic testing: Record/replay workflows, stable sessions

Basic Usage:
    >>> from thoughtflow import Agent
    >>> from thoughtflow.adapters import OpenAIAdapter
    >>>
    >>> adapter = OpenAIAdapter(api_key="...")
    >>> agent = Agent(adapter)
    >>> response = agent.call([
    ...     {"role": "user", "content": "Hello!"}
    ... ])
"""

from __future__ import annotations

# Core exports
from thoughtflow.agent import Agent
from thoughtflow.message import Message, MessageList

# Submodule access
from thoughtflow import adapters
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
    # Core
    "Agent",
    "Message",
    "MessageList",
    # Submodules
    "adapters",
    "tools",
    "memory",
    "trace",
    "eval",
    # Metadata
    "__version__",
]
