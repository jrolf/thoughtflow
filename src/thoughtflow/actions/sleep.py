"""
SLEEP action - pause execution for a specified duration.

Useful for rate limiting, backoff, and timing control.
"""

from __future__ import annotations

import time as time_module

from thoughtflow.action import ACTION
from thoughtflow.actions._substitution import substitute


class SLEEP(ACTION):
    """
    An action that pauses execution for a specified duration.
    
    SLEEP is useful for:
    - Rate limiting between API calls
    - Exponential backoff patterns
    - Deliberate delays in workflows
    - Timing control
    
    Args:
        name (str): Unique identifier for this action.
        duration (float|callable): Seconds to sleep. Can be:
            - float: Fixed duration
            - callable: Function (memory) -> float for dynamic duration
        reason (str): Explanation for the sleep (logged).
    
    Example:
        >>> from thoughtflow.actions import SLEEP
        >>> from thoughtflow import MEMORY
        
        # Fixed delay
        >>> sleep = SLEEP(duration=2.5, reason="Rate limit pause")
        >>> memory = sleep(MEMORY())
        
        # Dynamic delay from memory
        >>> sleep = SLEEP(
        ...     duration=lambda m: m.get_var("retry_delay", 1.0),
        ...     reason="Backoff delay"
        ... )
        
        # Exponential backoff
        >>> sleep = SLEEP(
        ...     duration=lambda m: 2 ** m.get_var("attempt", 0),
        ...     reason="Exponential backoff"
        ... )
    """
    
    def __init__(self, name=None, duration=1.0, reason=""):
        """
        Initialize a SLEEP action.
        
        Args:
            name: Optional name (defaults to "sleep").
            duration: Seconds to sleep (float or callable).
            reason: Explanation for the sleep.
        """
        self.duration = duration
        self.reason = reason
        
        super().__init__(
            name=name or "sleep",
            fn=self._execute,
            description="SLEEP: {}".format(reason) if reason else "SLEEP for {} seconds".format(duration)
        )
    
    def _execute(self, memory, **kwargs):
        """
        Execute the SLEEP action.
        
        Args:
            memory: MEMORY instance (for dynamic duration resolution).
            **kwargs: Can override 'duration'.
        
        Returns:
            dict: {duration: float, reason: str, status: "slept"}
        """
        # Get duration (from kwargs, or resolve from self.duration)
        duration = kwargs.get('duration', self.duration)
        
        # Resolve dynamic duration
        if callable(duration):
            duration = duration(memory)
        else:
            duration = substitute(duration, memory)
        
        # Ensure duration is a positive number
        try:
            duration = float(duration)
            if duration < 0:
                duration = 0
        except (TypeError, ValueError):
            duration = 0
        
        # Sleep
        if duration > 0:
            time_module.sleep(duration)
        
        return {
            "status": "slept",
            "duration": duration,
            "reason": self.reason or "Sleep completed"
        }
    
    def to_dict(self):
        """
        Serialize SLEEP to dictionary.
        
        Note: Callable durations cannot be serialized.
        
        Returns:
            dict: Serializable representation.
        """
        base = super().to_dict()
        base["_class"] = "SLEEP"
        base["reason"] = self.reason
        # Only serialize duration if it's not a callable
        if not callable(self.duration):
            base["duration"] = self.duration
        return base
    
    @classmethod
    def from_dict(cls, data, **kwargs):
        """
        Reconstruct SLEEP from dictionary.
        
        Args:
            data: Dictionary representation.
            **kwargs: Ignored.
        
        Returns:
            SLEEP: Reconstructed instance.
        """
        sleep = cls(
            name=data.get("name"),
            duration=data.get("duration", 1.0),
            reason=data.get("reason", "")
        )
        if data.get("id"):
            sleep.id = data["id"]
        return sleep
    
    def __repr__(self):
        dur = "<callable>" if callable(self.duration) else self.duration
        return "SLEEP(name='{}', duration={}, reason='{}')".format(
            self.name, dur, self.reason
        )
    
    def __str__(self):
        dur = "<dynamic>" if callable(self.duration) else "{}s".format(self.duration)
        if self.reason:
            return "SLEEP {}: {}".format(dur, self.reason)
        return "SLEEP {}".format(dur)
