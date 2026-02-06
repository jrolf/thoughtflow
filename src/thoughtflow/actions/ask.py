"""
ASK action - prompt user for input.

Provides human-in-the-loop interaction for agents.
"""

from __future__ import annotations

from thoughtflow.action import ACTION
from thoughtflow.actions._substitution import substitute


class ASK(ACTION):
    """
    An action that prompts the user for input and waits for a response.
    
    ASK enables human-in-the-loop interactions, allowing agents to
    request information from users during workflow execution.
    
    Args:
        name (str): Unique identifier for this action.
        prompt (str|callable): Question to display. Supports:
            - str: Static text with {variable} placeholders
            - callable: Function (memory) -> str
        store_as (str): Memory variable to store the response.
        timeout (float): Seconds to wait for input (None = wait forever).
        default (any): Value to use if timeout or empty input.
        validator (callable): Function (input) -> bool to validate input.
        retry_prompt (str): Message shown on validation failure.
        max_retries (int): Maximum validation retry attempts (default: 3).
    
    Example:
        >>> from thoughtflow.actions import ASK
        >>> from thoughtflow import MEMORY
        
        # Simple question
        >>> ask = ASK(
        ...     prompt="What is your name?",
        ...     store_as="user_name"
        ... )
        >>> memory = ask(MEMORY())
        
        # With validation
        >>> ask = ASK(
        ...     prompt="Enter a number between 1-10:",
        ...     store_as="choice",
        ...     validator=lambda x: x.isdigit() and 1 <= int(x) <= 10,
        ...     retry_prompt="Invalid! Please enter a number 1-10:"
        ... )
        
        # With timeout and default
        >>> ask = ASK(
        ...     prompt="Continue? (y/n):",
        ...     store_as="continue",
        ...     timeout=30,
        ...     default="y"
        ... )
        
        # Dynamic prompt
        >>> ask = ASK(
        ...     prompt=lambda m: "Hello {}! What would you like to do?".format(
        ...         m.get_var("user_name", "there")
        ...     ),
        ...     store_as="user_intent"
        ... )
    """
    
    def __init__(
        self,
        name=None,
        prompt="",
        store_as=None,
        timeout=None,
        default=None,
        validator=None,
        retry_prompt="Invalid input. Please try again:",
        max_retries=3,
    ):
        """
        Initialize an ASK action.
        
        Args:
            name: Optional name (defaults to "ask").
            prompt: Question to display.
            store_as: Memory variable for response.
            timeout: Input timeout (seconds).
            default: Default value.
            validator: Validation function.
            retry_prompt: Message on validation failure.
            max_retries: Max validation retries.
        """
        if store_as is None:
            raise ValueError("ASK requires 'store_as' parameter")
        
        self.prompt = prompt
        self.store_as = store_as
        self.timeout = timeout
        self.default = default
        self.validator = validator
        self.retry_prompt = retry_prompt
        self.max_retries = max_retries
        
        super().__init__(
            name=name or "ask",
            fn=self._execute,
            result_key=store_as,
            description="ASK: Prompt user for input"
        )
    
    def _execute(self, memory, **kwargs):
        """
        Execute the ASK action.
        
        Args:
            memory: MEMORY instance.
            **kwargs: Can override parameters.
        
        Returns:
            str: User's input (or default).
        """
        # Get parameters
        prompt = kwargs.get('prompt', self.prompt)
        timeout = kwargs.get('timeout', self.timeout)
        default = kwargs.get('default', self.default)
        validator = kwargs.get('validator', self.validator)
        retry_prompt = kwargs.get('retry_prompt', self.retry_prompt)
        max_retries = kwargs.get('max_retries', self.max_retries)
        
        # Resolve prompt
        prompt_text = substitute(prompt, memory)
        if prompt_text is None:
            prompt_text = ""
        prompt_text = str(prompt_text)
        
        # Get input with optional timeout
        response = self._get_input(prompt_text, timeout, default)
        
        # Validate if validator provided
        if validator and response is not None:
            retries = 0
            while not validator(response) and retries < max_retries:
                retries += 1
                retry_text = substitute(retry_prompt, memory)
                response = self._get_input(str(retry_text), timeout, default)
                if response is None:
                    break
        
        # Use default if response is empty or None
        if response is None or response == '':
            response = default
        
        # Also add as user message to memory
        if response and hasattr(memory, 'add_msg'):
            memory.add_msg("user", str(response), channel="cli")
        
        return response
    
    def _get_input(self, prompt_text, timeout, default):
        """
        Get input from user with optional timeout.
        
        Args:
            prompt_text: Prompt to display.
            timeout: Timeout in seconds (None = no timeout).
            default: Default value on timeout.
        
        Returns:
            str: User input or default.
        """
        if timeout is None:
            # Simple blocking input
            try:
                return input(prompt_text + " ")
            except (EOFError, KeyboardInterrupt):
                return default
        
        # Timeout handling using threading (standard library)
        import threading
        
        result = [default]
        
        def get_input_thread():
            try:
                result[0] = input(prompt_text + " ")
            except (EOFError, KeyboardInterrupt):
                pass
        
        thread = threading.Thread(target=get_input_thread)
        thread.daemon = True
        thread.start()
        thread.join(timeout=timeout)
        
        return result[0]
    
    def to_dict(self):
        """
        Serialize ASK to dictionary.
        
        Note: Validator function cannot be serialized.
        
        Returns:
            dict: Serializable representation.
        """
        base = super().to_dict()
        base["_class"] = "ASK"
        base["store_as"] = self.store_as
        base["timeout"] = self.timeout
        base["default"] = self.default
        base["retry_prompt"] = self.retry_prompt
        base["max_retries"] = self.max_retries
        if not callable(self.prompt):
            base["prompt"] = self.prompt
        return base
    
    @classmethod
    def from_dict(cls, data, validator=None, **kwargs):
        """
        Reconstruct ASK from dictionary.
        
        Args:
            data: Dictionary representation.
            validator: Optional validator function.
            **kwargs: Ignored.
        
        Returns:
            ASK: Reconstructed instance.
        """
        ask = cls(
            name=data.get("name"),
            prompt=data.get("prompt", ""),
            store_as=data.get("store_as") or data.get("result_key"),
            timeout=data.get("timeout"),
            default=data.get("default"),
            validator=validator,
            retry_prompt=data.get("retry_prompt", "Invalid input. Please try again:"),
            max_retries=data.get("max_retries", 3)
        )
        if data.get("id"):
            ask.id = data["id"]
        return ask
    
    def __repr__(self):
        prompt = "<callable>" if callable(self.prompt) else repr(self.prompt[:30] + "..." if len(str(self.prompt)) > 30 else self.prompt)
        return "ASK(name='{}', prompt={}, store_as='{}')".format(
            self.name, prompt, self.store_as
        )
    
    def __str__(self):
        if callable(self.prompt):
            return "ASK <dynamic prompt> -> {}".format(self.store_as)
        preview = str(self.prompt)[:30]
        if len(str(self.prompt)) > 30:
            preview += "..."
        return "ASK: {} -> {}".format(preview, self.store_as)
