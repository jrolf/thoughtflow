"""
PLAN class for ThoughtFlow.

A specialized THOUGHT subclass for structured multi-step execution planning.
"""

from __future__ import annotations

import json

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

You can reference results from previous steps using {{step_N_result}} in parameter values,
where N is the step index (0-based).

Example:
[
  [{{"action": "search", "params": {{"query": "example"}}, "reason": "Start by gathering relevant information on the topic."}}],
  [{{"action": "analyze", "params": {{"content": "{{step_0_result}}"}}, "reason": "Analyze search results to extract key insights."}}],
  [{{"action": "summarize", "params": {{"text": "{{step_1_result}}"}}, "reason": "Condense findings into actionable summary."}},
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
    
    def validate(self, parsed_result):
        """
        Validate plan structure, action names, and parameters.
        
        Args:
            parsed_result: The parsed plan.
        
        Returns:
            tuple: (is_valid, reason_string)
        """
        # Must be a list
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
        Validate a single task.
        
        Args:
            task: Task dict to validate.
            step_idx: Step index (for error messages).
            task_idx: Task index within step (for error messages).
        
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
            
            # Check required params
            for param_name, param_type in params_schema.items():
                is_optional = param_type.endswith('?')
                
                if not is_optional and param_name not in task_params:
                    return False, "{}: action '{}' requires param '{}'".format(
                        task_loc, action_name, param_name
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
        
        Args:
            why: Reason the previous attempt failed.
        
        Returns:
            str: Repair suffix to append to prompt.
        """
        actions_str = ", ".join(self._actions_list)
        return (
            "\n(Your previous response was invalid: {}. "
            "Return ONLY a valid JSON array. Valid actions are: {}. "
            "Each task must include 'action' and 'reason' fields.)"
        ).format(why, actions_str)
    
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
