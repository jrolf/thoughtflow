"""
Memory module for ThoughtFlow.

The MEMORY class is the event-sourced state container for managing events,
logs, messages, reflections, and variables in ThoughtFlow workflows.

Example:
    >>> from thoughtflow.memory import MEMORY
    >>>
    >>> memory = MEMORY()
    >>> memory.add_msg('user', 'Hello!', channel='webapp')
    >>> memory.add_msg('assistant', 'Hi there!', channel='webapp')
    >>> memory.set_var('session_id', 'abc123', desc='Current session')
    >>>
    >>> # Get messages
    >>> memory.get_msgs(include=['user'])
    >>>
    >>> # Prepare context for LLM
    >>> context = memory.prepare_context(format='openai')
    >>>
    >>> # Save/load state
    >>> memory.save('memory.pkl')
    >>> memory.to_json('memory.json')
"""

from __future__ import annotations

from thoughtflow.memory.base import MEMORY

__all__ = [
    "MEMORY",
]
