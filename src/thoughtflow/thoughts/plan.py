"""
PLAN class for ThoughtFlow.

A specialized THOUGHT subclass for structured multi-step execution planning.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import inspect
import json
import re
import time

from thoughtflow.thought import THOUGHT


class PLAN(THOUGHT):
    """
    A planning step that generates structured multi-step execution plans.
    
    Produces a plan as List[List[Dict]] where:
    - Outer list: Steps (executed sequentially)
    - Inner list: Tasks (can execute in parallel within a step)
    - Dict: Individual task with {"action": "...", "params": {...}, "reason": "..."}
    
    Each task includes:
    - action (required): Name of the action to execute
    - params (optional): Parameters for the action
    - reason (required): 1-3 sentence explanation of why this action was chosen
    
    Args:
        name (str): Unique identifier for this planner.
        llm (LLM): LLM instance for plan generation.
        actions (dict): Available actions. Supports two formats:
            - Simple: {"action_name": "description"}
            - With params: {"action_name": {"description": "...", "params": {"arg": "type?"}}}
              Use "?" suffix for optional params (e.g., "int?" means optional int)
        prompt (str): Prompt template with {variable} placeholders.
        max_steps (int): Maximum steps allowed in plan (default: 10).
        max_parallel (int): Maximum parallel tasks per step (default: 5).
        allow_empty (bool): Whether empty plans are valid (default: False).
        validate_params (bool): Validate params against schema (default: True).
        max_retries (int): Retry attempts for invalid plans (default: 3).
        **kwargs: Additional THOUGHT parameters.
    
    Example:
        # Simple actions (descriptions only)
        planner = PLAN(
            name="research",
            llm=llm,
            actions={
                "search": "Search the web for information",
                "analyze": "Analyze content for insights",
                "summarize": "Create a summary",
            },
            prompt="Create a plan to: {goal}"
        )
        
        # Actions with parameter schemas
        planner = PLAN(
            name="workflow",
            llm=llm,
            actions={
                "search": {
                    "description": "Search for information",
                    "params": {"query": "str", "max_results": "int?"}
                },
                "fetch": {
                    "description": "Fetch a resource",
                    "params": {"url": "str"}
                },
                "notify": {
                    "description": "Send notification",
                    "params": {"message": "str", "channel": "str?"}
                }
            },
            prompt="Plan to achieve: {goal}\\nContext: {context}"
        )
        
        memory.set_var("goal", "Research and summarize ThoughtFlow")
        memory = planner(memory)
        plan = memory.get_var("workflow_result")
        # [
        #     [{"action": "search", "params": {"query": "ThoughtFlow"},
        #       "reason": "Start by gathering information about the library."}],
        #     [{"action": "fetch", "params": {"url": "{step_0_result}"},
        #       "reason": "Retrieve the most relevant document for analysis."}],
        #     [{"action": "summarize", "params": {"text": "{step_1_result}"},
        #       "reason": "Condense findings into a clear summary."},
        #      {"action": "notify", "params": {"message": "Done!"},
        #       "reason": "Alert user that research is complete."}]
        # ]
    """
    
    def __init__(self, name=None, llm=None, prompt=None, actions=None, **kwargs):
        """
        Initialize a PLAN instance.
        
        Args:
            name: Name of the planner.
            llm: LLM interface.
            prompt: Prompt template.
            actions: Dict of available actions.
            **kwargs: Additional configuration.
        """
        # Validate actions
        if actions is None:
            raise ValueError("PLAN requires 'actions' parameter")
        
        if not isinstance(actions, dict):
            raise ValueError("'actions' must be a dict, got: {}".format(type(actions).__name__))
        
        if not actions:
            raise ValueError("'actions' cannot be empty")
        
        # Parse and normalize actions
        self._actions_list = list(actions.keys())
        self._actions_descriptions = {}
        self._actions_params = {}
        self._has_param_schemas = False
        
        for action_name, action_def in actions.items():
            if isinstance(action_def, str):
                # Simple format: {"action": "description"}
                self._actions_descriptions[action_name] = action_def
            elif isinstance(action_def, dict):
                # Full format: {"action": {"description": "...", "params": {...}}}
                self._actions_descriptions[action_name] = action_def.get('description', '')
                if 'params' in action_def:
                    self._actions_params[action_name] = action_def['params']
                    self._has_param_schemas = True
            else:
                raise ValueError(
                    "Action '{}' must be str or dict, got: {}".format(
                        action_name, type(action_def).__name__
                    )
                )
        
        # PLAN-specific attributes
        self.actions = actions  # Store original for serialization
        self.max_steps = kwargs.pop('max_steps', 10)
        self.max_parallel = kwargs.pop('max_parallel', 5)
        self.allow_empty = kwargs.pop('allow_empty', False)
        self.validate_params = kwargs.pop('validate_params', True)
        
        # Set default max_retries to 3 for PLAN
        if 'max_retries' not in kwargs:
            kwargs['max_retries'] = 3
        
        # Force operation to llm_call
        kwargs['operation'] = 'llm_call'
        
        super().__init__(name=name, llm=llm, prompt=prompt, **kwargs)
    
    def build_prompt(self, memory, context_vars=None):
        """
        Build prompt with actions list appended.
        
        Args:
            memory: MEMORY object providing context.
            context_vars: Optional context variables.
        
        Returns:
            str: Prompt with actions section and format instructions appended.
        """
        base_prompt = super().build_prompt(memory, context_vars)
        actions_section = self._format_actions()
        format_instructions = self._format_instructions()
        return base_prompt + "\n\n" + actions_section + "\n\n" + format_instructions
    
    def _format_actions(self):
        """
        Format actions for inclusion in prompt.
        
        Returns:
            str: Formatted actions section.
        """
        lines = ["Available Actions:"]
        
        for action_name in self._actions_list:
            desc = self._actions_descriptions.get(action_name, '')
            
            if action_name in self._actions_params:
                # Include parameter info
                params = self._actions_params[action_name]
                param_strs = []
                for param_name, param_type in params.items():
                    if param_type.endswith('?'):
                        param_strs.append("{} (optional {})".format(param_name, param_type[:-1]))
                    else:
                        param_strs.append("{} ({})".format(param_name, param_type))
                params_desc = ", ".join(param_strs) if param_strs else "none"
                lines.append("- {}: {} [params: {}]".format(action_name, desc, params_desc))
            else:
                lines.append("- {}: {}".format(action_name, desc))
        
        return "\n".join(lines)
    
    def _format_instructions(self):
        """
        Format output instructions for the LLM.
        
        Returns:
            str: Instructions for plan format.
        """
        instructions = """Output Format:
