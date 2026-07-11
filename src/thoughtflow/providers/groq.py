"""
GroqLLM — Groq inference with production-safe defaults.

Qwen models on Groq emit think-blocks that hijack JSON extraction in THOUGHT
unless reasoning_format is hidden. This class sets that default for Qwen model
IDs only; other models are unchanged.
"""

from __future__ import annotations

import re

from thoughtflow.llm import LLM

_QWEN_PREFIXES = ("qwen/", "qwen-")


def _is_qwen_model(model):
    """Return True when the model slug is a Qwen family ID on Groq."""
    model_lower = model.lower()
    return any(model_lower.startswith(p) for p in _QWEN_PREFIXES)


class GroqLLM(LLM):
    """
    Groq inference with production-safe defaults.

    Inherits the full ThoughtFlow param pipeline and prompt caching support.
    Optional strip_think_blocks post-processes choices when enabled.

    Args:
        model (str): Groq model slug (e.g. openai/gpt-oss-20b, qwen/qwen3-32b).
        key (str): GROQ_API_KEY.
        strip_think_blocks (bool): When True, remove redacted_thinking blocks
            from responses (default False).
        **kwargs: Model params (temperature, max_tokens, reasoning_effort, ...)
            and transport params — forwarded via the standard LLM pipeline.
    """

    def __init__(self, model, key, strip_think_blocks=False, **kwargs):
        if _is_qwen_model(model):
            kwargs.setdefault("reasoning_format", "hidden")
        self.strip_think_blocks = strip_think_blocks
        super().__init__(model_id="groq:" + model, key=key, **kwargs)

    def call(self, msg_list, params=None, output_schema=None, stream=False):
        """Call Groq; optionally strip think-blocks from string choices."""
        if params is None:
            params = {}
        choices = super().call(msg_list, params=params, output_schema=output_schema, stream=stream)
        if stream or not self.strip_think_blocks:
            return choices
        return [self._strip_think_blocks(c) for c in choices]

    @staticmethod
    def _strip_think_blocks(text):
        """Remove Groq/Qwen redacted_thinking blocks from response text."""
        return re.sub(
            r"<think>.*?</think>\s*",
            "",
            str(text or ""),
            flags=re.DOTALL,
        ).strip()
