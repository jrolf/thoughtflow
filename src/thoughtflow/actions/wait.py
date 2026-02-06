"""
WAIT action - wait until a condition is met.

Useful for polling, synchronization, and event-driven workflows.
"""

from __future__ import annotations

import time as time_module

from thoughtflow.action import ACTION


class WAIT(ACTION):
    """
    An action that waits until a condition is met or timeout occurs.
    
    WAIT enables polling patterns and synchronization in workflows.
    It repeatedly checks a condition at specified intervals.
    
    Args:
        name (str): Unique identifier for this action.
        condition (callable): Function (memory) -> bool that returns True
            when the wait should end.
        timeout (float): Maximum wait time in seconds (None = wait forever).
        poll_interval (float): Seconds between condition checks (default: 1.0).
        on_timeout (str): Behavior when timeout occurs:
            - "raise": Raise TimeoutError (default)
            - "continue": Continue workflow (return False)
            - "default": Return the 'default' value
        default (any): Value to return on timeout (if on_timeout="default").
        store_timeout_as (str): Memory variable to store timeout status.
    
    Example:
        >>> from thoughtflow.actions import WAIT
        >>> from thoughtflow import MEMORY
        
        # Wait for approval flag
        >>> wait = WAIT(
        ...     condition=lambda m: m.get_var("approved") == True,
        ...     timeout=300,  # 5 minutes
        ...     poll_interval=5
        ... )
        
        # Wait with graceful timeout
        >>> wait = WAIT(
        ...     condition=lambda m: m.get_var("data_ready"),
        ...     timeout=60,
        ...     on_timeout="continue"
        ... )
        
        # Wait for file to appear (using memory variable)
        >>> import os
        >>> wait = WAIT(
        ...     condition=lambda m: os.path.exists(m.get_var("expected_file")),
        ...     timeout=120,
        ...     poll_interval=2
        ... )
    """
    
    def __init__(
        self,
        name=None,
        condition=None,
        timeout=None,
        poll_interval=1.0,
        on_timeout="raise",
        default=None,
        store_timeout_as=None,
    ):
        """
        Initialize a WAIT action.
        
        Args:
            name: Optional name (defaults to "wait").
            condition: Condition function.
            timeout: Maximum wait time.
            poll_interval: Check interval.
            on_timeout: Timeout behavior.
            default: Default value on timeout.
            store_timeout_as: Variable for timeout status.
        """
        if condition is None:
            raise ValueError("WAIT requires 'condition' parameter")
        if not callable(condition):
            raise ValueError("WAIT 'condition' must be callable")
        
        self.condition = condition
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.on_timeout = on_timeout
        self.default = default
        self.store_timeout_as = store_timeout_as
        
        super().__init__(
            name=name or "wait",
            fn=self._execute,
            description="WAIT: Wait for condition"
        )
    
    def _execute(self, memory, **kwargs):
        """
        Execute the WAIT action.
        
        Args:
            memory: MEMORY instance.
            **kwargs: Can override parameters.
        
        Returns:
            dict: {
                "status": "completed" or "timeout",
                "waited_seconds": float,
                "checks": int
            }
        
        Raises:
            TimeoutError: If timeout and on_timeout="raise".
        """
        # Get parameters
        condition = kwargs.get('condition', self.condition)
        timeout = kwargs.get('timeout', self.timeout)
        poll_interval = kwargs.get('poll_interval', self.poll_interval)
        on_timeout = kwargs.get('on_timeout', self.on_timeout)
        default = kwargs.get('default', self.default)
        store_timeout_as = kwargs.get('store_timeout_as', self.store_timeout_as)
        
        start_time = time_module.time()
        checks = 0
        
        while True:
            checks += 1
            
            # Check condition
            try:
                if condition(memory):
                    elapsed = time_module.time() - start_time
                    
                    # Store timeout status if requested
                    if store_timeout_as and hasattr(memory, 'set_var'):
                        memory.set_var(store_timeout_as, False)
                    
                    return {
                        "status": "completed",
                        "waited_seconds": round(elapsed, 2),
                        "checks": checks,
                        "timed_out": False
                    }
            except Exception as e:
                # Log condition check errors but continue waiting
                if hasattr(memory, 'add_log'):
                    memory.add_log("WAIT condition error: {}".format(str(e)))
            
            # Check timeout
            if timeout is not None:
                elapsed = time_module.time() - start_time
                if elapsed >= timeout:
                    return self._handle_timeout(
                        memory, elapsed, checks, on_timeout, default, store_timeout_as
                    )
            
            # Wait before next check
            time_module.sleep(poll_interval)
    
    def _handle_timeout(self, memory, elapsed, checks, on_timeout, default, store_timeout_as):
        """
        Handle timeout based on on_timeout setting.
        
        Args:
            memory: MEMORY instance.
            elapsed: Time waited.
            checks: Number of condition checks.
            on_timeout: Timeout behavior.
            default: Default value.
            store_timeout_as: Variable for status.
        
        Returns:
            dict or default value.
        
        Raises:
            TimeoutError: If on_timeout="raise".
        """
        # Store timeout status if requested
        if store_timeout_as and hasattr(memory, 'set_var'):
            memory.set_var(store_timeout_as, True)
        
        result = {
            "status": "timeout",
            "waited_seconds": round(elapsed, 2),
            "checks": checks,
            "timed_out": True
        }
        
        if on_timeout == "raise":
            raise TimeoutError(
                "WAIT timed out after {:.1f} seconds ({} checks)".format(elapsed, checks)
            )
        
        if on_timeout == "default":
            return default
        
        # on_timeout == "continue"
        return result
    
    def to_dict(self):
        """
        Serialize WAIT to dictionary.
        
        Note: Condition function cannot be serialized.
        
        Returns:
            dict: Serializable representation.
        """
        base = super().to_dict()
        base["_class"] = "WAIT"
        base["timeout"] = self.timeout
        base["poll_interval"] = self.poll_interval
        base["on_timeout"] = self.on_timeout
        base["default"] = self.default
        base["store_timeout_as"] = self.store_timeout_as
        return base
    
    @classmethod
    def from_dict(cls, data, condition=None, **kwargs):
        """
        Reconstruct WAIT from dictionary.
        
        Args:
            data: Dictionary representation.
            condition: Required condition function.
            **kwargs: Ignored.
        
        Returns:
            WAIT: Reconstructed instance.
        """
        if condition is None:
            raise ValueError("WAIT.from_dict requires 'condition' function")
        
        wait = cls(
            name=data.get("name"),
            condition=condition,
            timeout=data.get("timeout"),
            poll_interval=data.get("poll_interval", 1.0),
            on_timeout=data.get("on_timeout", "raise"),
            default=data.get("default"),
            store_timeout_as=data.get("store_timeout_as")
        )
        if data.get("id"):
            wait.id = data["id"]
        return wait
    
    def __repr__(self):
        return "WAIT(name='{}', timeout={}, poll_interval={})".format(
            self.name, self.timeout, self.poll_interval
        )
    
    def __str__(self):
        if self.timeout:
            return "WAIT (timeout: {}s, poll: {}s)".format(self.timeout, self.poll_interval)
        return "WAIT (no timeout, poll: {}s)".format(self.poll_interval)
