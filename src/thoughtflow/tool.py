"""
TOOL class for ThoughtFlow.

A TOOL wraps a callable and adds a schema layer that LLM providers use for
function-calling / tool-use. The key boundary between TOOL and ACTION:

- ACTION is imperative: your code calls it directly.
- TOOL is declarative: the LLM selects it via a schema, and the agent loop
  executes it on the LLM's behalf.

A TOOL can wrap an ACTION (via .from_action()), a plain function, or any
other callable. It adds a name, description, and parameter schema that can
be formatted into the JSON structure expected by LLM provider tool-calling APIs.
"""

from __future__ import annotations

import time as time_module

from thoughtflow._util import event_stamp


class TOOL:
    """
    An LLM-selectable capability with a schema.

    TOOL wraps a callable and attaches metadata (name, description, parameter
    schema) so that an LLM can discover it, reason about when to use it, and
    generate the correct arguments. The framework then executes the tool and
    feeds the result back to the LLM.

    The parameter schema uses a JSON-Schema-compatible dict format. This is the
    same format that OpenAI, Anthropic, and other providers expect in their
    function-calling APIs.

    Attributes:
        name (str): Unique identifier for this tool. Sent to the LLM as the
            function name.
        description (str): Human-readable explanation of what this tool does.
            Sent to the LLM to help it decide when to use the tool.
        parameters (dict): JSON Schema dict describing the tool's input
            parameters. Example: {"type": "object", "properties": {...}}.
        fn (callable): The function to execute when the tool is called.
        id (str): Unique identifier for this tool instance (event_stamp).
        last_result: The most recent result from executing this tool.
        last_error: The most recent error, if any.
        execution_count (int): Number of times this tool has been executed.

    Example:
        >>> def search_web(query, max_results=3):
        ...     return {"results": ["result1", "result2"]}
        ...
        >>> tool = TOOL(
        ...     name="web_search",
        ...     description="Search the web for current information.",
        ...     parameters={
        ...         "type": "object",
        ...         "properties": {
        ...             "query": {"type": "string", "description": "Search query"},
        ...             "max_results": {"type": "integer", "description": "Max"},
        ...         },
        ...         "required": ["query"],
        ...     },
        ...     fn=search_web,
        ... )
        >>> schema = tool.to_schema()
        >>> result = tool({"query": "latest news"})
    """

    def __init__(self, name, description, parameters, fn):
        """
        Initialize a TOOL with a name, description, parameter schema, and function.

        Args:
            name (str): Unique identifier for this tool. This is the name the
                LLM will use when requesting a tool call.
            description (str): Human-readable description of what this tool does.
                This helps the LLM decide when to use the tool.
            parameters (dict): JSON-Schema-compatible dict describing the tool's
                input parameters. Should include "type", "properties", and
                optionally "required". If a simpler dict of just property
                definitions is passed, it will be wrapped automatically.
            fn (callable): The function to execute. It receives keyword arguments
                matching the parameter names the LLM provides.
        """
        self.name = name
        self.id = event_stamp()
        self.description = description
        self.parameters = self._normalize_parameters(parameters)
        self.fn = fn
        self.last_result = None
        self.last_error = None
        self.execution_count = 0
        self.execution_history = []

    def _normalize_parameters(self, parameters):
        """
        Ensure parameters follow JSON Schema object format.

        If the caller provides a flat dict of property definitions (without
        the wrapping "type": "object"), this method wraps it automatically.
        This keeps the constructor ergonomic for simple cases.

        Args:
            parameters (dict): Raw parameter spec from the constructor.

        Returns:
            dict: A properly structured JSON Schema object.
        """
        if not parameters:
            return {"type": "object", "properties": {}}

        # Already properly structured
        if parameters.get("type") == "object" and "properties" in parameters:
            return parameters

        # Flat dict of property defs — wrap it
        if all(isinstance(v, dict) for v in parameters.values()):
            has_schema_keys = any(
                "type" in v or "description" in v
                for v in parameters.values()
            )
            if has_schema_keys:
                return {"type": "object", "properties": parameters}

        # Already structured but missing explicit "type"
        if "properties" in parameters:
            return {"type": "object", **parameters}

        return {"type": "object", "properties": parameters}

    def __call__(self, arguments=None):
        """
        Execute the tool with the given arguments.

        This is normally called by the agent loop, not by the user directly.
        The arguments dict comes from the LLM's tool-call request and is
        unpacked as keyword arguments to the wrapped function.

        Args:
            arguments (dict, optional): Keyword arguments for the function,
                as provided by the LLM. Defaults to {}.

        Returns:
            The result of executing the wrapped function.

        Example:
            >>> tool = TOOL("add", "Add numbers", {...}, lambda a, b: a + b)
            >>> tool({"a": 2, "b": 3})
            5
        """
        arguments = arguments or {}
        start_time = time_module.time()
        self.execution_count += 1

        try:
            result = self.fn(**arguments)
            self.last_result = result
            self.last_error = None

            duration_ms = (time_module.time() - start_time) * 1000
            self.execution_history.append({
                'stamp': event_stamp(),
                'duration_ms': duration_ms,
                'success': True,
                'error': None,
            })
            return result

        except Exception as e:
            self.last_error = e
            duration_ms = (time_module.time() - start_time) * 1000
            self.execution_history.append({
                'stamp': event_stamp(),
                'duration_ms': duration_ms,
                'success': False,
                'error': str(e),
            })
            raise

    def to_schema(self):
        """
        Return the tool schema in OpenAI function-calling format.

        This is the canonical format used by the AGENT class when building
        the tools array for an LLM call. Other provider formats (Anthropic,
        Gemini, etc.) are derived from this canonical form by the AGENT.

        Returns:
            dict: OpenAI-compatible function-calling schema.

        Example:
            >>> tool.to_schema()
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "Search the web.",
                    "parameters": {"type": "object", "properties": {...}}
                }
            }
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    @classmethod
    def from_action(cls, action, description=None, parameters=None):
        """
        Create a TOOL from an existing ACTION instance.

        This bridges the imperative ACTION world (your code calls it) with the
        declarative TOOL world (the LLM selects it). The ACTION's function is
        wrapped so that it can be called without a memory object — the TOOL
        receives keyword arguments from the LLM, not a memory.

        The resulting TOOL's function does NOT receive a memory object. If the
        underlying ACTION function requires memory, the agent loop is
        responsible for providing it at execution time.

        Args:
            action (ACTION): The ACTION instance to promote.
            description (str, optional): Override description. Defaults to
                the ACTION's existing description.
            parameters (dict, optional): JSON Schema for the tool's parameters.
                Required — ACTION does not carry schema information.

        Returns:
            TOOL: A new TOOL instance wrapping the ACTION's function.

        Example:
            >>> from thoughtflow import ACTION
            >>> search = ACTION(name="search", fn=search_fn)
            >>> tool = TOOL.from_action(
            ...     search,
            ...     description="Search the web",
            ...     parameters={"query": {"type": "string"}},
            ... )
        """
        default_desc = 'Tool: {}'.format(action.name)
        desc = description or getattr(action, 'description', default_desc)
        params = parameters or {"type": "object", "properties": {}}
        name = action.name

        # Wrap the ACTION's fn. ACTION fns expect (memory, **kwargs), but
        # TOOL fns receive just **kwargs from the LLM. We pass None for the
        # memory argument since TOOL execution is memory-independent — the
        # agent loop is responsible for memory integration.
        raw_fn = action.fn

        def tool_fn(**kwargs):
            """Wrapper that calls the ACTION's fn with None for memory."""
            return raw_fn(None, **kwargs)

        # Preserve the original function name for debugging
        tool_fn.__name__ = getattr(raw_fn, '__name__', name)
        tool_fn.__qualname__ = getattr(raw_fn, '__qualname__', name)
        tool_fn._source_action = action

        return cls(name=name, description=desc, parameters=params, fn=tool_fn)

    def to_dict(self):
        """
        Return a serializable dictionary representation of this tool.

        The function itself cannot be serialized, so it is represented by
        name only. Use from_dict() with a function registry to reconstruct.

        Returns:
            dict: Serializable representation.
        """
        return {
            "name": self.name,
            "id": self.id,
            "description": self.description,
            "parameters": self.parameters,
            "fn_name": getattr(self.fn, '__name__', self.name),
            "execution_count": self.execution_count,
        }

    @classmethod
    def from_dict(cls, data, fn_registry):
        """
        Reconstruct a TOOL from a dictionary representation.

        Args:
            data (dict): Dictionary from to_dict().
            fn_registry (dict): Maps function names to callable objects.

        Returns:
            TOOL: Reconstructed TOOL instance.

        Raises:
            KeyError: If the function name is not found in the registry.
        """
        fn_name = data["fn_name"]
        if fn_name not in fn_registry:
            raise KeyError("Function '{}' not found in registry".format(fn_name))

        tool = cls(
            name=data["name"],
            description=data["description"],
            parameters=data["parameters"],
            fn=fn_registry[fn_name],
        )
        if data.get("id"):
            tool.id = data["id"]
        tool.execution_count = data.get("execution_count", 0)
        return tool

    def __str__(self):
        """Return a concise string representation."""
        return "TOOL({}, executions={})".format(self.name, self.execution_count)

    def __repr__(self):
        """Return a detailed string representation."""
        props = self.parameters.get("properties", {})
        param_keys = list(props.keys())
        return "TOOL(name='{}', description='{}', params={})".format(
            self.name, self.description[:50], param_keys
        )
