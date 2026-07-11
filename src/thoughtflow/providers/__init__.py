"""
Native provider convenience classes for ThoughtFlow.

These thin subclasses inherit the unified param pipeline (llm_params) and
prompt caching adapters (llm_cache) from the base LLM class. They only add
production-safe defaults via setdefault — they do not reimplement wire logic.

Authors may always use LLM(model_id="groq:...") directly; native classes are
shortcuts for tier maps and harness construction.
"""

from thoughtflow.providers.groq import GroqLLM
from thoughtflow.providers.cerebras import CerebrasLLM
from thoughtflow.providers.openrouter import OpenRouterLLM

__all__ = ["GroqLLM", "CerebrasLLM", "OpenRouterLLM"]
