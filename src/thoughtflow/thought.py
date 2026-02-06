"""
THOUGHT class for ThoughtFlow.

The THOUGHT class represents a single, modular reasoning or action step within an agentic 
workflow. It is the atomic unit of cognition in the Thoughtflow framework.
"""

from __future__ import annotations

import json
import copy

from thoughtflow._util import (
    event_stamp,
    construct_prompt,
    construct_msgs,
    valid_extract,
    ValidExtractError,
)


class THOUGHT:
    """
    The THOUGHT class represents a single, modular reasoning or action step within an agentic 
    workflow. It is designed to operate on MEMORY objects, orchestrating LLM calls, memory queries, 
    and variable manipulations in a composable and traceable manner. 
    THOUGHTs are the atomic units of reasoning, planning, and execution in the Thoughtflow framework, 
    and can be chained or composed to build complex agent behaviors.

    CONCEPT:
    A thought is a self-contained, modular process of (1) creating a structured prompt for an LLM, 
    (2) Executing the LLM request, (3) cleaning / validating the LLM response, and (4) retry execution 
    if it is necesary. It is the discrete unit of cognition. It is the execution of a single cognitive task. 
    In-so-doing, we have created the fundamental component of architecting multi-step cognitive systems.

    The Simple Equation of a Thought:
    Thoughts = Prompt + Context + LLM + Parsing + Validation


    COMPONENTS:

    1. PROMPT
    The Prompt() object is essentially the structured template which may contain certain parameters to fill-out. 
    This defines the structure and the rules for executing the LLM request.

    2. CONTEXT
    This is the relevant context which comes from a Memory() object. It is passed to a prompt object in the 
    structure of a dictionary containing the variables required / optional. Any context that is given, but 
    does not exist as a variable in the prompt, will be excluded.

    3. LLM REQUEST
    This is the simple transaction of submitting a structured Messages object to an LLM in order to receive 
    a response. The messages object may include a system prompt and a series of historical user / assistant 
    interactions. Passed in this request is also parameters like temperature.

    4. PARSING
    It is often that LLMs offer extra text even if they are told not to. For this reason, it is important 
    to parse the response such that we are only handling the content that was requested, and nothing more. 
    So if we are asking for a Python List, the parsed response should begin with "[" and end with "]".

    5. VALIDATION
    It is possible that even if a response was successfully parsed that it is not valid, given the constraints 
    of the Thought. For this reason, it is helpful to have a validation routine that stamps the response as valid 
    according to a fixed list of rules. "max_retries" is a param that tells the Thought how many times it can 
    retry the prompt before returning an error.


    Supported Operations:
        - llm_call: Execute an LLM request with prompt and context (default)
        - memory_query: Query memory state and return variables/data without LLM
        - variable_set: Set or compute memory variables from context
        - conditional: Execute logic based on memory conditions

    Key Features:
        - Callable interface: mem = thought(mem) or mem = thought(mem, vars)
        - Automatic retry with configurable attempts and repair prompts
        - Schema-based response parsing via valid_extract or custom parsers
        - Multiple validators: has_keys, list_min_len, custom callables
        - Pre/post hooks for custom processing
        - Full execution tracing and history
        - Serialization support via to_dict()/from_dict()
        - Channel support for message tracking

    Parameters:
        name (str): Unique identifier for this thought
        llm (LLM): LLM instance for execution (required for llm_call operation)
        prompt (str|dict): Prompt template with {variable} placeholders
        operation (str): Type of operation ('llm_call', 'memory_query', 'variable_set', 'conditional')
        system_prompt (str): Optional system prompt for LLM context (via config)
        parser (str|callable): Response parser ('text', 'json', 'list', or callable)
        parsing_rules (dict): Schema for valid_extract parsing (e.g., {'kind': 'python', 'format': []})
        validator (str|callable): Response validator ('any', 'has_keys:k1,k2', 'list_min_len:N', or callable)
        max_retries (int): Maximum retry attempts (default: 1)
        retry_delay (float): Delay between retries in seconds (default: 0)
        required_vars (list): Variables required from memory
        optional_vars (list): Optional variables from memory
        output_var (str): Variable name for storing result (default: '{name}_result')
        pre_hook (callable): Function called before execution: fn(thought, memory, vars, **kwargs)
        post_hook (callable): Function called after execution: fn(thought, memory, result, error)
        channel (str): Channel for message tracking (default: 'system')
        add_reflection (bool): Whether to add reflection on success (default: True)

    Example usage:
        # Basic LLM call with result storage
        mem = MEMORY()
        llm = LLM(model="openai:gpt-4o-mini", api_key="...")
        thought = THOUGHT(
            name="summarize",
            llm=llm,
            prompt="Summarize the last user message: {last_user_msg}",
            operation="llm_call"
        )
        mem = thought(mem)  # Executes the thought, updates memory with result
        result = mem.get_var("summarize_result")

        # Schema-based parsing example
        thought = THOUGHT(
            name="extract_info",
            llm=llm,
            prompt="Extract name and age from: {text}",
            parsing_rules={"kind": "python", "format": {"name": "", "age": 0}}
        )

        # Memory query example (no LLM)
        thought = THOUGHT(
            name="get_context",
            operation="memory_query",
            required_vars=["user_name", "session_id"]
        )

        # Variable set example
        thought = THOUGHT(
            name="init_session",
            operation="variable_set",
            prompt={"session_active": True, "start_time": None}  # dict of values to set
        )


    !!! IMPORTANT !!!
    The resulting functionality from this class must enable the following pattern:
    mem = thought(mem) # where mem is a MEMORY object
    or
    mem = thought(mem,vars) # where vars (optional)is a dictionary of variables to pass to the thought

    THOUGHT OPERATIONS MUST BE CALLABLE.

    """
    
    # Valid operation types
    VALID_OPERATIONS = {'llm_call', 'memory_query', 'variable_set', 'conditional'}

    def __init__(self, name=None, llm=None, prompt=None, operation=None, **kwargs):
        """
        Initialize a THOUGHT instance.

        Args:
            name (str): Name of the thought.
            llm: LLM interface or callable.
            prompt: Prompt template (str or dict).
            operation (str): Operation type (e.g., 'llm_call', 'memory_query', etc).
            **kwargs: Additional configuration parameters.
        """
        self.name = name
        self.id = event_stamp() 
        self.llm = llm
        self.prompt = prompt
        self.operation = operation

        # Store any additional configuration parameters
        self.config = kwargs.copy()

        # Optionally, store a description or docstring if provided
        self.description = kwargs.get("description", None)

        # Optionally, store validation rules, parsing functions, etc.
        self.validation = kwargs.get("validation", None)
        self.parse_fn = kwargs.get("parse_fn", None)
        self.max_retries = kwargs.get("max_retries", 1)
        self.retry_delay = kwargs.get("retry_delay", 0)

        # Optionally, store default context variables or requirements
        self.required_vars = kwargs.get("required_vars", [])
        self.optional_vars = kwargs.get("optional_vars", [])

        # Optionally, store output variable name
        self.output_var = kwargs.get("output_var", "{}_result".format(self.name) if self.name else None)

        # Internal state for tracking last result, errors, etc.
        self.last_result = None
        self.last_error = None
        self.last_prompt = None
        self.last_msgs = None
        self.last_response = None

        # Allow for custom hooks (pre/post processing)
        self.pre_hook = kwargs.get("pre_hook", None)
        self.post_hook = kwargs.get("post_hook", None)
        
        # Execution history tracking
        self.execution_history = []


    def __call__(self, memory, vars={}, **kwargs):
        """
        Execute the thought on the given MEMORY object.

        Args:
            memory: MEMORY object.
            vars: Optional dictionary of variables to pass to the thought.
            **kwargs: Additional parameters for execution.
        Returns:
            Updated MEMORY object with result stored (if applicable).
        """
        import time as time_module
        
        start_time = time_module.time()
        
        # Allow vars to be None
        if vars is None:
            vars = {}
        
        # Pre-hook
        if self.pre_hook and callable(self.pre_hook):
            self.pre_hook(self, memory, vars, **kwargs)

        # Determine operation type
        operation = self.operation or 'llm_call'
        
        # Dispatch to appropriate handler based on operation type
        if operation == 'llm_call':
            result, last_error, attempts_made = self._execute_llm_call(memory, vars, **kwargs)
        elif operation == 'memory_query':
            result, last_error, attempts_made = self._execute_memory_query(memory, vars, **kwargs)
        elif operation == 'variable_set':
            result, last_error, attempts_made = self._execute_variable_set(memory, vars, **kwargs)
        elif operation == 'conditional':
            result, last_error, attempts_made = self._execute_conditional(memory, vars, **kwargs)
        else:
            raise ValueError("Unknown operation: {}. Valid operations: {}".format(operation, self.VALID_OPERATIONS))
        
        # Calculate execution duration
        duration_ms = (time_module.time() - start_time) * 1000
        
        # Build execution event for logging
        execution_event = {
            'thought_name': self.name,
            'thought_id': self.id,
            'operation': operation,
            'attempts': attempts_made,
            'success': result is not None,
            'duration_ms': round(duration_ms, 2),
            'output_var': self.output_var
        }

        # If failed after all retries
        if result is None and last_error is not None:
            execution_event['error'] = last_error
            if hasattr(memory, "add_log") and callable(getattr(memory, "add_log", None)):
                memory.add_log("Thought execution failed: " + json.dumps(execution_event))
            # Store None as result
            self.update_memory(memory, None)
        else:
            if hasattr(memory, "add_log") and callable(getattr(memory, "add_log", None)):
                memory.add_log("Thought execution complete: " + json.dumps(execution_event))
            self.update_memory(memory, result)
        
        # Track execution history on the THOUGHT instance
        self.execution_history.append({
            'stamp': event_stamp(),
            'memory_id': getattr(memory, 'id', None),
            'operation': operation,
            'duration_ms': duration_ms,
            'success': result is not None or last_error is None,
            'attempts': attempts_made,
            'error': self.last_error
        })

        # Post-hook
        if self.post_hook and callable(self.post_hook):
            self.post_hook(self, memory, self.last_result, self.last_error)

        return memory

    def _build_repair_suffix(self, why):
        """
        Build the repair suffix for retry attempts.
        Subclasses can override this to customize repair prompts.
        
        Args:
            why (str): Reason the previous attempt failed.
        
        Returns:
            str: Suffix to append to the prompt for retry.
        """
        return "\n(Please return only the requested format; your last answer failed: {})".format(why)

    def _execute_llm_call(self, memory, vars, **kwargs):
        """
        Execute an LLM call operation with retry logic.
        
        Returns:
            tuple: (result, last_error, attempts_made)
        """
        import copy as copy_module
        import time as time_module
        
        retries_left = self.max_retries
        last_error = None
        result = None
        attempts_made = 0
        
        # Store original prompt to avoid mutation - work with a copy
        original_prompt = copy_module.deepcopy(self.prompt)
        working_prompt = copy_module.deepcopy(self.prompt)

        while retries_left > 0:
            attempts_made += 1
            try:
                # Temporarily set working prompt for this iteration
                self.prompt = working_prompt
                
                # Build context and prompt/messages
                ctx = self.get_context(memory)
                ctx.update(vars)
                msgs = self.build_msgs(memory, ctx)

                # Run LLM
                llm_kwargs = self.config.get("llm_params", {})
                llm_kwargs.update(kwargs)
                response = self.run_llm(msgs, **llm_kwargs)
                self.last_response = response

                # Get channel from config for message tracking
                channel = self.config.get("channel", "api")
                
                # Add assistant message to memory (if possible)
                if hasattr(memory, "add_msg") and callable(getattr(memory, "add_msg", None)):
                    memory.add_msg("assistant", response, channel=channel)

                # Parse
                parsed = self.parse_response(response)
                self.last_result = parsed

                # Validate
                valid, why = self.validate(parsed)
                if valid:
                    result = parsed
                    self.last_error = None
                    # Logging
                    if hasattr(memory, "add_log") and callable(getattr(memory, "add_log", None)):
                        memory.add_log("Thought '{}' completed successfully".format(self.name))
                    # Add reflection for reasoning trace (if configured)
                    if self.config.get("add_reflection", True):
                        if hasattr(memory, "add_ref") and callable(getattr(memory, "add_ref", None)):
                            # Truncate response for reflection if too long
                            response_preview = str(response)[:300]
                            if len(str(response)) > 300:
                                response_preview += "..."
                            memory.add_ref("Thought '{}': {}".format(self.name, response_preview))
                    break
                else:
                    last_error = why
                    self.last_error = why
                    if hasattr(memory, "add_log") and callable(getattr(memory, "add_log", None)):
                        memory.add_log("Thought '{}' validation failed: {}".format(self.name, why))
                    # Create repair suffix for next retry (modify working_prompt, not original)
                    repair_suffix = self._build_repair_suffix(why)
                    if isinstance(original_prompt, str):
                        working_prompt = original_prompt.rstrip() + repair_suffix
                    elif isinstance(original_prompt, dict):
                        working_prompt = copy_module.deepcopy(original_prompt)
                        last_key = list(working_prompt.keys())[-1]
                        working_prompt[last_key] = working_prompt[last_key].rstrip() + repair_suffix
            except Exception as e:
                last_error = str(e)
                self.last_error = last_error
                if hasattr(memory, "add_log") and callable(getattr(memory, "add_log", None)):
                    memory.add_log("Thought '{}' error: {}".format(self.name, last_error))
                # Create repair suffix for next retry (modify working_prompt, not original)
                repair_suffix = self._build_repair_suffix(last_error)
                if isinstance(original_prompt, str):
                    working_prompt = original_prompt.rstrip() + repair_suffix
                elif isinstance(original_prompt, dict):
                    working_prompt = copy_module.deepcopy(original_prompt)
                    last_key = list(working_prompt.keys())[-1]
                    working_prompt[last_key] = working_prompt[last_key].rstrip() + repair_suffix
            retries_left -= 1
            if self.retry_delay:
                time_module.sleep(self.retry_delay)

        # Restore original prompt after execution (prevents permanent mutation)
        self.prompt = original_prompt
        
        return result, last_error, attempts_made

    def _execute_memory_query(self, memory, vars, **kwargs):
        """
        Execute a memory query operation (no LLM involved).
        Retrieves specified variables from memory and returns them as a dict.
        
        Returns:
            tuple: (result, last_error, attempts_made)
        """
        try:
            result = {}
            
            # Get required variables
            for var in self.required_vars:
                if hasattr(memory, "get_var") and callable(getattr(memory, "get_var", None)):
                    val = memory.get_var(var)
                else:
                    val = getattr(memory, var, None)
                
                if val is None:
                    return None, "Required variable '{}' not found in memory".format(var), 1
                result[var] = val
            
            # Get optional variables
            for var in self.optional_vars:
                if hasattr(memory, "get_var") and callable(getattr(memory, "get_var", None)):
                    val = memory.get_var(var)
                else:
                    val = getattr(memory, var, None)
                
                if val is not None:
                    result[var] = val
            
            # Include any vars passed directly
            result.update(vars)
            
            self.last_result = result
            self.last_error = None
            
            if hasattr(memory, "add_log") and callable(getattr(memory, "add_log", None)):
                memory.add_log("Thought '{}' memory query completed".format(self.name))
            
            return result, None, 1
            
        except Exception as e:
            self.last_error = str(e)
            return None, str(e), 1

    def _execute_variable_set(self, memory, vars, **kwargs):
        """
        Execute a variable set operation.
        Sets variables in memory from the prompt (as dict) or vars parameter.
        
        Returns:
            tuple: (result, last_error, attempts_made)
        """
        try:
            values_to_set = {}
            
            # If prompt is a dict, use it as the values to set
            if isinstance(self.prompt, dict):
                values_to_set.update(self.prompt)
            
            # Override/add with vars parameter
            values_to_set.update(vars)
            
            # Set each variable in memory
            for key, value in values_to_set.items():
                if hasattr(memory, "set_var") and callable(getattr(memory, "set_var", None)):
                    desc = self.config.get("var_descriptions", {}).get(key, "Set by thought: {}".format(self.name))
                    memory.set_var(key, value, desc=desc)
                elif hasattr(memory, "vars"):
                    if key not in memory.vars:
                        memory.vars[key] = []
                    stamp = event_stamp(value)
                    memory.vars[key].append([stamp, value])
            
            self.last_result = values_to_set
            self.last_error = None
            
            if hasattr(memory, "add_log") and callable(getattr(memory, "add_log", None)):
                memory.add_log("Thought '{}' set {} variables".format(self.name, len(values_to_set)))
            
            return values_to_set, None, 1
            
        except Exception as e:
            self.last_error = str(e)
            return None, str(e), 1

    def _execute_conditional(self, memory, vars, **kwargs):
        """
        Execute a conditional operation.
        Evaluates a condition from config and returns the appropriate result.
        
        Config options:
            condition (callable): Function that takes (memory, vars) and returns bool
            if_true: Value/action if condition is true
            if_false: Value/action if condition is false
        
        Returns:
            tuple: (result, last_error, attempts_made)
        """
        try:
            condition_fn = self.config.get("condition")
            if_true = self.config.get("if_true")
            if_false = self.config.get("if_false")
            
            if condition_fn is None:
                return None, "No condition function provided for conditional operation", 1
            
            if not callable(condition_fn):
                return None, "Condition must be callable", 1
            
            # Evaluate condition
            ctx = self.get_context(memory)
            ctx.update(vars)
            condition_result = condition_fn(memory, ctx)
            
            # Return appropriate value
            if condition_result:
                result = if_true
                if callable(if_true):
                    result = if_true(memory, ctx)
            else:
                result = if_false
                if callable(if_false):
                    result = if_false(memory, ctx)
            
            self.last_result = result
            self.last_error = None
            
            if hasattr(memory, "add_log") and callable(getattr(memory, "add_log", None)):
                memory.add_log("Thought '{}' conditional evaluated to {}".format(self.name, bool(condition_result)))
            
            return result, None, 1
            
        except Exception as e:
            self.last_error = str(e)
            return None, str(e), 1

    def build_prompt(self, memory, context_vars=None):
        """
        Build the prompt for the LLM using construct_prompt.

        Args:
            memory: MEMORY object providing context.
            context_vars (dict): Optional context variables to fill the prompt.

        Returns:
            str: The constructed prompt string.
        """
        # Get context variables (merge get_context and context_vars)
        ctx = self.get_context(memory)
        if context_vars:
            ctx.update(context_vars)
        prompt_template = self.prompt
        # If prompt is a dict, use construct_prompt, else format as string
        if isinstance(prompt_template, dict):
            prompt = construct_prompt(prompt_template)
        elif isinstance(prompt_template, str):
            try:
                prompt = prompt_template.format(**ctx)
            except Exception:
                # fallback: just return as is
                prompt = prompt_template
        else:
            prompt = str(prompt_template)
        self.last_prompt = prompt
        return prompt

    def build_msgs(self, memory, context_vars=None):
        """
        Build the messages list for the LLM using construct_msgs.

        Args:
            memory: MEMORY object providing context.
            context_vars (dict): Optional context variables to fill the prompt.

        Returns:
            list: List of message dicts for LLM input.
        """
        ctx = self.get_context(memory)
        if context_vars:
            ctx.update(context_vars)
        # Compose system and user prompts
        sys_prompt = self.config.get("system_prompt", "")
        usr_prompt = self.build_prompt(memory, ctx)
        # Optionally, allow for prior messages from memory
        msgs = []
        if hasattr(memory, "get_msgs"):
            # Optionally, get recent messages for context
            msgs = memory.get_msgs(repr="list") if callable(getattr(memory, "get_msgs", None)) else []
        # Build messages using construct_msgs
        msgs_out = construct_msgs(
            usr_prompt=usr_prompt,
            vars=ctx,
            sys_prompt=sys_prompt,
            msgs=msgs
        )
        self.last_msgs = msgs_out
        return msgs_out

    def get_context(self, memory):
        """
        Extract relevant context from the MEMORY object for this thought.

        Args:
            memory: MEMORY object.

        Returns:
            dict: Context variables for prompt filling.
        """
        ctx = {}
        # If required_vars is specified, try to get those from memory
        if hasattr(self, "required_vars") and self.required_vars:
            for var in self.required_vars:
                # Try to get from memory.get_var if available
                if hasattr(memory, "get_var") and callable(getattr(memory, "get_var", None)):
                    val = memory.get_var(var)
                else:
                    val = getattr(memory, var, None)
                if val is not None:
                    ctx[var] = val
        # Optionally, add optional_vars if present in memory
        if hasattr(self, "optional_vars") and self.optional_vars:
            for var in self.optional_vars:
                if hasattr(memory, "get_var") and callable(getattr(memory, "get_var", None)):
                    val = memory.get_var(var)
                else:
                    val = getattr(memory, var, None)
                if val is not None:
                    ctx[var] = val
        # Add some common context keys if available (content_only=True for prompt templates)
        if hasattr(memory, "last_user_msg") and callable(getattr(memory, "last_user_msg", None)):
            ctx["last_user_msg"] = memory.last_user_msg(content_only=True)
        if hasattr(memory, "last_asst_msg") and callable(getattr(memory, "last_asst_msg", None)):
            ctx["last_asst_msg"] = memory.last_asst_msg(content_only=True)
        if hasattr(memory, "get_msgs") and callable(getattr(memory, "get_msgs", None)):
            ctx["messages"] = memory.get_msgs(repr="list")
        # Add all memory.vars if present
        if hasattr(memory, "vars"):
            ctx.update(getattr(memory, "vars", {}))
        return ctx

    def run_llm(self, msgs, **llm_kwargs):
        """
        Execute the LLM call with the given messages.
        !!! USE THE EXISTING LLM CLASS !!!

        Args:
            msgs (list): List of message dicts.
            **llm_kwargs: Additional LLM parameters.

        Returns:
            str: Raw LLM response.
        """
        if self.llm is None:
            raise ValueError("No LLM instance provided to this THOUGHT.")
        # The LLM class is expected to be callable: llm(msgs, **kwargs)
        # If LLM is a class with .call, use that (standard interface)
        if hasattr(self.llm, "call") and callable(getattr(self.llm, "call", None)):
            response = self.llm.call(msgs, llm_kwargs)
        elif hasattr(self.llm, "chat") and callable(getattr(self.llm, "chat", None)):
            response = self.llm.chat(msgs, **llm_kwargs)
        else:
            response = self.llm(msgs, **llm_kwargs)
        
        # Handle list response from LLM.call() - it returns a list of choices
        if isinstance(response, list):
            response = response[0] if response else ""
        
        # If response is a dict with 'content', extract it
        if isinstance(response, dict) and "content" in response:
            return response["content"]
        
        return response

    def parse_response(self, response):
        """
        Parse the LLM response to extract the desired content.

        Args:
            response (str): Raw LLM response.

        Returns:
            object: Parsed result (e.g., string, list, dict).
        
        Supports:
            - Custom parse_fn callable
            - Schema-based parsing via parsing_rules (uses valid_extract)
            - Built-in parsers: 'text', 'json', 'list'
        """
        # Use custom parse_fn if provided
        if self.parse_fn and callable(self.parse_fn):
            return self.parse_fn(response)
        
        # Check for schema-based parsing rules (using valid_extract)
        parsing_rules = self.config.get("parsing_rules")
        if parsing_rules:
            try:
                return valid_extract(response, parsing_rules)
            except ValidExtractError as e:
                raise ValueError("Schema-based parsing failed: {}".format(e))
        
        # Use built-in parser based on config
        parser = self.config.get("parser", None)
        if parser is None:
            # Default: return as string
            return response
        if parser == "text":
            return response
        elif parser == "json":
            import re
            # Remove code fences if present
            text = response.strip()
            text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
            # Find first JSON object or array
            match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
            if match:
                json_str = match.group(1)
                return json.loads(json_str)
            else:
                raise ValueError("No JSON object or array found in response.")
        elif parser == "list":
            import ast, re
            # Find first list literal
            match = re.search(r"(\[.*\])", response, re.DOTALL)
            if match:
                list_str = match.group(1)
                return ast.literal_eval(list_str)
            else:
                raise ValueError("No list found in response.")
        elif callable(parser):
            return parser(response)
        else:
            # Unknown parser, return as is
            return response

    def validate(self, parsed_result):
        """
        Validate the parsed result according to the thought's rules.

        Args:
            parsed_result: The parsed output from the LLM.

        Returns:
            (bool, why): True if valid, False otherwise, and reason string.
        """
        # Use custom validation if provided
        if self.validation and callable(self.validation):
            try:
                valid, why = self.validation(parsed_result)
                return bool(valid), why
            except Exception as e:
                return False, "Validation exception: {}".format(e)
        # Use built-in validator based on config
        validator = self.config.get("validator", None)
        if validator is None or validator == "any":
            return True, ""
        elif isinstance(validator, str):
            if validator.startswith("has_keys:"):
                keys = [k.strip() for k in validator.split(":", 1)[1].split(",")]
                if isinstance(parsed_result, dict):
                    missing = [k for k in keys if k not in parsed_result]
                    if not missing:
                        return True, ""
                    else:
                        return False, "Missing keys: {}".format(missing)
                else:
                    return False, "Result is not a dict"
            elif validator.startswith("list_min_len:"):
                try:
                    min_len = int(validator.split(":", 1)[1])
                except Exception:
                    min_len = 1
                if isinstance(parsed_result, list) and len(parsed_result) >= min_len:
                    return True, ""
                else:
                    return False, "List too short (min {})".format(min_len)
            elif validator == "summary_v1":
                # Example: summary must be a string of at least 10 chars
                if isinstance(parsed_result, str) and len(parsed_result.strip()) >= 10:
                    return True, ""
                else:
                    return False, "Summary too short"
            else:
                return True, ""
        elif callable(validator):
            try:
                valid, why = validator(parsed_result)
                return bool(valid), why
            except Exception as e:
                return False, "Validation exception: {}".format(e)
        else:
            return True, ""

    def update_memory(self, memory, result):
        """
        Update the MEMORY object with the result of this thought.

        Args:
            memory: MEMORY object.
            result: The result to store.

        Returns:
            MEMORY: Updated memory object.
        """
        # Store result in vars or via set_var if available
        varname = self.output_var or ("{}_result".format(self.name) if self.name else "thought_result")
        if hasattr(memory, "set_var") and callable(getattr(memory, "set_var", None)):
            memory.set_var(varname, result, desc="Result of thought: {}".format(self.name))
        elif hasattr(memory, "vars"):
            # Fallback: directly access vars dict if set_var not available
            if varname not in memory.vars:
                memory.vars[varname] = []
            stamp = event_stamp(result) if 'event_stamp' in globals() else 'no_stamp'
            memory.vars[varname].append({'object': result, 'stamp': stamp})
        else:
            setattr(memory, varname, result)
        return memory

    def to_dict(self):
        """
        Return a serializable dictionary representation of this THOUGHT.
        
        Note: The LLM instance, parse_fn, validation, and hooks cannot be serialized,
        so they are represented by type/name only. When deserializing, these must be
        provided separately.
        
        Returns:
            dict: Serializable representation of this thought.
        """
        return {
            "name": self.name,
            "id": self.id,
            "prompt": self.prompt,
            "operation": self.operation,
            "config": self.config,
            "description": self.description,
            "max_retries": self.max_retries,
            "retry_delay": self.retry_delay,
            "output_var": self.output_var,
            "required_vars": self.required_vars,
            "optional_vars": self.optional_vars,
            "execution_history": self.execution_history,
            # Store metadata about non-serializable items
            "llm_type": type(self.llm).__name__ if self.llm else None,
            "has_parse_fn": self.parse_fn is not None,
            "has_validation": self.validation is not None,
            "has_pre_hook": self.pre_hook is not None,
            "has_post_hook": self.post_hook is not None,
        }

    @classmethod
    def from_dict(cls, data, llm=None, parse_fn=None, validation=None, pre_hook=None, post_hook=None):
        """
        Reconstruct a THOUGHT from a dictionary representation.
        
        Args:
            data (dict): Dictionary representation of a THOUGHT.
            llm: LLM instance to use (required for execution).
            parse_fn: Optional custom parse function.
            validation: Optional custom validation function.
            pre_hook: Optional pre-execution hook.
            post_hook: Optional post-execution hook.
            
        Returns:
            THOUGHT: Reconstructed THOUGHT object.
        """
        # Extract config and merge with explicit kwargs
        config = data.get("config", {}).copy()
        
        thought = cls(
            name=data.get("name"),
            llm=llm,
            prompt=data.get("prompt"),
            operation=data.get("operation"),
            description=data.get("description"),
            max_retries=data.get("max_retries", 1),
            retry_delay=data.get("retry_delay", 0),
            output_var=data.get("output_var"),
            required_vars=data.get("required_vars", []),
            optional_vars=data.get("optional_vars", []),
            parse_fn=parse_fn,
            validation=validation,
            pre_hook=pre_hook,
            post_hook=post_hook,
            **config
        )
        
        # Restore ID if provided
        if data.get("id"):
            thought.id = data["id"]
        
        # Restore execution history
        thought.execution_history = data.get("execution_history", [])
        
        return thought

    def copy(self):
        """
        Return a deep copy of this THOUGHT.
        
        Note: The LLM instance is shallow-copied (same reference), as LLM
        instances typically should be shared. All other attributes are deep-copied.
        
        Returns:
            THOUGHT: A new THOUGHT instance with copied attributes.
        """
        import copy as copy_module
        
        new_thought = THOUGHT(
            name=self.name,
            llm=self.llm,  # Shallow copy - same LLM instance
            prompt=copy_module.deepcopy(self.prompt),
            operation=self.operation,
            description=self.description,
            max_retries=self.max_retries,
            retry_delay=self.retry_delay,
            output_var=self.output_var,
            required_vars=copy_module.deepcopy(self.required_vars),
            optional_vars=copy_module.deepcopy(self.optional_vars),
            parse_fn=self.parse_fn,
            validation=self.validation,
            pre_hook=self.pre_hook,
            post_hook=self.post_hook,
            **copy_module.deepcopy(self.config)
        )
        
        # Copy internal state
        new_thought.id = event_stamp()  # Generate new ID for the copy
        new_thought.execution_history = copy_module.deepcopy(self.execution_history)
        new_thought.last_result = copy_module.deepcopy(self.last_result)
        new_thought.last_error = self.last_error
        new_thought.last_prompt = self.last_prompt
        new_thought.last_msgs = copy_module.deepcopy(self.last_msgs)
        new_thought.last_response = self.last_response
        
        return new_thought

    def __repr__(self):
        """
        Return a detailed string representation of this THOUGHT.
        
        Returns:
            str: Detailed representation including key attributes.
        """
        return ("THOUGHT(name='{}', operation='{}', "
                "max_retries={}, output_var='{}')".format(
                    self.name, self.operation, self.max_retries, self.output_var))

    def __str__(self):
        """
        Return a human-readable string representation of this THOUGHT.
        
        Returns:
            str: Simple description of the thought.
        """
        return "Thought: {}".format(self.name or 'unnamed')


