"""
Prompt caching helpers for ThoughtFlow LLM calls.

Provider prompt caching cuts cost and latency for stable prefixes (system prompts,
tool schemas, long document context) in agentic loops. ThoughtFlow exposes caching
with little fuss:

- Mark messages with ``cache=True`` or use ``cached_system()`` / ``cached_message()``.
- Wire adapters translate markers to provider-native shapes (Anthropic cache_control).
- Cache markers are stripped from record/replay exchange keys so semantic hashes stay
  stable whether or not caching was enabled during recording.

Replay (LLM.record / LLM.replay) and provider prompt caching are orthogonal:
replay caches full responses offline; provider caching caches input token prefixes
at the API.
"""

from __future__ import annotations

import copy

# Services that receive Anthropic-style cache_control blocks on marked messages.
_CACHE_BLOCK_SERVICES = frozenset({"anthropic"})

# Services that pass messages through; optional prompt_cache_key may sit in wire params.
_OPENAI_COMPAT_CACHE_SERVICES = frozenset({
    "openai",
    "groq",
    "openrouter",
})

# Services where cache markers are stripped silently (no provider support).
_NO_CACHE_SERVICES = frozenset({"ollama", "gemini"})


def cached_system(content):
    """
    Build a system message marked for provider prompt caching.

    Use for stable system prompts resent every agent turn.

    Args:
        content (str): System prompt text.

    Returns:
        dict: Message dict with ``cache=True``.
    """
    return {"role": "system", "content": content, "cache": True}


def cached_message(role, content):
    """
    Build a message marked for provider prompt caching.

    Args:
        role (str): Message role (system, user, assistant, ...).
        content (str): Message body.

    Returns:
        dict: Message dict with ``cache=True``.
    """
    return {"role": role, "content": content, "cache": True}


def _content_has_native_cache_control(content):
    """Return True when content already carries provider cache_control blocks."""
    if not isinstance(content, list):
        return False
    for block in content:
        if isinstance(block, dict) and block.get("cache_control"):
            return True
    return False


def _to_cached_text_block(text):
    """Anthropic/OpenAI-style text block with ephemeral cache_control."""
    return {
        "type": "text",
        "text": text,
        "cache_control": {"type": "ephemeral"},
    }


def _transform_message_for_provider(message, service):
    """
    Apply provider-native cache wire format to one normalized message.

    Removes the ThoughtFlow ``cache`` flag from the returned message.
    """
    msg = dict(message)
    want_cache = msg.pop("cache", False)
    content = msg.get("content", "")

    if _content_has_native_cache_control(content):
        return msg

    if not want_cache:
        return msg

    if service in _NO_CACHE_SERVICES:
        return msg

    if service in _CACHE_BLOCK_SERVICES:
        if isinstance(content, str):
            msg["content"] = [_to_cached_text_block(content)]
        elif isinstance(content, list):
            msg["content"] = copy.deepcopy(content)
        return msg

    if service in _OPENAI_COMPAT_CACHE_SERVICES:
        # OpenAI-compatible hosts: automatic prefix caching for long prompts;
        # keep string content — prompt_cache_key may be set in wire params.
        return msg

    return msg


def apply_cache_markers(messages, service):
    """
    Transform messages for provider wire format when cache=True is set.

    Args:
        messages (list): Normalized, role-mapped message dicts.
        service (str): ThoughtFlow service name.

    Returns:
        list: New message list with cache markers translated or stripped.
    """
    return [_transform_message_for_provider(m, service) for m in messages]


def strip_cache_markers(msg_list):
    """
    Remove cache hints for record/replay exchange keys.

    Semantic content must hash the same whether the author enabled provider
    caching on the live call or not.

    Args:
        msg_list (list): Raw or normalized messages.

    Returns:
        list: Deep-copied messages without ``cache`` or ``cache_control``.
    """
    stripped = []
    for m in msg_list:
        if not isinstance(m, dict):
            stripped.append(m)
            continue
        msg = copy.deepcopy(m)
        msg.pop("cache", None)
        content = msg.get("content")
        if isinstance(content, list):
            new_blocks = []
            for block in content:
                if isinstance(block, dict):
                    block = dict(block)
                    block.pop("cache_control", None)
                new_blocks.append(block)
            msg["content"] = new_blocks
        stripped.append(msg)
    return stripped


def format_anthropic_system(system_parts, system_messages):
    """
    Build Anthropic ``system`` field from split system prompts.

    When any system message was marked ``cache=True``, returns a list of text
    blocks with cache_control; otherwise returns a joined string (legacy shape).

    Args:
        system_parts (list): Plain system strings from split (no cache info).
        system_messages (list): Original normalized system message dicts.

    Returns:
        str or list: Anthropic API system value.
    """
    if not system_messages:
        if not system_parts:
            return None
        if len(system_parts) == 1:
            return system_parts[0]
        return "\n\n".join(system_parts)

    if not any(m.get("cache") for m in system_messages):
        if len(system_parts) == 1:
            return system_parts[0]
        return "\n\n".join(system_parts)

    blocks = []
    for msg in system_messages:
        content = msg.get("content", "")
        want_cache = msg.get("cache", False)
        if want_cache:
            if isinstance(content, str):
                blocks.append(_to_cached_text_block(content))
            elif isinstance(content, list):
                blocks.extend(copy.deepcopy(content))
        else:
            if isinstance(content, str):
                blocks.append({"type": "text", "text": content})
            elif isinstance(content, list):
                blocks.extend(copy.deepcopy(content))

    if not blocks:
        if len(system_parts) == 1:
            return system_parts[0]
        return "\n\n".join(system_parts)

    return blocks
