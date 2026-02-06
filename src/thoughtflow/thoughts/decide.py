"""
DECIDE class for ThoughtFlow.

A specialized THOUGHT subclass for constrained decision-making.
"""

from __future__ import annotations

from thoughtflow.thought import THOUGHT


class DECIDE(THOUGHT):
    """
    A decision step that constrains LLM output to a finite set of choices.
    
    DECIDE is a specialized THOUGHT that presents a set of choices to an LLM
    and ensures the response matches one of the allowed options. It includes
    automatic retry with choice-specific prompts when the LLM returns an
    invalid selection.
    
    Inherits from THOUGHT and adds:
        - Automatic choice presentation in prompt
        - Smart parsing to extract selection from LLM response
        - Validation against allowed choices
        - Choice-specific repair prompts on retry
    
    Args:
        name (str): Unique identifier for this decision.
        llm (LLM): LLM instance for execution.
        choices (list|dict): The allowed choices. Can be:
            - list: ["approve", "reject", "escalate"]
            - dict: {"approve": "Accept request", "reject": "Deny request", ...}
              When a dict is provided, keys are the choices and values are
              descriptions shown to the LLM.
        prompt (str): Prompt template with {variable} placeholders.
        default (str): Default choice if all retries fail (optional).
        case_sensitive (bool): Whether matching is case-sensitive (default: False).
        max_retries (int): Maximum retry attempts (default: 5).
        **kwargs: Additional THOUGHT parameters.
    
    Example:
        >>> from thoughtflow import DECIDE, MEMORY, LLM
        
        # Simple list of choices
        >>> decide = DECIDE(
        ...     name="sentiment",
        ...     llm=llm,
        ...     choices=["positive", "negative", "neutral"],
        ...     prompt="Classify the sentiment of: {text}"
        ... )
        
        # Dict with descriptions (descriptions shown to LLM)
        >>> decide = DECIDE(
        ...     name="action",
        ...     llm=llm,
        ...     choices={
        ...         "approve": "Accept and proceed with the request",
        ...         "reject": "Deny the request",
        ...         "escalate": "Send to human reviewer"
        ...     },
        ...     prompt="Decide how to handle: {request}"
        ... )
        
        >>> mem = decide(mem)
        >>> result = mem.get_var("action_result")  # "approve", "reject", or "escalate"
    """
    
    def __init__(self, name=None, llm=None, prompt=None, choices=None, **kwargs):
        """
        Initialize a DECIDE instance.
        
        Args:
            name: Name of the decision.
            llm: LLM interface.
            prompt: Prompt template.
            choices: List or dict of allowed choices.
            **kwargs: Additional configuration.
        """
        # Validate and normalize choices
        if choices is None:
            raise ValueError("DECIDE requires 'choices' parameter")
        
        if isinstance(choices, dict):
            self._choices_list = list(choices.keys())
            self._choices_descriptions = choices
        elif isinstance(choices, (list, tuple)):
            self._choices_list = list(choices)
            self._choices_descriptions = {}
        else:
            raise ValueError("'choices' must be a list or dict, got: {}".format(type(choices).__name__))
        
        if not self._choices_list:
            raise ValueError("'choices' cannot be empty")
        
        # DECIDE-specific attributes
        self.choices = choices  # Store original for serialization
        self.default = kwargs.pop('default', None)
        self.case_sensitive = kwargs.pop('case_sensitive', False)
        
        # Set default max_retries to 5 for DECIDE
        if 'max_retries' not in kwargs:
            kwargs['max_retries'] = 5
        
        # Force operation to llm_call
        kwargs['operation'] = 'llm_call'
        
        super().__init__(name=name, llm=llm, prompt=prompt, **kwargs)
    
    def build_prompt(self, memory, context_vars=None):
        """
        Build prompt with choices appended.
        
        Args:
            memory: MEMORY object providing context.
            context_vars: Optional context variables.
        
        Returns:
            str: Prompt with choices section appended.
        """
        base_prompt = super().build_prompt(memory, context_vars)
        choices_section = self._format_choices()
        instruction = "\n\nRespond with only your choice, nothing else."
        return base_prompt + "\n\n" + choices_section + instruction
    
    def _format_choices(self):
        """
        Format choices for inclusion in prompt.
        Format is determined by whether choices was provided as list or dict.
        
        Returns:
            str: Formatted choices section.
        """
        if self._choices_descriptions:
            # Dict format: show descriptions
            lines = ["- {}: {}".format(choice, desc) for choice, desc in self._choices_descriptions.items()]
        else:
            # List format: simple bullet list
            lines = ["- {}".format(choice) for choice in self._choices_list]
        
        return "Choose one of:\n" + "\n".join(lines)
    
    def parse_response(self, response):
        """
        Extract the chosen option from LLM response.
        
        Attempts matching in order:
        1. Exact match (after normalization)
        2. Choice found within response text
        
        Args:
            response: Raw LLM response string.
        
        Returns:
            str: The matched choice, or raw response if no match found.
        """
        text = response.strip()
        
        def normalize(s):
            return s.lower().strip() if not self.case_sensitive else s.strip()
        
        normalized_text = normalize(text)
        
        # Try exact match against choices
        for choice in self._choices_list:
            if normalize(choice) == normalized_text:
                return choice
        
        # Try to find choice embedded in response (longest match first to avoid partial matches)
        sorted_choices = sorted(self._choices_list, key=len, reverse=True)
        for choice in sorted_choices:
            if normalize(choice) in normalized_text:
                return choice
        
        # No match found - return raw for validation to catch
        return text
    
    def validate(self, parsed_result):
        """
        Validate that result is an allowed choice.
        
        Args:
            parsed_result: The parsed response.
        
        Returns:
            tuple: (is_valid, reason_string)
        """
        def normalize(s):
            return s.lower().strip() if not self.case_sensitive else s.strip()
        
        normalized = normalize(str(parsed_result))
        for choice in self._choices_list:
            if normalize(choice) == normalized:
                return True, ""
        
        return False, "Not a valid choice. Must be one of: {}".format(self._choices_list)
    
    def _build_repair_suffix(self, why):
        """
        Build choice-specific repair prompt for retries.
        
        Args:
            why: Reason the previous attempt failed.
        
        Returns:
            str: Repair suffix to append to prompt.
        """
        choices_str = ", ".join(self._choices_list)
        return "\n(Respond with exactly one of: {}. No other text.)".format(choices_str)
    
    def update_memory(self, memory, result):
        """
        Store result in memory, using default if result is None.
        
        Args:
            memory: MEMORY object.
            result: The decision result (or None if failed).
        
        Returns:
            MEMORY: Updated memory object.
        """
        if result is None and self.default is not None:
            result = self.default
        return super().update_memory(memory, result)
    
    def to_dict(self):
        """
        Return a serializable dictionary representation.
        
        Returns:
            dict: Serializable representation including DECIDE-specific fields.
        """
        data = super().to_dict()
        data.update({
            'choices': self.choices,
            'default': self.default,
            'case_sensitive': self.case_sensitive,
            '_class': 'DECIDE',
        })
        return data
    
    @classmethod
    def from_dict(cls, data, llm=None, **kwargs):
        """
        Reconstruct a DECIDE from a dictionary representation.
        
        Args:
            data: Dictionary representation.
            llm: LLM instance to use.
            **kwargs: Additional arguments.
        
        Returns:
            DECIDE: Reconstructed instance.
        """
        # Get config but remove keys we're setting explicitly to avoid duplicates
        config = data.get('config', {}).copy()
        for key in ['max_retries', 'default', 'case_sensitive']:
            config.pop(key, None)
        
        return cls(
            name=data.get('name'),
            llm=llm,
            prompt=data.get('prompt'),
            choices=data.get('choices'),
            default=data.get('default'),
            case_sensitive=data.get('case_sensitive', False),
            max_retries=data.get('max_retries', 5),
            **config
        )
    
    def __repr__(self):
        """Return detailed string representation."""
        return ("DECIDE(name='{}', choices={}, "
                "max_retries={}, default={})".format(
                    self.name, self._choices_list, self.max_retries, self.default))
    
    def __str__(self):
        """Return human-readable string representation."""
        return "Decide: {} (choices: {})".format(
            self.name or 'unnamed', 
            ", ".join(self._choices_list)
        )
