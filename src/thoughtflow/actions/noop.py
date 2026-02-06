"""
NOOP action - explicitly do nothing.

The simplest possible action, useful for:
- Placeholders during development
- Conditional skipping
- Testing and mocking
"""

from __future__ import annotations

from thoughtflow.action import ACTION
from thoughtflow._util import event_stamp


class NOOP(ACTION):
    """
    An action that explicitly does nothing.
    
    NOOP is the simplest action primitive. It logs its execution but performs
    no actual work. Useful for:
    - Placeholder during development
    - Conditional skip without if statements
    - Explicit "do nothing" for clarity
    - Testing and mocking
    
    Args:
        name (str): Unique identifier for this action.
        reason (str): Explanation for why nothing is being done (logged).
    
    Example:
        >>> from thoughtflow.actions import NOOP
        >>> from thoughtflow import MEMORY
        
        # Explicit placeholder
        >>> noop = NOOP(name="todo", reason="Feature not yet implemented")
        >>> memory = noop(MEMORY())
        
        # Conditional skip
        >>> action = real_action if enabled else NOOP(reason="Disabled")
        >>> memory = action(memory)
    """
    
    def __init__(self, name=None, reason=""):
        """
        Initialize a NOOP action.
        
        Args:
            name: Optional name (defaults to "noop").
            reason: Explanation for the no-op (logged).
        """
        self.reason = reason
        
        super().__init__(
            name=name or "noop",
            fn=self._execute,
            description="NOOP: {}".format(reason) if reason else "NOOP (do nothing)"
        )
    
    def _execute(self, memory, **kwargs):
        """
        Execute the NOOP action (do nothing, return reason).
        
        Args:
            memory: MEMORY instance (unused).
            **kwargs: Ignored.
        
        Returns:
            dict: {reason: str, status: "noop"}
        """
        return {
            "status": "noop",
            "reason": self.reason or "No operation performed"
        }
    
    def to_dict(self):
        """
        Serialize NOOP to dictionary.
        
        Returns:
            dict: Serializable representation.
        """
        base = super().to_dict()
        base["reason"] = self.reason
        base["_class"] = "NOOP"
        return base
    
    @classmethod
    def from_dict(cls, data, **kwargs):
        """
        Reconstruct NOOP from dictionary.
        
        Args:
            data: Dictionary representation.
            **kwargs: Ignored.
        
        Returns:
            NOOP: Reconstructed instance.
        """
        noop = cls(
            name=data.get("name"),
            reason=data.get("reason", "")
        )
        if data.get("id"):
            noop.id = data["id"]
        return noop
    
    def __repr__(self):
        return "NOOP(name='{}', reason='{}')".format(self.name, self.reason)
    
    def __str__(self):
        if self.reason:
            return "NOOP: {}".format(self.reason)
        return "NOOP"