ThoughtClassTests = """
# --- THOUGHT Class Tests ---

# Test 1: Basic THOUGHT instantiation and attributes
>>> from thoughtflow import THOUGHT, MEMORY, event_stamp
>>> t = THOUGHT(name="test_thought", prompt="Hello {name}", max_retries=3)
>>> t.name
'test_thought'
>>> t.max_retries
3
>>> t.output_var
'test_thought_result'
>>> t.operation is None  # Defaults to None, which means 'llm_call'
True
>>> len(t.execution_history)
0

# Test 2: Serialization round-trip with to_dict/from_dict
>>> t1 = THOUGHT(name="serialize_test", prompt="test prompt", max_retries=3, output_var="my_output")
>>> data = t1.to_dict()
>>> data['name']
'serialize_test'
>>> data['max_retries']
3
>>> data['output_var']
'my_output'
>>> t2 = THOUGHT.from_dict(data)
>>> t2.name == t1.name
True
>>> t2.max_retries == t1.max_retries
True
>>> t2.output_var == t1.output_var
True

# Test 3: Copy creates independent instance
>>> t1 = THOUGHT(name="copy_test", prompt="original prompt")
>>> t2 = t1.copy()
>>> t2.name = "modified"
>>> t1.name
'copy_test'
>>> t2.name
'modified'
>>> t1.id != t2.id  # Copy gets new ID
True

# Test 4: __repr__ and __str__
>>> t = THOUGHT(name="repr_test", operation="llm_call", max_retries=2, output_var="result")
>>> "repr_test" in repr(t)
True
>>> "llm_call" in repr(t)
True
>>> str(t)
'Thought: repr_test'
>>> t2 = THOUGHT()  # unnamed
>>> str(t2)
'Thought: unnamed'

# Test 5: Memory query operation (no LLM)
>>> mem = MEMORY()
>>> mem.set_var("user_name", "Alice", desc="Test user")
>>> mem.set_var("session_id", "sess123", desc="Test session")
>>> t = THOUGHT(
...     name="query_test",
...     operation="memory_query",
...     required_vars=["user_name", "session_id"]
... )
>>> mem2 = t(mem)
>>> result = mem2.get_var("query_test_result")
>>> result['user_name']
'Alice'
>>> result['session_id']
'sess123'

# Test 6: Variable set operation
>>> mem = MEMORY()
>>> t = THOUGHT(
...     name="setvar_test",
...     operation="variable_set",
...     prompt={"status": "active", "count": 42}
... )
>>> mem2 = t(mem)
>>> mem2.get_var("status")
'active'
>>> mem2.get_var("count")
42

# Test 7: Execution history tracking
>>> mem = MEMORY()
>>> t = THOUGHT(name="history_test", operation="memory_query", required_vars=[])
>>> len(t.execution_history)
0
>>> mem = t(mem)
>>> len(t.execution_history)
1
>>> t.execution_history[0]['success']
True
>>> 'duration_ms' in t.execution_history[0]
True
>>> 'stamp' in t.execution_history[0]
True

# Test 8: Conditional operation
>>> mem = MEMORY()
>>> mem.set_var("threshold", 50)
>>> t = THOUGHT(
...     name="cond_test",
...     operation="conditional",
...     condition=lambda m, ctx: ctx.get('value', 0) > ctx.get('threshold', 0),
...     if_true="above",
...     if_false="below"
... )
>>> mem2 = t(mem, vars={'value': 75})
>>> mem2.get_var("cond_test_result")
'above'
>>> mem3 = t(mem, vars={'value': 25})
>>> mem3.get_var("cond_test_result")
'below'

# Test 9: VALID_OPERATIONS class attribute
>>> 'llm_call' in THOUGHT.VALID_OPERATIONS
True
>>> 'memory_query' in THOUGHT.VALID_OPERATIONS
True
>>> 'variable_set' in THOUGHT.VALID_OPERATIONS
True
>>> 'conditional' in THOUGHT.VALID_OPERATIONS
True

# Test 10: Parse response with parsing_rules (valid_extract integration)
>>> t = THOUGHT(name="parse_test", parsing_rules={"kind": "python", "format": []})
>>> t.parse_response("Here is the list: [1, 2, 3]")
[1, 2, 3]
>>> t2 = THOUGHT(name="parse_dict", parsing_rules={"kind": "python", "format": {"name": "", "count": 0}})
>>> t2.parse_response("Result: {'name': 'test', 'count': 5}")
{'name': 'test', 'count': 5}

# Test 11: Built-in parsers
>>> t = THOUGHT(name="json_test", parser="json")
>>> t.parse_response('Here is JSON: {"key": "value"}')
{'key': 'value'}
>>> t2 = THOUGHT(name="list_test", parser="list")
>>> t2.parse_response("Numbers: [1, 2, 3, 4, 5]")
[1, 2, 3, 4, 5]
>>> t3 = THOUGHT(name="text_test", parser="text")
>>> t3.parse_response("plain text")
'plain text'

# Test 12: Built-in validators
>>> t = THOUGHT(name="val_test", validator="has_keys:name,age")
>>> t.validate({"name": "Alice", "age": 30})
(True, '')
>>> t.validate({"name": "Bob"})
(False, 'Missing keys: [\\'age\\']')
>>> t2 = THOUGHT(name="list_val", validator="list_min_len:3")
>>> t2.validate([1, 2, 3])
(True, '')
>>> t2.validate([1, 2])
(False, 'List too short (min 3)')

"""
