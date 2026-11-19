"""
DECIDE class for ThoughtFlow.

A specialized THOUGHT subclass for constrained decision-making across both
generative LLMs (``LLM``) and structured System-One decision models (``DM``).
"""

from __future__ import annotations

import copy
import json
import re
import string
import time

from thoughtflow._util import TemplateRenderError, event_stamp, render_template
from thoughtflow.dm import DM, DecisionError, normalize_questions_spec
from thoughtflow.llm import ReplayMissError
from thoughtflow.thought import THOUGHT, _TEMPLATE_FIELD_RE

_NEGATION_RE = re.compile(
    r"(?:\b(?:do|does|did|would|could|should|can|will|is|are|was|were|must|may|might)?\s*"
    r"(?:not|n't)|"
    r"\b(?:never|no|cannot|can't|won't|don't|doesn't|didn't|shouldn't|wouldn't|couldn't|"
    r"neither|nor|avoid|against|instead\s+of|rather\s+than))\s*$",
    re.IGNORECASE,
)

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _extract_simple_template_pointers(template_str, ctx):
    """
    Parse ``template_str`` for simple ``{identifier}`` placeholders present in ``ctx``.

    Uses ``string.Formatter().parse`` so repeated placeholders (``"{x} vs {x}"``)
    and escaped double braces (``"{{literal}}"``) are handled accurately without
    fragile brace-counting regexes.

    Returns:
        tuple: ``(ordered_var_names, backticked_instructions)`` when every format
        field in ``template_str`` is a plain identifier present in ``ctx``; or
        ``(None, None)`` when ``template_str`` contains complex expressions
        (e.g. ``{item[0]}``) or unescaped braces in ``substitute`` mode.
    """
    seen_vars = []
    parts = []
    try:
        for literal_text, field_name, format_spec, conversion in string.Formatter().parse(template_str):
            if literal_text:
                parts.append(literal_text)
            if field_name is None:
                continue
            if format_spec or conversion or not _IDENT_RE.match(field_name) or field_name not in ctx:
                return None, None
            if field_name not in seen_vars:
                seen_vars.append(field_name)
            parts.append("`{}`".format(field_name))
    except ValueError:
        return None, None

    return seen_vars, "".join(parts)


