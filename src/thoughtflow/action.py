"""
ACTION class for ThoughtFlow.

The ACTION class encapsulates an external or internal operation that can be invoked 
within a Thoughtflow agent workflow.
"""

from __future__ import annotations

import json

from thoughtflow._util import event_stamp


class ACTION:
    """
    The ACTION class encapsulates an external or internal operation that can be invoked within a Thoughtflow agent.
    It is designed to represent a single, named action (such as a tool call, API request, or function) whose result
    is stored in the agent's state for later inspection, branching, or retry.
    
    An ACTION represents a discrete, named operation (function, API call, tool invocation) that can be defined once
    and executed multiple times with different parameters. When executed, the ACTION handles logging, error management,
    and result storage in a consistent way.
    
    Attributes:
        name (str): Identifier for this action, used for logging and storing results.
        id (str): Unique identifier for this action instance (event_stamp).
        fn (callable): The function to execute when this action is called.
        config (dict): Default configuration parameters that will be passed to the function.
        result_key (str): Key where results are stored in memory (defaults to "{name}_result").
        description (str): Human-readable description of what this action does.
        last_result (Any): The most recent result from executing this action.
        last_error (Exception): The most recent error from executing this action, if any.
        execution_count (int): Number of times this action has been executed.
        execution_history (list): Full execution history with timing and success/error tracking.
    
    Methods:
        __init__(name, fn, config=None, result_key=None, description=None):
            Initializes an ACTION with a name, function, and optional configuration.
            
        __call__(memory, **kwargs):
            Executes the action function with the memory object and any override parameters.
            The function receives (memory, **merged_kwargs) where merged_kwargs combines
            self.config with any call-specific kwargs.
            
            Returns the memory object with results stored via set_var.
            Logs execution details with JSON-formatted event data.
            Tracks execution timing and history.
            
            Handles exceptions during execution by logging them rather than raising them,
            allowing the workflow to continue and decide how to handle failures.
            
        get_last_result():
            Returns the most recent result from executing this action.
            
        was_successful():
            Returns True if the last execution was successful, False otherwise.
            
        reset_stats():
            Resets execution statistics (count, last_result, last_error, execution_history).
            
        copy():
            Returns a copy of this ACTION with a new ID and reset statistics.
            
        to_dict():
            Returns a serializable dictionary representation of this action.
            
        from_dict(cls, data, fn_registry):
            Class method to reconstruct an ACTION from a dictionary representation.
    
    Example Usage:
        # Define a web search action
        def search_web(memory, query, max_results=3):
            # Implementation of web search
            results = web_api.search(query, limit=max_results)
            return {"status": "success", "hits": results}
            
        search_action = ACTION(
            name="web_search",
            fn=search_web,
            config={"max_results": 5},
            description="Searches the web for information"
        )
        
        # Execute the action
        memory = MEMORY()
        memory = search_action(memory, query="thoughtflow framework")
        
        # Access results
        result = memory.get_var("web_search_result")
        
        # Check execution history
        print(search_action.execution_history[-1]['duration_ms'])  # Execution time
        print(search_action.execution_history[-1]['success'])      # True/False
    
    Design Principles:
        1. Explicit and inspectable operations with consistent logging
        2. Predictable result storage via memory.set_var
        3. Error handling that doesn't interrupt workflow execution
        4. Composability with other Thoughtflow components (MEMORY, THOUGHT)
        5. Serialization support for reproducibility
        6. Full execution history with timing for debugging and optimization
    """
    
    def __init__(self, name, fn, config=None, result_key=None, description=None):
        """
        Initialize an ACTION with a name, function, and optional configuration.
        
        Args:
            name (str): Identifier for this action, used for logging and result storage.
            fn (callable): The function to execute when this action is called.
            config (dict, optional): Default configuration parameters passed to the function.
            result_key (str, optional): Key where results are stored in memory (defaults to "{name}_result").
            description (str, optional): Human-readable description of what this action does.
        """
        self.name = name
        self.id = event_stamp()  # Unique identifier for this action instance
        self.fn = fn
        self.config = config or {}
        self.result_key = result_key or "{}_result".format(name)
        self.description = description or "Action: {}".format(name)
        self.last_result = None
        self.last_error = None
        self.execution_count = 0
        self.execution_history = []  # Full execution tracking with timing
    
    def __call__(self, memory, **kwargs):
        """
        Execute the action function with the memory object and any override parameters.
        
        Args:
            memory (MEMORY): The memory object to update with results.
            **kwargs: Parameters that override the default config for this execution.
            
        Returns:
            MEMORY: The updated memory object with results stored in memory.vars[result_key].
            
        Note:
            The function receives (memory, **merged_kwargs) where merged_kwargs combines
            self.config with any call-specific kwargs.
            
            Exceptions during execution are logged rather than raised, allowing the
            workflow to continue and decide how to handle failures.
        """
        import time as time_module
        
        start_time = time_module.time()
        
        # Merge default config with call-specific kwargs
        merged_kwargs = {**self.config, **kwargs}
        self.execution_count += 1
        
        try:
            # Execute the function
            result = self.fn(memory, **merged_kwargs)
            self.last_result = result
            self.last_error = None
            
            # Calculate execution duration
            duration_ms = (time_module.time() - start_time) * 1000
            
            # Store result in memory using set_var (correct API)
            if hasattr(memory, "set_var") and callable(getattr(memory, "set_var", None)):
                memory.set_var(self.result_key, result, desc="Result of action: {}".format(self.name))
            
            # Build execution event for logging (JSON format like THOUGHT)
            execution_event = {
                'action_name': self.name,
                'action_id': self.id,
                'status': 'success',
                'duration_ms': round(duration_ms, 2),
                'result_key': self.result_key
            }
            
            # Log successful execution (single message with JSON, no invalid details param)
            if hasattr(memory, "add_log") and callable(getattr(memory, "add_log", None)):
                memory.add_log("Action execution complete: " + json.dumps(execution_event))
            
            # Track execution history
            self.execution_history.append({
                'stamp': event_stamp(),
                'memory_id': getattr(memory, 'id', None),
                'duration_ms': duration_ms,
                'success': True,
                'error': None
            })
                
        except Exception as e:
            # Handle and log exceptions
            self.last_error = e
            
            # Calculate execution duration
            duration_ms = (time_module.time() - start_time) * 1000
            
            # Build error event for logging
            error_event = {
                'action_name': self.name,
                'action_id': self.id,
                'status': 'error',
                'error': str(e),
                'duration_ms': round(duration_ms, 2),
                'result_key': self.result_key
            }
            
            # Log failed execution (single message with JSON)
            if hasattr(memory, "add_log") and callable(getattr(memory, "add_log", None)):
                memory.add_log("Action execution failed: " + json.dumps(error_event))
            
            # Store error info in memory using set_var
            if hasattr(memory, "set_var") and callable(getattr(memory, "set_var", None)):
                memory.set_var(self.result_key, error_event, desc="Error in action: {}".format(self.name))
            
            # Track execution history
            self.execution_history.append({
                'stamp': event_stamp(),
                'memory_id': getattr(memory, 'id', None),
                'duration_ms': duration_ms,
                'success': False,
                'error': str(e)
            })
        
        return memory
    
    def get_last_result(self):
        """
        Returns the most recent result from executing this action.
        
        Returns:
            Any: The last result or None if the action hasn't been executed.
        """
        return self.last_result
    
    def was_successful(self):
        """
        Returns True if the last execution was successful, False otherwise.
        
        Returns:
            bool: True if the last execution completed without errors, False otherwise.
        """
        return self.last_error is None and self.execution_count > 0
    
    def reset_stats(self):
        """
        Resets execution statistics (count, last_result, last_error, execution_history).
        
        Returns:
            ACTION: Self for method chaining.
        """
        self.execution_count = 0
        self.last_result = None
        self.last_error = None
        self.execution_history = []
        return self
    
    def copy(self):
        """
        Return a copy of this ACTION with a new ID.
        
        The function reference is shared (same callable), but config is copied.
        Execution statistics are reset in the copy.
        
        Returns:
            ACTION: A new ACTION instance with copied attributes and new ID.
        """
        new_action = ACTION(
            name=self.name,
            fn=self.fn,  # Same function reference
            config=self.config.copy() if self.config else None,
            result_key=self.result_key,
            description=self.description
        )
        # New ID is already assigned in __init__, no need to set it
        return new_action
    
    def to_dict(self):
        """
        Returns a serializable dictionary representation of this action.
        
        Note: The function itself cannot be serialized, so it's represented by name.
        When deserializing, a function registry must be provided.
        
        Returns:
            dict: Serializable representation of this action.
        """
        return {
            "name": self.name,
            "id": self.id,
            "fn_name": self.fn.__name__,
            "config": self.config,
            "result_key": self.result_key,
            "description": self.description,
            "execution_count": self.execution_count,
            "execution_history": self.execution_history
        }
    
    @classmethod
    def from_dict(cls, data, fn_registry):
        """
        Reconstruct an ACTION from a dictionary representation.
        
        Args:
            data (dict): Dictionary representation of an ACTION.
            fn_registry (dict): Dictionary mapping function names to function objects.
            
        Returns:
            ACTION: Reconstructed ACTION object.
            
        Raises:
            KeyError: If the function name is not found in the registry.
        """
        if data["fn_name"] not in fn_registry:
            raise KeyError("Function '{}' not found in registry".format(data['fn_name']))
            
        action = cls(
            name=data["name"],
            fn=fn_registry[data["fn_name"]],
            config=data["config"],
            result_key=data["result_key"],
            description=data["description"]
        )
        # Restore ID if provided, otherwise keep the new one from __init__
        if data.get("id"):
            action.id = data["id"]
        action.execution_count = data.get("execution_count", 0)
        action.execution_history = data.get("execution_history", [])
        return action
    
    def __str__(self):
        """
        Returns a string representation of this action.
        
        Returns:
            str: String representation.
        """
        return "ACTION({}, desc='{}', executions={})".format(self.name, self.description, self.execution_count)
    
    def __repr__(self):
        """
        Returns a detailed string representation of this action.
        
        Returns:
            str: Detailed string representation.
        """
        return ("ACTION(name='{}', fn={}, "
                "config={}, result_key='{}', "
                "description='{}', execution_count={})".format(
                    self.name, self.fn.__name__, self.config, 
                    self.result_key, self.description, self.execution_count))


### ACTION CLASS TESTS

ActionClassTests = """
# --- ACTION Class Tests ---


"""
