"""
DEPRECATED: Use THOUGHT class instead.

The Agent class has been replaced by the THOUGHT class which provides
a more powerful and flexible interface for LLM interactions.

Example migration:
    # Old (deprecated):
    agent = Agent(adapter)
    response = agent.call(messages)
    
    # New:
    from thoughtflow import THOUGHT, MEMORY, LLM
    
    llm = LLM("openai:gpt-4o", key="your-api-key")
    thought = THOUGHT(name="my_thought", llm=llm, prompt="...")
    memory = MEMORY()
    memory = thought(memory)
    result = memory.get_var("my_thought_result")
"""

from __future__ import annotations

import warnings


class Agent:
    """
    DEPRECATED: Use THOUGHT class instead.
    
    The Agent class has been deprecated in favor of the THOUGHT class,
    which provides a more powerful and flexible interface for LLM interactions.
    """
    
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "Agent is deprecated. Use THOUGHT instead. "
            "See the migration guide in the module docstring.",
            DeprecationWarning,
            stacklevel=2
        )
        raise NotImplementedError(
            "Agent is deprecated. Use THOUGHT instead. "
            "Example: thought = THOUGHT(name='my_thought', llm=llm, prompt='...')"
        )


class TracedAgent:
    """
    DEPRECATED: Use THOUGHT class instead.
    
    The TracedAgent class has been deprecated. THOUGHT provides built-in
    execution history tracking and tracing capabilities.
    """
    
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "TracedAgent is deprecated. Use THOUGHT instead. "
            "THOUGHT provides built-in execution history tracking.",
            DeprecationWarning,
            stacklevel=2
        )
        raise NotImplementedError(
            "TracedAgent is deprecated. Use THOUGHT instead. "
            "THOUGHT provides built-in execution history tracking via execution_history."
        )