Return a plan as a JSON array of steps. Each step is an array of tasks that can run in parallel.
Each task is an object with:
- "action" (required): The action name from Available Actions
- "params" (optional): Parameters for the action
- "reason" (required): 1-3 sentences explaining why this action and these parameters were chosen

Structure: [[{{task}}, {{task}}], [{{task}}], ...]
- Outer array: steps (executed in sequence)
- Inner array: tasks (can execute in parallel within that step)

You can reference results from previous steps using $step_N_result (or $step_N.field for dict outputs)
in parameter values, where N is the step index (0-based).

Example:
[
  [{{"action": "search", "params": {{"query": "example"}}, "reason": "Start by gathering relevant information on the topic."}}],
  [{{"action": "analyze", "params": {{"content": "$step_0_result"}}, "reason": "Analyze search results to extract key insights."}}],
  [{{"action": "summarize", "params": {{"text": "$step_1_result"}}, "reason": "Condense findings into actionable summary."}},
   {{"action": "notify", "params": {{"message": "Done!"}}, "reason": "Alert user that the task is complete."}}]
]

Constraints:
- Maximum {max_steps} steps
- Maximum {max_parallel} parallel tasks per step
- Only use actions from the Available Actions list
- Each task MUST include a "reason" field (1-3 sentences, no newlines)
- Return ONLY the JSON array, no other text""".format(
            max_steps=self.max_steps, max_parallel=self.max_parallel
        )
        
        return instructions
    
    def parse_response(self, response):
        """
        Extract plan structure from LLM response.
        
        Args:
            response: Raw LLM response string.
        
        Returns:
            list: Parsed plan as List[List[Dict]], or raw response if parsing fails.
        """
        text = response.strip()
        
        # Try to extract JSON from response
        # Handle cases where LLM wraps in markdown code blocks
        if '```json' in text:
            start = text.find('```json') + 7
            end = text.find('```', start)
            if end > start:
                text = text[start:end].strip()
        elif '```' in text:
            start = text.find('```') + 3
            end = text.find('```', start)
            if end > start:
                text = text[start:end].strip()
        
        # Try to find array bounds
        if not text.startswith('['):
            start = text.find('[')
            if start >= 0:
                # Find matching closing bracket
                depth = 0
                for i, c in enumerate(text[start:], start):
                    if c == '[':
                        depth += 1
                    elif c == ']':
                        depth -= 1
                        if depth == 0:
                            text = text[start:i+1]
                            break
        
        try:
            plan = json.loads(text)
            return plan
        except json.JSONDecodeError:
            # Return raw for validation to catch
            return response
    
    def normalize_plan(self, parsed_result):
        """
        Optional hook for deterministic plan repairs before validation.

        Override in subclasses when the model returns JSON that is syntactically
        valid but needs cleanup: unwrap string plans, lift flat params onto task
        dicts, unwrap ``{"steps": [...]}`` envelopes, etc. Runs once before
        step/task/action checks.

        Default is a no-op pass-through. Keep repairs deterministic — no LLM calls.

        Args:
            parsed_result: Output from ``parse_response`` (list, dict, or occasionally str).

        Returns:
            The plan structure validation will inspect (expected: list of step lists).
        """
        return parsed_result

    def _prepare_and_validate(self, parsed_result):
        """
        Normalize once, then validate the exact plan that will be stored.

        A subclass that overrides public ``validate()`` keeps the legacy
        polymorphic path: its validator receives the raw parsed value, and that
        same value remains the stored result. Subclasses that only override
        ``normalize_plan()`` use PLAN's normalize-once path.

        Args:
            parsed_result: Parsed plan from the model response.

        Returns:
            tuple: ``(result_for_storage, is_valid, reason_string)``.
        """
        if type(self).validate is not PLAN.validate:
            return super()._prepare_and_validate(parsed_result)

        prepared = self.normalize_plan(parsed_result)
        valid, why = self._validate_plan(prepared)
        return prepared, valid, why

    def validate(self, parsed_result):
        """
        Validate plan structure, action names, and parameters.

        Flow:
          1. ``normalize_plan(parsed_result)``
          2. Top-level shape: non-empty list (unless allow_empty), max_steps
          3. Per step: list of tasks, max_parallel, non-empty
          4. Per task: ``_validate_task`` (action, params schema, reason)

        Missing required params are collected per task and reported together so
        one retry message lists every omission instead of burning max_retries
        one param at a time.

        Args:
            parsed_result: Parsed plan from LLM (normalized before checks).

        Returns:
            tuple: (is_valid, reason_string). reason_string empty when valid.
        """
        prepared = self.normalize_plan(parsed_result)
        return self._validate_plan(prepared)

    def _validate_plan(self, parsed_result):
        """
        Validate an already-normalized plan without running normalize again.

        Args:
            parsed_result: Normalized plan structure.

        Returns:
            tuple: (is_valid, reason_string)
        """
        if not isinstance(parsed_result, list):
            return False, "Plan must be a list of steps, got: {}".format(type(parsed_result).__name__)
        
        # Check empty
        if not parsed_result and not self.allow_empty:
            return False, "Plan cannot be empty"
        
        # Check max steps
        if len(parsed_result) > self.max_steps:
            return False, "Plan has {} steps, maximum is {}".format(len(parsed_result), self.max_steps)
        
        # Validate each step
        for step_idx, step in enumerate(parsed_result):
            # Each step must be a list
            if not isinstance(step, list):
                return False, "Step {} must be a list of tasks, got: {}".format(
                    step_idx, type(step).__name__
                )
            
            # Check empty step
            if not step:
                return False, "Step {} is empty (must have at least one task)".format(step_idx)
            
            # Check max parallel
            if len(step) > self.max_parallel:
                return False, "Step {} has {} tasks, maximum parallel is {}".format(
                    step_idx, len(step), self.max_parallel
                )
            
            # Validate each task
            for task_idx, task in enumerate(step):
                valid, reason = self._validate_task(task, step_idx, task_idx)
                if not valid:
                    return False, reason
        
        return True, ""
    
    def _validate_task(self, task, step_idx, task_idx):
        """
        Validate a single task within a plan step.

        Checks:
          - task is a dict with ``action`` key
          - action name exists in ``self._actions_list``
          - ``params`` is a dict when schema exists; all missing required params
            are collected before returning (aggregate error message)
          - ``reason`` is a non-empty single-line string

        Parameter schemas use ``?`` suffix for optional params (same convention
        as THOUGHT parsing_rules).

        Args:
            task: Task dict from LLM output.
            step_idx (int): Zero-based step index for error messages.
            task_idx (int): Zero-based task index within the step.

        Returns:
            tuple: (is_valid, reason_string)
        """
        task_loc = "Step {} Task {}".format(step_idx, task_idx)
        
        # Must be a dict
        if not isinstance(task, dict):
            return False, "{}: must be a dict, got: {}".format(task_loc, type(task).__name__)
        
        # Must have 'action' key
        if 'action' not in task:
            return False, "{}: missing required 'action' key".format(task_loc)
        
        action_name = task['action']
        
        # Action must be valid
        if action_name not in self._actions_list:
            return False, "{}: unknown action '{}'. Valid actions: {}".format(
                task_loc, action_name, self._actions_list
            )
        
        # Validate params if schema exists and validation is enabled
        if self.validate_params and action_name in self._actions_params:
            params_schema = self._actions_params[action_name]
            task_params = task.get('params', {})
            
            if not isinstance(task_params, dict):
                return False, "{}: 'params' must be a dict".format(task_loc)
            
            # Aggregate missing required params — report all at once for one useful retry
            missing_params = []
            for param_name, param_type in params_schema.items():
                is_optional = param_type.endswith('?')
                if not is_optional and param_name not in task_params:
                    missing_params.append(param_name)

            if missing_params:
                return False, "{}: action '{}' requires params: {}".format(
                    task_loc, action_name, ", ".join(missing_params)
                )
        
        # Validate reason field (required)
        if 'reason' not in task:
            return False, "{}: missing required 'reason' field".format(task_loc)
        
        task_reason = task['reason']
        
        if not isinstance(task_reason, str):
            return False, "{}: 'reason' must be a string, got: {}".format(
                task_loc, type(task_reason).__name__
            )
        
        if not task_reason.strip():
            return False, "{}: 'reason' cannot be empty".format(task_loc)
        
        if '\n' in task_reason:
            return False, "{}: 'reason' cannot contain newlines".format(task_loc)
        
        return True, ""
    
    def _build_repair_suffix(self, why):
        """
        Build plan-specific repair prompt for retries.

        Uses THOUGHT's humanized repair text (_format_repair_reason) and appends
        PLAN-specific constraints: valid actions list, JSON array shape, required
        action and reason fields.

        Args:
            why (str): Reason the previous attempt failed (from validate).

        Returns:
            str: Suffix appended to prompt on next retry.
        """
        actions_str = ", ".join(self._actions_list)
        friendly = self._format_repair_reason(why)
        return (
            "\n(Your previous response was invalid: {}. "
            "Return ONLY a valid JSON array. Valid actions are: {}. "
            "Each task must include 'action' and 'reason' fields.)"
        ).format(friendly, actions_str)
    
    def to_dict(self):
        """
        Return a serializable dictionary representation.
        
        Returns:
            dict: Serializable representation including PLAN-specific fields.
        """
        data = super().to_dict()
        data.update({
            'actions': self.actions,
            'max_steps': self.max_steps,
            'max_parallel': self.max_parallel,
            'allow_empty': self.allow_empty,
            'validate_params': self.validate_params,
            '_class': 'PLAN',
        })
        return data
    
    @classmethod
    def from_dict(cls, data, llm=None, **kwargs):
        """
        Reconstruct a PLAN from a dictionary representation.
        
        Args:
            data: Dictionary representation.
            llm: LLM instance to use.
            **kwargs: Additional arguments.
        
        Returns:
            PLAN: Reconstructed instance.
        """
        # Get config but remove keys we're setting explicitly to avoid duplicates
        config = data.get('config', {}).copy()
        for key in ['max_retries', 'max_steps', 'max_parallel', 'allow_empty', 'validate_params']:
            config.pop(key, None)
        
        return cls(
            name=data.get('name'),
            llm=llm,
            prompt=data.get('prompt'),
            actions=data.get('actions'),
            max_steps=data.get('max_steps', 10),
            max_parallel=data.get('max_parallel', 5),
            allow_empty=data.get('allow_empty', False),
            validate_params=data.get('validate_params', True),
            max_retries=data.get('max_retries', 3),
            **config
        )
    
    def __repr__(self):
        """Return detailed string representation."""
        return (
            "PLAN(name='{}', actions={}, max_steps={}, max_parallel={}, max_retries={})"
        ).format(
            self.name, self._actions_list, self.max_steps, self.max_parallel, self.max_retries
        )
    
    def __str__(self):
        """Return human-readable string representation."""
        return "Plan: {} ({} actions available)".format(
            self.name or 'unnamed',
            len(self._actions_list)
        )


_STEP_REF_RE = re.compile(
    r"\$step_(\d+)(?:_(\d+))?(?:_result|\.([A-Za-z_][A-Za-z0-9_]*))?"
    r"|\{step_(\d+)(?:_(\d+))?(?:_result|\.([A-Za-z_][A-Za-z0-9_]*))?\}"
)


def _lookup_step_reference(match, step_outputs, task_outputs, current_step_idx):
    """Resolve one regex match against completed ``step_outputs`` / ``task_outputs``."""
    if match.group(1) is not None:
        ref_step = int(match.group(1))
        ref_task = int(match.group(2)) if match.group(2) is not None else None
        field = match.group(3)
    else:
        ref_step = int(match.group(4))
        ref_task = int(match.group(5)) if match.group(5) is not None else None
        field = match.group(6)

    if ref_step >= current_step_idx or ref_step not in step_outputs:
        raise KeyError(
            "Step {} cannot reference unavailable step {} output ('{}')".format(
                current_step_idx, ref_step, match.group(0)
            )
        )

    if ref_task is not None:
        if (ref_step, ref_task) not in task_outputs:
            raise KeyError(
                "Step {} Task {} output not found ('{}')".format(
                    ref_step, ref_task, match.group(0)
                )
            )
        base_val = task_outputs[(ref_step, ref_task)]
    else:
        base_val = step_outputs[ref_step]

    if not field:
        return base_val
    if isinstance(base_val, dict) and field in base_val:
        return base_val[field]
    if field == "result":
        return base_val
    raise KeyError(
        "Field '{}' not found on step {} output ({})".format(
            field, ref_step, type(base_val).__name__
        )
    )


def _resolve_plan_params(value, step_outputs, task_outputs, current_step_idx):
    """
    Recursively resolve ``$step_N_result``, ``$step_N.field``, and ``{step_N_result}``
    references inside task parameter values.

    Exact full-string references preserve native Python types (dicts, lists, ints);
    substring references format cleanly into surrounding text.
    """
    if isinstance(value, str):
        stripped = value.strip()
        full_match = _STEP_REF_RE.fullmatch(stripped)
        if full_match is not None:
            return _lookup_step_reference(
                full_match, step_outputs, task_outputs, current_step_idx
            )

        def _sub(m):
            resolved = _lookup_step_reference(
                m, step_outputs, task_outputs, current_step_idx
            )
            if isinstance(resolved, (dict, list)):
                return json.dumps(resolved, ensure_ascii=False, default=str)
            return "" if resolved is None else str(resolved)

        return _STEP_REF_RE.sub(_sub, value)

    if isinstance(value, dict):
        return {
            k: _resolve_plan_params(v, step_outputs, task_outputs, current_step_idx)
            for k, v in value.items()
        }

    if isinstance(value, list):
        return [
            _resolve_plan_params(item, step_outputs, task_outputs, current_step_idx)
            for item in value
        ]

    return value


def _normalize_action_registry(actions):
    """Normalize a dict or iterable of ACTION/TOOL/callables into ``{name: target}``."""
    if isinstance(actions, dict):
        return dict(actions)
    if isinstance(actions, (list, tuple, set)):
        registry = {}
        for item in actions:
            name = getattr(item, "name", None) or getattr(item, "__name__", None) or str(item)
            registry[name] = item
        return registry
    raise TypeError(
        "actions must be a dict or iterable of ACTION/TOOL/callables, got {}".format(
            type(actions).__name__
        )
    )


def _execute_single_plan_task(entry, target_memory, params, clone_action=False):
    """
    Invoke an ``ACTION``, ``TOOL``, or plain Python callable and return ``(ok, result, error)``.
    """
    from thoughtflow.action import ACTION
    from thoughtflow.tool import TOOL

    if isinstance(entry, ACTION):
        runner = entry.copy() if clone_action else entry
        runner(target_memory, **params)
        ok = runner.was_successful()
        err = str(runner.last_error) if runner.last_error is not None else None
        return ok, runner.last_result, err

    if isinstance(entry, TOOL):
        try:
            out = entry(params, context={"memory": target_memory})
            structured_err = ACTION._detect_structured_error(out)
            if structured_err is not None:
                return False, out, structured_err
            return True, out, None
        except Exception as exc:
            return False, None, str(exc)

    if callable(entry):
        try:
            sig = inspect.signature(entry)
            param_names = list(sig.parameters.keys())
            takes_memory = bool(param_names) and param_names[0] in ("memory", "mem")
        except (TypeError, ValueError):
            takes_memory = False

        try:
            if takes_memory:
                out = entry(target_memory, **params)
            else:
                out = entry(**params)
            structured_err = ACTION._detect_structured_error(out)
            if structured_err is not None:
                return False, out, structured_err
            return True, out, None
        except Exception as exc:
            return False, None, str(exc)

    return False, None, "Unsupported action entry of type {}".format(type(entry).__name__)


def run_plan(
    plan,
    memory,
    actions,
    on_error="stop",
    parallel_inner=False,
    max_workers=None,
):
    """
    Execute a ``PLAN`` data structure against ``memory``, resolving inter-step references (#48).

    Supports ``$step_N_result``, ``$step_N.field``, ``$step_N_M_result``, and
    legacy ``{step_N_result}`` parameter references without colliding with
    ``THOUGHT``'s prompt template braces.

    Args:
        plan (list): ``list[list[dict]]`` produced by ``PLAN`` (or a flat
            ``list[dict]`` of sequential tasks).
        memory (MEMORY): ``MEMORY`` instance updated with ``step_{N}_result``
            and ``plan_receipts``.
        actions (dict or list): Mapping of ``{action_name: ACTION | TOOL | callable}``
            or an iterable of named ``ACTION`` / ``TOOL`` / function objects.
        on_error (str): ``'stop'`` (default — halt after a failing step),
            ``'continue'`` (record error receipt and continue), or ``'raise'``
            (raise ``RuntimeError`` on the first task failure).
        parallel_inner (bool): When ``True``, execute multi-task inner steps
            concurrently via ``ThreadPoolExecutor`` over isolated memory copies
            and commit results in deterministic task order.
        max_workers (int, optional): Worker cap when ``parallel_inner=True``.

    Returns:
        list[dict]: Ordered execution receipts, each containing ``step``,
        ``task``, ``action``, ``params``, ``reason``, ``ok``, ``result``,
        ``error``, and ``duration_ms``.

    Example:
        >>> receipts = run_plan(plan, memory, {"search": search_tool, "summarize": sum_fn})
        >>> all(r["ok"] for r in receipts)
        True
    """
    if on_error not in ("stop", "continue", "raise"):
        raise ValueError(
            "on_error must be 'stop', 'continue', or 'raise', got: {!r}".format(on_error)
        )

    registry = _normalize_action_registry(actions)
    if not plan:
        if hasattr(memory, "set_var") and callable(getattr(memory, "set_var", None)):
            memory.set_var("plan_receipts", [], desc="Execution receipts from run_plan")
        return []

    normalized_steps = [
        step if isinstance(step, list) else [step]
        for step in plan
    ]

    receipts = []
    step_outputs = {}
    task_outputs = {}

    for step_idx, step_tasks in enumerate(normalized_steps):
        use_parallel = bool(parallel_inner and len(step_tasks) > 1)

        def _run_task_at(task_idx, task_spec):
            t0 = time.time()
            action_name = task_spec.get("action") if isinstance(task_spec, dict) else None
            raw_params = (task_spec.get("params") or {}) if isinstance(task_spec, dict) else {}
            reason = task_spec.get("reason", "") if isinstance(task_spec, dict) else ""

            if not action_name or action_name not in registry:
                err_msg = "Unknown action: {!r}".format(action_name)
                return {
                    "step": step_idx,
                    "task": task_idx,
                    "action": action_name,
                    "params": raw_params,
                    "reason": reason,
                    "ok": False,
                    "result": None,
                    "error": err_msg,
                    "duration_ms": round((time.time() - t0) * 1000, 2),
                }

            try:
                resolved_params = _resolve_plan_params(
                    raw_params, step_outputs, task_outputs, step_idx
                )
            except Exception as exc:
                return {
                    "step": step_idx,
                    "task": task_idx,
                    "action": action_name,
                    "params": raw_params,
                    "reason": reason,
                    "ok": False,
                    "result": None,
                    "error": str(exc),
                    "duration_ms": round((time.time() - t0) * 1000, 2),
                }

            target_mem = (
                memory.copy()
                if (use_parallel and hasattr(memory, "copy") and callable(getattr(memory, "copy", None)))
                else memory
            )
            ok, res_val, err_msg = _execute_single_plan_task(
                registry[action_name],
                target_mem,
                resolved_params,
                clone_action=use_parallel,
            )
            return {
                "step": step_idx,
                "task": task_idx,
                "action": action_name,
                "params": resolved_params,
                "reason": reason,
                "ok": ok,
                "result": res_val,
                "error": err_msg,
                "duration_ms": round((time.time() - t0) * 1000, 2),
                "_branch_mem": target_mem if target_mem is not memory else None,
            }

        if use_parallel:
            base_vars = (
                memory.get_all_vars(resolve_refs=False)
                if hasattr(memory, "get_all_vars")
                else {}
            )
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = [
                    pool.submit(_run_task_at, t_idx, t_spec)
                    for t_idx, t_spec in enumerate(step_tasks)
                ]
                step_receipts = [f.result() for f in futures]
            for item in step_receipts:
                branch_mem = item.pop("_branch_mem", None)
                if (
                    branch_mem is not None
                    and hasattr(branch_mem, "get_all_vars")
                    and hasattr(memory, "set_var")
                ):
                    for var_k, var_v in branch_mem.get_all_vars().items():
                        if base_vars.get(var_k) != var_v:
                            memory.set_var(var_k, var_v)
        else:
            step_receipts = []
            for t_idx, t_spec in enumerate(step_tasks):
                rec = _run_task_at(t_idx, t_spec)
                rec.pop("_branch_mem", None)
                step_receipts.append(rec)
                if not rec["ok"] and on_error in ("stop", "raise"):
                    break

        step_failed = False
        step_values = []
        for rec in step_receipts:
            receipts.append(rec)
            task_outputs[(step_idx, rec["task"])] = rec["result"]
            step_values.append(rec["result"])
            if hasattr(memory, "set_var") and callable(getattr(memory, "set_var", None)):
                memory.set_var(
                    "step_{}_{}_result".format(step_idx, rec["task"]),
                    rec["result"],
                    desc="Plan step {} task {} output".format(step_idx, rec["task"]),
                )
            if not rec["ok"]:
                step_failed = True
                if on_error == "raise":
                    if hasattr(memory, "set_var") and callable(getattr(memory, "set_var", None)):
                        memory.set_var("plan_receipts", list(receipts), desc="Execution receipts from run_plan")
                    raise RuntimeError(
                        "Plan failed at step {} task {} ('{}'): {}".format(
                            step_idx, rec["task"], rec["action"], rec["error"]
                        )
                    )

        step_summary_val = step_values[0] if len(step_tasks) == 1 and step_values else step_values
        step_outputs[step_idx] = step_summary_val
        if hasattr(memory, "set_var") and callable(getattr(memory, "set_var", None)):
            memory.set_var(
                "step_{}_result".format(step_idx),
                step_summary_val,
                desc="Plan step {} output".format(step_idx),
            )

        if step_failed and on_error == "stop":
            break

    if hasattr(memory, "set_var") and callable(getattr(memory, "set_var", None)):
        memory.set_var("plan_receipts", list(receipts), desc="Execution receipts from run_plan")

    return receipts

