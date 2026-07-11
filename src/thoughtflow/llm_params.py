"""
Model-parameter pipeline for ThoughtFlow LLM calls.

Every LLM connection class shares one contract:

1. Constructor kwargs split into **reserved** (client-only), **transport** (headers/URL),
   and **model** (wire) buckets.
2. Per-call ``params`` merge with ``default_params``; per-call wins.
3. ``split_call_params`` removes transport keys before JSON bodies are built.
4. Provider profiles decide how wire params map onto each API shape.

See ``docs/concepts/llm.md`` and ``primitives/LLM.md`` for the author-facing guide.
"""

from __future__ import annotations

from thoughtflow._util import TRANSPORT_PARAM_KEYS

# Constructor/call kwargs that are never model parameters and never on the wire.
LLM_RESERVED_KEYS = frozenset({
    "record",
    "request_timeout",
    "on_usage",
})

# OpenAI-compatible services pass wire params through unchanged.
OPENAI_COMPAT_SERVICES = frozenset({
    "openai",
    "groq",
    "openrouter",
})

# Anthropic body fields we map explicitly from wire params.
ANTHROPIC_WIRE_KEYS = frozenset({
    "max_tokens",
    "temperature",
    "top_p",
    "top_k",
    "stop_sequences",
})


def merge_call_params(default_params, per_call):
    """
    Merge constructor defaults with per-call overrides.

    Per-call values win on conflict. Neither operand is mutated.
    """
    return {**default_params, **(per_call or {})}


def split_call_params(merged):
    """
    Split merged call params into wire payload params and transport context.

    Transport keys (base_url, referer, extra_headers, etc.) are client-side
    routing metadata. They must not appear in provider JSON bodies.

    Args:
        merged (dict): Output of merge_call_params.

    Returns:
        tuple: (wire_params, transport_ctx) — both new dicts.
    """
    wire = dict(merged)
    transport = {}
    for key in TRANSPORT_PARAM_KEYS:
        if key in wire:
            transport[key] = wire.pop(key)
    return wire, transport


def normalize_usage(response, service, model):
    """
    Normalize provider usage blocks into one inspectable dict.

    Captures standard token counts plus cache and reasoning fields when the
    provider returns them (OpenAI cached_tokens, Anthropic cache_read_input_tokens,
    Groq reasoning_tokens, etc.).

    Args:
        response (dict): Parsed JSON response from _send_request.
        service (str): ThoughtFlow service name.
        model (str): Model slug.

    Returns:
        dict: Normalized usage record, or None when no usage block exists.
    """
    if not isinstance(response, dict):
        return None
    usage = response.get("usage")
    if not usage:
        return None

    record = {
        "prompt_tokens": usage.get("prompt_tokens", usage.get("input_tokens", 0)),
        "completion_tokens": usage.get("completion_tokens", usage.get("output_tokens", 0)),
        "service": service,
        "model": model,
    }

    prompt_details = usage.get("prompt_tokens_details") or {}
    cached = prompt_details.get("cached_tokens")
    if cached:
        record["cached_tokens"] = cached

    if usage.get("cache_read_input_tokens"):
        record["cache_read_input_tokens"] = usage["cache_read_input_tokens"]
    if usage.get("cache_creation_input_tokens"):
        record["cache_creation_input_tokens"] = usage["cache_creation_input_tokens"]

    completion_details = usage.get("completion_tokens_details") or {}
    reasoning = completion_details.get("reasoning_tokens")
    if reasoning:
        record["reasoning_tokens"] = reasoning

    return record


def build_gemini_generation_config(wire_params):
    """
    Extract OpenAI-style sampling keys into Gemini generationConfig.

    Popped keys are removed from wire_params in place so they are not duplicated
    at the top level of the Gemini payload.

    Args:
        wire_params (dict): Mutable wire param dict.

    Returns:
        dict: generationConfig object (may be empty).
    """
    generation_config = {}
    if "max_tokens" in wire_params:
        generation_config["maxOutputTokens"] = wire_params.pop("max_tokens")
    if "temperature" in wire_params:
        generation_config["temperature"] = wire_params.pop("temperature")
    if "top_p" in wire_params:
        generation_config["topP"] = wire_params.pop("top_p")
    return generation_config


def pick_anthropic_wire_params(wire_params):
    """
    Return Anthropic message API fields from wire params.

    Only known keys are forwarded; provider-specific extensions belong in
    documented wire keys or OpenAI-compatible services.

    Args:
        wire_params (dict): Wire params (not mutated).

    Returns:
        dict: Subset safe to merge into Anthropic payload.
    """
    return {k: wire_params[k] for k in ANTHROPIC_WIRE_KEYS if k in wire_params}