class DECIDE(THOUGHT):
    """
    A decision step that produces a typed, constrained judgment from an ``LLM`` or ``DM``.

    ``DECIDE`` presents a bounded decision schema to a model and writes the clean
    decision value to ``{name}_result`` alongside rich telemetry in
    ``{name}_outcome``. It works identically with generative ``LLM`` instances
    (using prompt construction, smart parsing, validation, and choice-specific
    repair retries) and structured ``DM`` decision models (executing a single
    forward pass with calibrated probability distributions and zero text parsing).

    Supported decision modes:
        1. **Categorical choice** (default): ``choices=["approve", "reject"]`` or
           ``choices={"approve": "Accept request", "reject": "Deny request"}``.
           Stores the selected option string in ``{name}_result``.
        2. **Binary evaluation (``noul``)**: ``choices=bool`` (or ``kind="noul"``)
           with optional ``threshold=0.5``. Stores ``True`` or ``False`` in
           ``{name}_result`` and the calibrated probability $P(\\text{true})$ in
           ``{name}_outcome["probability"]``.
        3. **Ordered rubric (``score``)**: ``levels=["Low", "Medium", "High"]``.
           Stores a continuous float score in ``[0.0, K - 1.0]`` in ``{name}_result``.
        4. **Multi-question batch**: ``questions={"dept": {...}, "urgent": {...}}``.
           Evaluates multiple independent questions over shared state in one pass
           and stores ``{question_id: value}`` in ``{name}_result``.

    Args:
        name (str): Unique identifier for this decision.
        llm (LLM or DM): Model instance (``model=`` is accepted as an alias).
        prompt (str or dict): Prompt / instruction template with ``{variable}``
            placeholders.
        choices (list, dict, or type[bool]): Allowed options for choice mode, or
            ``bool`` for binary ``noul`` evaluation.
        levels (list, optional): Ordered rubric descriptions (lowest to highest)
            for ``score`` mode.
        questions (dict, optional): Multi-question specification map for batched
            single-pass evaluation.
        state (str, list, or dict, optional): Controls how ``DM`` state is built:
            - ``"auto"`` (default): lifts ``{var}`` placeholders referenced in
              ``prompt`` into a structured ``state`` dict and rewrites ``{var}`` to
              backticked `` `var` `` in ``instructions`` so untrusted data stays
              separate from instructions.
            - ``list[str]``: explicit list of ``MEMORY`` variable names to pack
              into ``state`` while rendering ``prompt`` as ``instructions``.
            - ``dict``: template dict rendered from ``MEMORY`` context.
        threshold (float): Probability cutoff for ``choices=bool`` / ``noul``
            questions (default ``0.5``).
        min_confidence (float, optional): Minimum normalized ``confidence`` in
            ``[0, 1]`` required to accept a ``DM`` answer; below this cutoff
            ``DECIDE`` substitutes ``default`` and sets ``source='low_confidence'``.
        min_margin (float, optional): Minimum top-2 probability gap
            (``p_top1 - p_top2``) required to accept a ``DM`` answer.
        default: Fallback value used when retries exhaust, the model refuses, or
            confidence/margin falls below threshold.
        case_sensitive (bool): Case-sensitive choice matching on ``LLM`` path
            (default ``False``).
        max_retries (int): Maximum attempts (default ``5``). On ``DM`` calls,
            only transient network/5xx/429 errors retry; deterministic 4xx errors
            and refusals return in 1 attempt.
        **kwargs: Additional ``THOUGHT`` parameters.
    """

    def __init__(self, name=None, llm=None, prompt=None, choices=None, **kwargs):
        """Initialize a DECIDE instance."""
        model_alias = kwargs.pop("model", None)
        if llm is None and model_alias is not None:
            llm = model_alias

        levels = kwargs.pop("levels", None)
        questions = kwargs.pop("questions", None)
        kind_override = kwargs.pop("kind", None)

        self.default = kwargs.pop("default", None)
        self.case_sensitive = kwargs.pop("case_sensitive", False)
        self.threshold = float(kwargs.pop("threshold", 0.5))
        self.min_confidence = kwargs.pop("min_confidence", None)
        self.min_margin = kwargs.pop("min_margin", None)
        self.state_spec = kwargs.pop("state", "auto")

        raw_abstain = kwargs.pop("abstain", False)
        if raw_abstain is False or raw_abstain is None:
            self.abstain = False
            self._abstain_token = None
        elif raw_abstain is True:
            self.abstain = True
            self._abstain_token = "none"
        elif isinstance(raw_abstain, str) and raw_abstain.strip():
            self.abstain = raw_abstain.strip()
            self._abstain_token = self.abstain
        else:
            raise ValueError("'abstain' must be a bool or non-empty str")

        self.levels = None
        self.questions = None

        if questions is not None:
            self.questions = normalize_questions_spec(questions)
            self.decide_mode = "multi"
            self.choices = None
            self._choices_list = list(self.questions.keys())
            self._choices_descriptions = {}
        elif (
            choices is bool
            or choices == "bool"
            or kind_override is bool
            or kind_override in ("noul", "predicate", "bool", "boolean")
        ):
            self.decide_mode = "noul"
            self.choices = "bool"
            self._choices_list = ["true", "false"]
            self._choices_descriptions = {}
        elif levels is not None and choices is None:
            if not isinstance(levels, (list, tuple)) or not levels:
                raise ValueError("'levels' must be a non-empty list of ordered rubric descriptions")
            self.decide_mode = "score"
            self.levels = list(levels)
            self.choices = None
            self._choices_list = [str(i) for i in range(len(self.levels))]
            self._choices_descriptions = {
                str(i): str(desc) for i, desc in enumerate(self.levels)
            }
        else:
            if choices is None:
                raise ValueError("DECIDE requires 'choices' parameter (or 'levels' / 'questions')")
            if isinstance(choices, dict):
                self._choices_list = list(choices.keys())
                self._choices_descriptions = dict(choices)
            elif isinstance(choices, (list, tuple)):
                self._choices_list = list(choices)
                self._choices_descriptions = {}
            else:
                raise ValueError(
                    "'choices' must be a list or dict (or bool), got: {}".format(
                        type(choices).__name__
                    )
                )
            if not self._choices_list:
                raise ValueError("'choices' cannot be empty")
            self.decide_mode = "choice"
            self.choices = copy.deepcopy(choices)
            if self._abstain_token is not None:
                existing_norm = {
                    (c if self.case_sensitive else str(c).strip().lower())
                    for c in self._choices_list
                }
                token_norm = (
                    self._abstain_token
                    if self.case_sensitive
                    else self._abstain_token.lower()
                )
                if token_norm not in existing_norm:
                    self._choices_list.append(self._abstain_token)
                if self._choices_descriptions:
                    self._choices_descriptions.setdefault(
                        self._abstain_token,
                        "None of the provided options apply (abstain)",
                    )

        if "max_retries" not in kwargs:
            kwargs["max_retries"] = 5

        kwargs["operation"] = "llm_call"
        self._last_decision_meta = None
        self._has_fallback_result = False
        self._fallback_result = None

        super().__init__(name=name, llm=llm, prompt=prompt, **kwargs)

    def _is_decision_model(self):
        """Return True when ``self.llm`` is a structured Decision Model (``DM``)."""
        return bool(getattr(self.llm, "is_decision_model", False))

    def _referenced_template_vars(self):
        """Include variables referenced by ``state`` and ``questions`` for lazy ``_obj_ref`` resolution."""
        referenced = super()._referenced_template_vars()
        if referenced is None:
            return None

        if isinstance(self.state_spec, (list, tuple)):
            referenced.update(str(k) for k in self.state_spec)
        elif isinstance(self.state_spec, dict):
            for val in self.state_spec.values():
                if isinstance(val, str):
                    referenced.update(_TEMPLATE_FIELD_RE.findall(val))
        elif isinstance(self.state_spec, str) and self.state_spec != "auto":
            referenced.update(_TEMPLATE_FIELD_RE.findall(self.state_spec))

        if isinstance(self.questions, dict):
            for qspec in self.questions.values():
                if not isinstance(qspec, dict):
                    continue
                instr = qspec.get("instructions", qspec.get("prompt"))
                if isinstance(instr, str):
                    referenced.update(_TEMPLATE_FIELD_RE.findall(instr))

        return referenced

    # ------------------------------------------------------------------ #
    # Generative LLM path (prompt formatting, parsing, validation)
    # ------------------------------------------------------------------ #

    def _is_abstain_value(self, value):
        """Return ``True`` when ``value`` matches the configured ``abstain`` token."""
        if self._abstain_token is None or not isinstance(value, str):
            return False
        if self.case_sensitive:
            return value.strip() == self._abstain_token
        return value.strip().lower() == self._abstain_token.lower()

    def build_prompt(self, memory, context_vars=None):
        """Build prompt with formatted choices appended for generative LLMs."""
        base_prompt = super().build_prompt(memory, context_vars)
        choices_section = self._format_choices()
        if self._abstain_token is not None and self.decide_mode == "choice":
            instruction = (
                "\n\nIf none of the options apply, respond with '{}'. "
                "Respond with only your choice, nothing else."
            ).format(self._abstain_token)
        else:
            instruction = "\n\nRespond with only your choice, nothing else."
        return base_prompt + "\n\n" + choices_section + instruction

    def _format_choices(self):
        """Format choices as a bullet list for generative LLM prompts."""
        if self._choices_descriptions:
            lines = [
                "- {}: {}".format(choice, desc)
                for choice, desc in self._choices_descriptions.items()
            ]
        else:
            lines = ["- {}".format(choice) for choice in self._choices_list]
        return "Choose one of:\n" + "\n".join(lines)

    def parse_response(self, response):
        """
        Extract an unambiguous chosen option from a generative LLM response.

        Attempts matching in order:
        1. Exact match after stripping surrounding whitespace, quotes,
           markdown emphasis, and trailing punctuation.
        2. Leading choice token at the very start of the response, preferring
           longest match first (without treating decimal points like ``1.5`` as
           trailing periods on numeric choices).
        3. Unambiguous embedded match: exactly one distinct non-overlapping
           choice appears on word boundaries and is not immediately negated.
        """
        text = str(response or "").strip()
        if not text:
            return text

        def normalize(s):
            return s.lower().strip() if not self.case_sensitive else s.strip()

        cleaned = text.strip(" \t\r\n\"'`*_.")
        normalized_cleaned = normalize(cleaned)
        sorted_choices = sorted(self._choices_list, key=len, reverse=True)

        for choice in sorted_choices:
            if normalize(choice) == normalized_cleaned or normalize(choice) == normalize(text):
                return choice

        flags = 0 if self.case_sensitive else re.IGNORECASE

        leading = text.lstrip(" \t\r\n\"'`*_")
        for choice in sorted_choices:
            lead_pat = re.compile(
                r"^" + re.escape(choice) + r"(?=$|[\s,:;!\?\)\]\}\"'`*_—\-]|\.(?!\d))",
                flags,
            )
            if lead_pat.match(leading):
                return choice

        occupied_spans = []
        matched_choices = []

        for choice in sorted_choices:
            pat = re.compile(
                r"(?<!\d\.)(?<![A-Za-z0-9_])" + re.escape(choice) + r"(?![A-Za-z0-9_]|\.\d)",
                flags,
            )
            choice_hits = []
            negated = False
            for m in pat.finditer(text):
                start, end = m.span()
                if any(not (end <= s or start >= e) for s, e in occupied_spans):
                    continue
                prefix = text[max(0, start - 32):start]
                if _NEGATION_RE.search(prefix):
                    negated = True
                    occupied_spans.append((start, end))
                    continue
                choice_hits.append((start, end))
                occupied_spans.append((start, end))

            if negated:
                return text
            if choice_hits:
                matched_choices.append(choice)

        if len(matched_choices) == 1:
            return matched_choices[0]

        return text

    def validate(self, parsed_result):
        """Validate that ``parsed_result`` matches one of the allowed choices."""
        def normalize(s):
            return s.lower().strip() if not self.case_sensitive else s.strip()

        normalized = normalize(str(parsed_result))
        for choice in self._choices_list:
            if normalize(choice) == normalized:
                return True, ""

        return False, "Not a valid choice. Must be one of: {}".format(self._choices_list)

    def _prepare_and_validate(self, parsed_result):
        """Validate and coerce LLM choices for ``noul`` (bool) and ``score`` (float) modes."""
        valid, why = self.validate(parsed_result)
        if not valid:
            return parsed_result, False, why

        if self.decide_mode == "noul":
            return str(parsed_result).strip().lower() == "true", True, ""
        if self.decide_mode == "score":
            return float(str(parsed_result).strip()), True, ""
        return parsed_result, True, ""

    def _build_repair_suffix(self, why):
        """Build choice-specific repair prompt for generative LLM retries."""
        choices_str = ", ".join(self._choices_list)
        return "\n(Respond with exactly one of: {}. No other text.)".format(choices_str)

    # ------------------------------------------------------------------ #
    # Decision Model (DM) execution path
    # ------------------------------------------------------------------ #

    def _build_dm_state_and_instructions(self, memory, vars_dict):
        """
        Construct ``(state, instructions, ctx)`` for a Decision Model call.

        In default ``state="auto"`` mode, simple ``{var}`` placeholders in
        ``prompt`` are lifted into a structured ``state`` dict while ``prompt``
        is rewritten with backticked `` `var` `` field pointers so untrusted
        input data stays separated from question instructions.
        """
        ctx = self.get_context(memory)
        if vars_dict:
            ctx.update(vars_dict)
        self._validate_required_vars(ctx)

        sys_prompt = self.config.get("system_prompt", "")
        rendered_sys = (
            self._render_template_value(sys_prompt, ctx).strip() if sys_prompt else ""
        )

        # Explicit state_spec: list of var names, dict template, or custom string template.
        if self.state_spec != "auto":
            if isinstance(self.state_spec, (list, tuple)):
                state_obj = {
                    k: (ctx[k] if k in ctx else memory.get_var(k))
                    for k in self.state_spec
                }
            elif isinstance(self.state_spec, dict):
                state_obj = {
                    k: (self._render_template_value(v, ctx) if isinstance(v, str) else v)
                    for k, v in self.state_spec.items()
                }
            else:
                state_obj = self._render_template_value(self.state_spec, ctx)

            instr = self._render_template_value(self.prompt, ctx) if self.prompt else ""
            if rendered_sys:
                instr = (rendered_sys + "\n" + instr).strip()
            return state_obj, instr, ctx

        # Default state="auto": validate template rendering first so missing
        # placeholders fail loudly as TemplateRenderError in format mode.
        if isinstance(self.prompt, str) and self.prompt:
            rendered_prompt = render_template(self.prompt, ctx, self._template_mode())
            simple_vars, pointer_instr = _extract_simple_template_pointers(self.prompt, ctx)

            if simple_vars:
                state_obj = {k: ctx[k] for k in simple_vars}
                if self._include_history() and hasattr(memory, "get_llm_msgs"):
                    prior = list(memory.get_llm_msgs())
                    if len(prior) > 1 and "messages" not in state_obj and "history" not in state_obj:
                        state_obj["history"] = prior
                instr = (rendered_sys + "\n" + pointer_instr).strip() if rendered_sys else pointer_instr
                return state_obj, instr, ctx

            if simple_vars is not None:
                # Prompt has zero placeholders (pure directive); supply history or shallow vars.
                prior = list(memory.get_llm_msgs()) if (self._include_history() and hasattr(memory, "get_llm_msgs")) else []
                if prior:
                    state_obj = prior
                elif hasattr(memory, "get_all_vars"):
                    state_obj = memory.get_all_vars(resolve_refs=False)
                else:
                    state_obj = {}
                instr = (rendered_sys + "\n" + rendered_prompt).strip() if rendered_sys else rendered_prompt
                return state_obj, instr, ctx

            # Complex format expression (e.g. {item[0]}): fall back to rendered_prompt as state.
            instr = rendered_sys or "Select the best answer for the state."
            return rendered_prompt, instr, ctx

        if isinstance(self.prompt, dict):
            rendered_prompt = self._render_template_value(self.prompt, ctx)
            instr = rendered_sys or "Select the best answer for the state."
            return rendered_prompt, instr, ctx

        # No top-level prompt (common in multi-question mode): lift any {var}
        # placeholders referenced across question instructions, else history/vars.
        if self.decide_mode == "multi" and isinstance(self.questions, dict):
            q_vars = []
            for qspec in self.questions.values():
                if not isinstance(qspec, dict):
                    continue
                q_instr = qspec.get("instructions", qspec.get("prompt"))
                if isinstance(q_instr, str) and q_instr:
                    render_template(q_instr, ctx, self._template_mode())
                    found, _ = _extract_simple_template_pointers(q_instr, ctx)
                    for k in found or ():
                        if k not in q_vars:
                            q_vars.append(k)
            if q_vars:
                return {k: ctx[k] for k in q_vars}, (rendered_sys or ""), ctx

        prior = list(memory.get_llm_msgs()) if (self._include_history() and hasattr(memory, "get_llm_msgs")) else []
        if prior:
            state_obj = prior
        elif hasattr(memory, "get_all_vars"):
            state_obj = memory.get_all_vars(resolve_refs=False)
        else:
            state_obj = {}
        return state_obj, (rendered_sys or "Evaluate the state."), ctx

    def _build_dm_questions(self, instructions, ctx, state_obj):
        """Build the question map sent to ``DM.call``."""
        qkey = self.name or "decision"

        if self.decide_mode == "multi":
            qmap = {}
            state_is_dict = isinstance(state_obj, dict)
            for k, spec in self.questions.items():
                item = copy.deepcopy(spec)
                raw_instr = item.get("instructions", item.get("prompt"))
                if isinstance(raw_instr, str) and raw_instr:
                    render_template(raw_instr, ctx, self._template_mode())
                    found, pointer_instr = _extract_simple_template_pointers(raw_instr, ctx)
                    if found and state_is_dict and all(v in state_obj for v in found):
                        item["instructions"] = pointer_instr
                    else:
                        item["instructions"] = self._render_template_value(raw_instr, ctx)
                elif instructions and not raw_instr:
                    item["instructions"] = instructions
                qmap[k] = item
            return qmap

        if self.decide_mode == "noul":
            return {qkey: {"type": "noul", "instructions": instructions}}

        if self.decide_mode == "score":
            return {
                qkey: {
                    "type": "score",
                    "instructions": instructions,
                    "levels": list(self.levels),
                }
            }

        crit = self._choices_descriptions if self._choices_descriptions else self._choices_list
        return {
            qkey: {
                "type": "choice",
                "instructions": instructions,
                "choices": crit,
            }
        }

    def _passes_uncertainty_gate(self, ans):
        """Return ``True`` when ``ans`` satisfies configured ``min_confidence`` and ``min_margin``."""
        if self.min_confidence is not None:
            conf = ans.get("confidence")
            if conf is None or conf < self.min_confidence:
                return False
        if self.min_margin is not None:
            margin = ans.get("margin")
            if margin is None or margin < self.min_margin:
                return False
        return True

    def _accumulate_dm_usage(self, dm_usage):
        """Accumulate normalized ``DM`` usage across retries or ``fallback_llm`` failover."""
        if not isinstance(dm_usage, dict):
            return
        if self._last_call_usage is None:
            self._last_call_usage = dict(dm_usage)
            return
        self._last_call_usage["prompt_tokens"] = (
            self._last_call_usage.get("prompt_tokens", 0)
            + dm_usage.get("prompt_tokens", 0)
        )
        self._last_call_usage["completion_tokens"] = (
            self._last_call_usage.get("completion_tokens", 0)
            + dm_usage.get("completion_tokens", 0)
        )
        if "cost" in dm_usage and dm_usage["cost"] is not None:
            self._last_call_usage["cost"] = (
                (self._last_call_usage.get("cost") or 0) + dm_usage["cost"]
            )

    def _finalize_dm_side_effects(self, memory, result_val):
        """Apply ``THOUGHT`` parity side effects (``visibility``, ``add_reflection``, ``record_prompt``)."""
        channel = self.config.get("channel", "api")
        if result_val is not None:
            rendered_reply = (
                json.dumps(result_val)
                if isinstance(result_val, (dict, list))
                else str(result_val)
            )
            if hasattr(memory, "add_msg") and callable(getattr(memory, "add_msg", None)):
                self._add_assistant_msg(memory, rendered_reply, channel)
            if self.config.get("add_reflection", False):
                if hasattr(memory, "add_ref") and callable(getattr(memory, "add_ref", None)):
                    preview = rendered_reply[:300]
                    if len(rendered_reply) > 300:
                        preview += "..."
                    memory.add_ref("Thought '{}': {}".format(self.name, preview))

        if (
            self.record_prompt
            and self.name
            and result_val is not None
            and self.last_prompt is not None
            and hasattr(memory, "set_var")
            and callable(getattr(memory, "set_var", None))
        ):
            memory.set_var(
                "{}_prompt".format(self.name),
                self.last_prompt,
                desc="Rendered prompt for thought: {}".format(self.name),
            )

    def _maybe_run_fallback(self, memory, vars, res, err, attempts, **kwargs):
        """
        Execute ``retry['fallback_llm']`` for a single rescue attempt after primary exhaustion.

        Clears stale ``_last_decision_meta`` from any primary refusal so generative
        ``LLM`` fallbacks build fresh outcomes, caps the backup run at 1 attempt,
        and preserves primary ``_failure_attempts`` history.
        """
        fallback = (self.retry or {}).get("fallback_llm")
        last_kind = (
            self._failure_attempts[-1].get("failure_kind")
            if self._failure_attempts
            else None
        )
        if (
            res is not None
            or err is None
            or fallback is None
            or self._used_fallback_llm
            or last_kind in ("template", "replay_miss")
        ):
            return res, err, attempts

        self._used_fallback_llm = True
        self._last_decision_meta = None
        self._has_fallback_result = False
        self._fallback_result = None

        saved_failures = list(self._failure_attempts)
        saved_max_retries = self.max_retries
        primary_llm = self.llm
        try:
            self.llm = fallback
            self.max_retries = 1
            if getattr(fallback, "is_decision_model", False):
                res2, err2, attempts2 = self._execute_dm_call(
                    memory, vars, dm_client=fallback, attempt_offset=attempts, **kwargs
                )
            elif self.decide_mode == "multi":
                res2, err2, attempts2 = self._execute_dm_call(
                    memory, vars, dm_client=DM.from_llm(fallback), attempt_offset=attempts, **kwargs
                )
            else:
                res2, err2, attempts2 = super()._execute_llm_call(memory, vars, **kwargs)
                # super()._execute_llm_call resets _failure_attempts; restore primary history
                # and offset any fallback failure attempt numbers.
                fb_failures = []
                for entry in self._failure_attempts:
                    shifted = dict(entry)
                    shifted["attempt"] = attempts + int(shifted.get("attempt", 1))
                    fb_failures.append(shifted)
                self._failure_attempts = saved_failures + fb_failures
                if (
                    res2 is None
                    and err2 is not None
                    and self.name
                    and hasattr(memory, "set_var")
                    and callable(getattr(memory, "set_var", None))
                ):
                    final_kind = (
                        self._failure_attempts[-1].get("failure_kind", "exception")
                        if self._failure_attempts
                        else "exception"
                    )
                    memory.set_var(
                        "{}_last_error".format(self.name),
                        {
                            "reason": err2,
                            "failure_kind": final_kind,
                            "attempts": list(self._failure_attempts),
                        },
                        desc="Last error for thought: {}".format(self.name),
                    )
                    memory.set_var(
                        "{}_attempts".format(self.name),
                        attempts + attempts2,
                        desc="Attempts for thought: {}".format(self.name),
                    )
            return res2, err2, attempts + attempts2
        finally:
            self.llm = primary_llm
            self.max_retries = saved_max_retries

    def _execute_llm_call(self, memory, vars, **kwargs):
        """Route to ``DM`` execution when ``self.llm`` is a decision model (or ``multi`` mode)."""
        self.last_result = None
        self._last_decision_meta = None
        self._has_fallback_result = False
        self._fallback_result = None

        if self._is_decision_model() or self.decide_mode == "multi":
            if self.llm is None:
                raise ValueError("No LLM or DM instance provided to this DECIDE.")
            primary_client = (
                self.llm if self._is_decision_model() else DM.from_llm(self.llm)
            )
            res, err, attempts = self._execute_dm_call(
                memory, vars, dm_client=primary_client, **kwargs
            )
            return self._maybe_run_fallback(memory, vars, res, err, attempts, **kwargs)

        return super()._execute_llm_call(memory, vars, **kwargs)

    def _execute_dm_call(self, memory, vars, dm_client, attempt_offset=0, **kwargs):
        """Execute a single-pass Decision Model evaluation with transient-only retry."""
        if dm_client is None:
            raise ValueError("No DM or LLM instance provided to this DECIDE.")

        attempts_made = 0
        http_failures = 0
        max_attempts = max(1, int(self.max_retries or 1))
        call_params = dict(self.config.get("llm_params", {}))
        call_params.update(kwargs)

        try:
            state_obj, instructions, ctx = self._build_dm_state_and_instructions(memory, vars)
            qmap = self._build_dm_questions(instructions, ctx, state_obj)
            self.last_prompt = instructions if instructions else json.dumps(qmap, default=str)
        except TemplateRenderError as exc:
            err = str(exc)
            self.last_error = err
            self._record_failure(memory, attempt_offset + 1, "template", err, raw_response=None)
            return None, err, 1

        dm_res = None
        last_error = None
        while attempts_made < max_attempts:
            attempts_made += 1
            global_attempt = attempt_offset + attempts_made
            try:
                dm_res = dm_client.call(state_obj, qmap, params=call_params or None)
                break
            except ReplayMissError as exc:
                last_error = str(exc)
                self.last_error = last_error
                self._record_failure(memory, global_attempt, "replay_miss", last_error, raw_response=None)
                return None, last_error, attempts_made
            except DecisionError as exc:
                last_error = str(exc)
                self.last_error = last_error
                self._record_failure(memory, global_attempt, "http", last_error, raw_response=exc.body or None)
                if not exc.retryable or attempts_made >= max_attempts:
                    return None, last_error, attempts_made
                http_failures += 1
                self._backoff_sleep(http_failures)
                if self.retry_delay:
                    time.sleep(self.retry_delay)
            except Exception as exc:
                last_error = str(exc)
                self.last_error = last_error
                self._record_failure(memory, global_attempt, "exception", last_error, raw_response=None)
                return None, last_error, attempts_made

        dm_usage = dm_res.get("usage")
        self._accumulate_dm_usage(dm_usage)
        self._emit_usage_event(memory, dm_usage, client=dm_client)
        self.last_response = dm_res

        if self.decide_mode == "multi":
            values = {}
            raw_values = {}
            gated_any = False
            refused_keys = []
            for k, ans in dm_res["answers"].items():
                if ans["type"] == "refusal":
                    refused_keys.append(k)
                    raw_values[k] = None
                    values[k] = (
                        self.default.get(k) if isinstance(self.default, dict) else self.default
                    )
                else:
                    un_gated = (
                        (ans["probability"] >= self.threshold)
                        if ans["type"] == "noul"
                        else ans["value"]
                    )
                    raw_values[k] = un_gated
                    if self._passes_uncertainty_gate(ans):
                        values[k] = un_gated
                    else:
                        gated_any = True
                        values[k] = (
                            self.default.get(k) if isinstance(self.default, dict) else self.default
                        )

            if refused_keys:
                why = "Decision model refused question(s): {}".format(", ".join(refused_keys))
                self.last_error = why
                self._last_finish_reason = "refusal"
                fallback_out = values if self.default is not None else None
                self._has_fallback_result = True
                self._fallback_result = fallback_out
                self._last_decision_meta = {
                    "source": "default" if self.default is not None else "refusal",
                    "stored_value": fallback_out,
                    "raw_value": raw_values,
                    "answers": dm_res["answers"],
                    "model": dm_res.get("model"),
                }
                self._record_failure(
                    memory, attempt_offset + attempts_made, "refusal", why, raw_response=None
                )
                return None, why, attempts_made

            self._last_finish_reason = "stop"
            self.last_result = values
            self.last_error = None
            self._last_decision_meta = {
                "source": "low_confidence" if gated_any else "model",
                "stored_value": values,
                "raw_value": raw_values,
                "answers": dm_res["answers"],
                "model": dm_res.get("model"),
            }
            self._finalize_dm_side_effects(memory, values)
            return values, None, attempts_made

        qkey = self.name or "decision"
        ans = dm_res["answers"][qkey]

        if ans["type"] == "refusal":
            why = "Decision model refused question '{}'".format(qkey)
            self.last_error = why
            self._last_finish_reason = "refusal"
            self._last_decision_meta = {
                "source": "default" if self.default is not None else "refusal",
                "stored_value": self.default,
                "raw_value": None,
                "probability": None,
                "probabilities": None,
                "confidence": None,
                "provider_confidence": None,
                "margin": None,
                "model": dm_res.get("model"),
            }
            self._record_failure(
                memory, attempt_offset + attempts_made, "refusal", why, raw_response=None
            )
            return None, why, attempts_made

        raw_val = (
            (ans["probability"] >= self.threshold)
            if self.decide_mode == "noul"
            else ans["value"]
        )
        passed_gate = self._passes_uncertainty_gate(ans)
        abstained = False
        if passed_gate:
            if self._is_abstain_value(raw_val):
                final_val = self._abstain_token
                source = "abstain"
                abstained = True
            else:
                final_val = raw_val
                source = "model"
        else:
            if self.default is not None:
                final_val = self.default
                source = "low_confidence"
            elif self._abstain_token is not None:
                final_val = self._abstain_token
                source = "abstain"
                abstained = True
            else:
                final_val = None
                source = "low_confidence"

        self._last_finish_reason = "stop"
        self.last_result = final_val
        self.last_error = None
        self._last_decision_meta = {
            "source": source,
            "abstained": abstained,
            "stored_value": final_val,
            "raw_value": raw_val,
            "probability": ans.get("probability"),
            "probabilities": ans.get("probabilities"),
            "confidence": ans.get("confidence"),
            "provider_confidence": ans.get("provider_confidence"),
            "margin": ans.get("margin"),
            "legend": ans.get("legend"),
            "model": dm_res.get("model"),
        }
        self._finalize_dm_side_effects(memory, final_val)
        return final_val, None, attempts_made

    # ------------------------------------------------------------------ #
    # Outcome, memory update, and serialization
    # ------------------------------------------------------------------ #

    def _build_outcome(
        self,
        ok,
        attempts,
        error_class=None,
        error=None,
        finish_reason=None,
        usage=None,
        validation_messages=None,
    ):
        """Enrich ``THOUGHT._build_outcome`` with decision provenance and probabilities."""
        outcome = super()._build_outcome(
            ok=ok,
            attempts=attempts,
            error_class=error_class,
            error=error,
            finish_reason=finish_reason,
            usage=usage,
            validation_messages=validation_messages,
        )

        meta = self._last_decision_meta
        if meta is not None:
            outcome.update({
                "kind": self.decide_mode,
                "value": meta.get("stored_value"),
                "raw_value": meta.get("raw_value"),
                "source": meta.get("source"),
                "abstained": bool(meta.get("abstained", False)),
                "probability": meta.get("probability"),
                "probabilities": meta.get("probabilities"),
                "confidence": meta.get("confidence"),
                "provider_confidence": meta.get("provider_confidence"),
                "margin": meta.get("margin"),
            })
            if meta.get("legend") is not None:
                outcome["legend"] = meta["legend"]
            if meta.get("answers") is not None:
                outcome["answers"] = meta["answers"]
            if meta.get("model") is not None:
                outcome["model"] = meta["model"]
        else:
            # Generative LLM path (or pre-call template/HTTP error): distinguish
            # model choice, explicit abstention, and fallback default.
            abstained = False
            if ok:
                if self._is_abstain_value(self.last_result):
                    source = "abstain"
                    abstained = True
                    val = self._abstain_token
                else:
                    source = "model"
                    val = self.last_result
            elif self.default is not None:
                source = "default"
                val = self.default
            else:
                source = "error"
                val = None
            outcome.update({
                "kind": self.decide_mode,
                "value": val,
                "raw_value": self.last_result if ok else None,
                "source": source,
                "abstained": abstained,
                "probability": None,
                "probabilities": None,
                "confidence": None,
                "provider_confidence": None,
                "margin": None,
            })

        return outcome

    def _write_extra_outcome_vars(self, memory):
        """Record ``{name}_source`` on ``MEMORY`` alongside ``{name}_outcome``."""
        if (
            self.name
            and isinstance(self.last_outcome, dict)
            and hasattr(memory, "set_var")
            and callable(getattr(memory, "set_var", None))
        ):
            memory.set_var(
                "{}_source".format(self.name),
                self.last_outcome.get("source"),
                desc="Decision provenance for: {}".format(self.name),
            )

    def update_memory(self, memory, result):
        """Store result in memory, substituting fallback/``default`` when ``result`` is ``None``."""
        if result is None:
            if self._has_fallback_result:
                result = self._fallback_result
            elif self.default is not None:
                result = self.default
        self.last_result = result
        return super().update_memory(memory, result)

    def to_dict(self):
        """Return a JSON-serializable dictionary representation of this DECIDE."""
        data = super().to_dict()
        serializable_state = (
            copy.deepcopy(self.state_spec)
            if isinstance(self.state_spec, (str, list, dict))
            else "auto"
        )
        data.update({
            "choices": copy.deepcopy(self.choices),
            "levels": copy.deepcopy(self.levels) if self.levels is not None else None,
            "questions": copy.deepcopy(self.questions) if self.questions is not None else None,
            "default": copy.deepcopy(self.default),
            "abstain": self.abstain,
            "case_sensitive": self.case_sensitive,
            "threshold": self.threshold,
            "min_confidence": self.min_confidence,
            "min_margin": self.min_margin,
            "state": serializable_state,
            "decide_mode": self.decide_mode,
            "_class": "DECIDE",
        })
        return data

    @classmethod
    def from_dict(
        cls,
        data,
        llm=None,
        model=None,
        parse_fn=None,
        validation=None,
        pre_hook=None,
        post_hook=None,
        fallback_llm=None,
        **kwargs,
    ):
        """Reconstruct a DECIDE instance from a dictionary representation."""
        config = dict(data.get("config") or {})
        config_validation = config.pop("validation", None)
        for key in (
            "name",
            "llm",
            "model",
            "prompt",
            "operation",
            "description",
            "max_retries",
            "retry_delay",
            "output_var",
            "required_vars",
            "optional_vars",
            "parse_fn",
            "pre_hook",
            "post_hook",
            "default",
            "abstain",
            "case_sensitive",
            "levels",
            "questions",
            "threshold",
            "min_confidence",
            "min_margin",
            "state",
            "kind",
        ):
            config.pop(key, None)

        config.update(kwargs)
        effective_validation = (
            validation
            if validation is not None
            else (data.get("validation") if data.get("validation") is not None else config_validation)
        )
        raw_choices = data.get("choices")
        choices_arg = bool if raw_choices == "bool" else raw_choices

        inst = cls(
            name=data.get("name"),
            llm=llm if llm is not None else model,
            prompt=data.get("prompt"),
            choices=choices_arg,
            levels=data.get("levels"),
            questions=data.get("questions"),
            default=data.get("default"),
            abstain=data.get("abstain", False),
            case_sensitive=data.get("case_sensitive", False),
            threshold=data.get("threshold", 0.5),
            min_confidence=data.get("min_confidence"),
            min_margin=data.get("min_margin"),
            state=data.get("state", "auto"),
            max_retries=data.get("max_retries", 5),
            description=data.get("description"),
            retry_delay=data.get("retry_delay", 0),
            output_var=data.get("output_var"),
            required_vars=data.get("required_vars", []),
            optional_vars=data.get("optional_vars", []),
            parse_fn=parse_fn,
            validation=effective_validation,
            pre_hook=pre_hook,
            post_hook=post_hook,
            **config,
        )
        if fallback_llm is not None:
            inst.retry["fallback_llm"] = fallback_llm
        if data.get("id"):
            inst.id = data["id"]
        inst.execution_history = copy.deepcopy(data.get("execution_history", []))
        return inst

    def copy(self):
        """Return an independent deep copy of this DECIDE sharing the same ``llm``/``DM`` reference."""
        cfg = self._copy_config()
        for key in (
            "name",
            "llm",
            "model",
            "prompt",
            "operation",
            "description",
            "max_retries",
            "retry_delay",
            "output_var",
            "required_vars",
            "optional_vars",
            "parse_fn",
            "validation",
            "pre_hook",
            "post_hook",
            "default",
            "abstain",
            "case_sensitive",
            "levels",
            "questions",
            "threshold",
            "min_confidence",
            "min_margin",
            "state",
            "kind",
        ):
            cfg.pop(key, None)

        choices_arg = bool if self.decide_mode == "noul" else copy.deepcopy(self.choices)
        cloned = type(self)(
            name=self.name,
            llm=self.llm,
            prompt=copy.deepcopy(self.prompt),
            choices=choices_arg,
            levels=copy.deepcopy(self.levels),
            questions=copy.deepcopy(self.questions),
            default=copy.deepcopy(self.default),
            abstain=self.abstain,
            case_sensitive=self.case_sensitive,
            threshold=self.threshold,
            min_confidence=self.min_confidence,
            min_margin=self.min_margin,
            state=copy.deepcopy(self.state_spec),
            max_retries=self.max_retries,
            description=self.description,
            retry_delay=self.retry_delay,
            output_var=self.output_var,
            required_vars=copy.deepcopy(self.required_vars),
            optional_vars=copy.deepcopy(self.optional_vars),
            parse_fn=self.parse_fn,
            validation=self.validation,
            pre_hook=self.pre_hook,
            post_hook=self.post_hook,
            **cfg,
        )
        cloned.visibility = self.visibility
        cloned.instruct_schema = self.instruct_schema
        cloned.record_prompt = self.record_prompt
        cloned.id = event_stamp()
        cloned.execution_history = copy.deepcopy(self.execution_history)
        cloned.last_result = copy.deepcopy(self.last_result)
        cloned.last_error = self.last_error
        cloned.last_prompt = self.last_prompt
        cloned.last_msgs = copy.deepcopy(self.last_msgs)
        cloned.last_response = copy.deepcopy(self.last_response)
        return cloned

    def __repr__(self):
        """Return detailed string representation."""
        return (
            "DECIDE(name='{}', mode='{}', choices={}, max_retries={}, default={})".format(
                self.name, self.decide_mode, self._choices_list, self.max_retries, self.default
            )
        )

    def __str__(self):
        """Return human-readable string representation."""
        return "Decide: {} (choices: {})".format(
            self.name or "unnamed",
            ", ".join(self._choices_list),
        )
