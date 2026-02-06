"""
CALL action - call external functions with structured parameters.

A convenience wrapper for calling any function with memory-sourced parameters.
"""

from __future__ import annotations

import time as time_module

from thoughtflow.action import ACTION
from thoughtflow.actions._substitution import substitute


class CALL(ACTION):
    """
    An action that calls external functions with structured parameters.
    
    CALL provides a cleaner interface for invoking functions compared to
    the base ACTION class. It handles parameter substitution from memory
    and doesn't require the function to accept memory as first argument.
    
    Args:
        name (str): Unique identifier for this action.
        function (callable): Function to call.
        params (dict|callable): Parameters to pass to function. Can be:
            - dict: Static params with {variable} placeholders
            - callable: Function (memory) -> dict
        timeout (float): Execution timeout (uses threading).
        on_error (str): Error handling:
            - "log": Log error and continue (default)
            - "raise": Raise exception
            - "ignore": Silently continue
        store_as (str): Memory variable for result (default: "{name}_result").
    
    Example:
        >>> from thoughtflow.actions import CALL
        >>> from thoughtflow import MEMORY
        
        # Simple function call
        >>> def greet(name):
        ...     return "Hello, {}!".format(name)
        >>> call = CALL(
        ...     function=greet,
        ...     params={"name": "Alice"}
        ... )
        >>> memory = call(MEMORY())
        >>> memory.get_var("call_result")
        'Hello, Alice!'
        
        # With memory variables
        >>> def process(data, multiplier=1):
        ...     return data * multiplier
        >>> call = CALL(
        ...     function=process,
        ...     params={"data": "{input_data}", "multiplier": 2}
        ... )
        
        # Dynamic parameters
        >>> call = CALL(
        ...     function=external_api.query,
        ...     params=lambda m: {
        ...         "query": m.get_var("user_query"),
        ...         "limit": m.get_var("max_results", 10)
        ...     }
        ... )
        
        # With timeout
        >>> call = CALL(
        ...     function=slow_api_call,
        ...     params={"url": "{target_url}"},
        ...     timeout=30
        ... )
    
    Difference from base ACTION:
        Base ACTION requires functions that accept (memory, **kwargs).
        CALL wraps any function and handles parameter resolution separately.
        
        ```python
        # Base ACTION requires:
        def my_fn(memory, query, limit):
            return api.search(query, limit)
        action = ACTION(name="x", fn=my_fn)
        
        # CALL wraps any function:
        call = CALL(function=api.search, params={"query": "x", "limit": 10})
        ```
    """
    
    def __init__(
        self,
        name=None,
        function=None,
        params=None,
        timeout=None,
        on_error="log",
        store_as=None,
    ):
        """
        Initialize a CALL action.
        
        Args:
            name: Optional name (defaults to "call").
            function: Function to call.
            params: Parameters to pass.
            timeout: Execution timeout.
            on_error: Error behavior.
            store_as: Memory variable name.
        """
        if function is None:
            raise ValueError("CALL requires 'function' parameter")
        if not callable(function):
            raise ValueError("CALL 'function' must be callable")
        
        self.function = function
        self.params = params or {}
        self.timeout = timeout
        self.on_error = on_error
        
        # Get function name for defaults
        fn_name = getattr(function, '__name__', 'call')
        name = name or fn_name
        
        super().__init__(
            name=name,
            fn=self._execute,
            result_key=store_as or "{}_result".format(name),
            description="CALL: {}".format(fn_name)
        )
    
    def _execute(self, memory, **kwargs):
        """
        Execute the CALL action.
        
        Args:
            memory: MEMORY instance.
            **kwargs: Additional parameters (merged with self.params).
        
        Returns:
            Function result.
        """
        # Get parameters
        params = kwargs.get('params', self.params)
        timeout = kwargs.get('timeout', self.timeout)
        on_error = kwargs.get('on_error', self.on_error)
        
        # Resolve parameters
        resolved_params = substitute(params, memory) or {}
        
        # Merge with kwargs (excluding our control parameters)
        for k, v in kwargs.items():
            if k not in ('params', 'timeout', 'on_error'):
                resolved_params[k] = substitute(v, memory)
        
        # Execute function
        start_time = time_module.time()
        
        try:
            if timeout:
                result = self._call_with_timeout(resolved_params, timeout)
            else:
                result = self.function(**resolved_params)
            
            return result
            
        except Exception as e:
            return self._handle_error(e, on_error, memory)
    
    def _call_with_timeout(self, params, timeout):
        """
        Call function with timeout using threading.
        
        Args:
            params: Function parameters.
            timeout: Timeout in seconds.
        
        Returns:
            Function result.
        
        Raises:
            TimeoutError: If function doesn't complete in time.
        """
        import threading
        
        result = [None]
        error = [None]
        
        def run_function():
            try:
                result[0] = self.function(**params)
            except Exception as e:
                error[0] = e
        
        thread = threading.Thread(target=run_function)
        thread.daemon = True
        thread.start()
        thread.join(timeout=timeout)
        
        if thread.is_alive():
            raise TimeoutError("CALL timed out after {} seconds".format(timeout))
        
        if error[0]:
            raise error[0]
        
        return result[0]
    
    def _handle_error(self, exception, on_error, memory):
        """
        Handle function call error.
        
        Args:
            exception: Exception that occurred.
            on_error: Error behavior.
            memory: MEMORY instance.
        
        Returns:
            Error dict if not raising.
        
        Raises:
            Exception: If on_error="raise".
        """
        if on_error == "raise":
            raise exception
        
        error_result = {
            "error": str(exception),
            "error_type": type(exception).__name__,
            "success": False
        }
        
        if on_error == "log":
            if hasattr(memory, 'add_log'):
                memory.add_log("CALL failed: {}".format(str(exception)))
        
        # on_error == "ignore" - just return the error dict
        return error_result
    
    def to_dict(self):
        """
        Serialize CALL to dictionary.
        
        Note: The function itself cannot be serialized.
        
        Returns:
            dict: Serializable representation.
        """
        base = super().to_dict()
        base["_class"] = "CALL"
        base["function_name"] = getattr(self.function, '__name__', '<unknown>')
        base["timeout"] = self.timeout
        base["on_error"] = self.on_error
        if not callable(self.params):
            base["params"] = self.params
        return base
    
    @classmethod
    def from_dict(cls, data, function=None, fn_registry=None, **kwargs):
        """
        Reconstruct CALL from dictionary.
        
        Args:
            data: Dictionary representation.
            function: Function to use.
            fn_registry: Dict mapping function names to functions.
            **kwargs: Ignored.
        
        Returns:
            CALL: Reconstructed instance.
        """
        # Get function from parameter or registry
        fn = function
        if fn is None and fn_registry:
            fn_name = data.get("function_name")
            fn = fn_registry.get(fn_name)
        
        if fn is None:
            raise ValueError(
                "CALL.from_dict requires 'function' parameter or "
                "'fn_registry' with function '{}'".format(data.get("function_name"))
            )
        
        call = cls(
            name=data.get("name"),
            function=fn,
            params=data.get("params"),
            timeout=data.get("timeout"),
            on_error=data.get("on_error", "log"),
            store_as=data.get("result_key")
        )
        if data.get("id"):
            call.id = data["id"]
        return call
    
    def __repr__(self):
        fn_name = getattr(self.function, '__name__', '<callable>')
        return "CALL(name='{}', function={}, params={})".format(
            self.name, fn_name, "<callable>" if callable(self.params) else self.params
        )
    
    def __str__(self):
        fn_name = getattr(self.function, '__name__', '<function>')
        return "CALL: {}()".format(fn_name)
