"""
ThoughtFlow: Powerful AI systems from simple parts.

Core Philosophy:
    - Simple parts: A handful of composable primitives, not forty classes
    - Explicit state: All state is visible, serializable, and replayable
    - Portability: Works across OpenAI, Anthropic, local models, serverless
    - Deterministic testing: Record/replay workflows, stable sessions

Core Primitives:
    - LLM: Multi-provider interface for generative text (`call`) and structured tool chat (`chat`)
    - DM: Multi-provider System-One decision models (`choice`, `noul`, `score`, `box`)
    - EMBED: Multi-provider vector embeddings
    - MEMORY: Event-sourced state container (messages, scopes, budgets, compaction, suspend/resume)
    - THOUGHT: Unit of cognition (Prompt + Context + LLM + Parsing + Validation + Outcome)
    - DECIDE: Constrained decisions over `LLM` or `DM` (`choice`, `noul`, `score`, `multi`)
    - PLAN: Structured multi-step execution plans (subclass of THOUGHT)
    - ACTION: Imperative external operation wrapper (+ 14 stdlib verbs)
    - TOOL / MCP: Declarative model-selectable tools, Model Context Protocol client, and `ReplayTOOL`
    - AGENT / tool_loop: Governed, write-ahead autonomous tool loop (`ReactAgent`, `ReflectAgent`, `PlanActAgent`)
    - DELEGATE / CHAT / WORKFLOW / CHRON: Coordination and orchestration primitives

Action Primitives (elemental agent verbs):
    - Communication: SAY, ASK, NOTIFY
    - Information Retrieval: SEARCH, FETCH, SCRAPE, READ
    - Persistence: WRITE, POST
    - Temporal Control: SLEEP, WAIT, NOOP
    - Scheduling: CHRON
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
from thoughtflow.llm import LLM, OpenAICompatibleLLM, ReplayLLM, ReplayMissError
from thoughtflow.llm_chat import ChatError
from thoughtflow.llm_cache import cached_system, cached_message
from thoughtflow.providers import GroqLLM, CerebrasLLM, OpenRouterLLM
from thoughtflow.embed import EMBED, ReplayEMBED
from thoughtflow.dm import DM, ReplayDM, DecisionError
from thoughtflow.memory import MEMORY
from thoughtflow.thought import THOUGHT
from thoughtflow.thoughts import DECIDE, PLAN, run_plan
from thoughtflow.action import ACTION
from thoughtflow.tool import TOOL, ReplayTOOL
from thoughtflow.mcp import MCP
from thoughtflow.agent import AGENT, tool_loop
from thoughtflow.agents import ReactAgent, ReflectAgent, PlanActAgent
from thoughtflow.delegate import DELEGATE, map_thought
from thoughtflow.workflow import WORKFLOW
from thoughtflow.chron import CHRON
from thoughtflow.chat import CHAT

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
    TemplateRenderError,
)

# Keep message types for potential utility
from thoughtflow.message import Message, MessageList

# Submodule access (eval for harness-style testing)
from thoughtflow import eval

# Version
try:
    from importlib.metadata import version as _get_version

    __version__ = _get_version("thoughtflow")
except Exception:
    __version__ = "0.3.1"

# Public API
__all__ = [
    # Core Primitives
    "LLM",
    "OpenAICompatibleLLM",
    "ReplayLLM",
    "ChatError",
    "ReplayMissError",
    "GroqLLM",
    "CerebrasLLM",
    "OpenRouterLLM",
    "cached_system",
    "cached_message",
    "EMBED",
    "ReplayEMBED",
    "DM",
    "ReplayDM",
    "DecisionError",
    "MEMORY",
    "THOUGHT",
    "DECIDE",
    "PLAN",
    "run_plan",
    "ACTION",
    "TOOL",
    "ReplayTOOL",
    "MCP",
    "AGENT",
    "tool_loop",
    "ReactAgent",
    "ReflectAgent",
    "PlanActAgent",
    "DELEGATE",
    "map_thought",
    "WORKFLOW",
    "CHRON",
    "CHAT",
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
    "TemplateRenderError",
    # Types
    "Message",
    "MessageList",
    # Submodules
    "eval",
    # Metadata
    "__version__",
]
