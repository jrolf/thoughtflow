"""
OpenRouterLLM — OpenRouter gateway with correct attribution headers.

OpenRouter expects HTTP-Referer and X-Title for rankings and abuse prevention.
Referer and title are transport params — split out of JSON bodies by the
unified param pipeline.
"""

from __future__ import annotations

from thoughtflow.llm import LLM


class OpenRouterLLM(LLM):
    """
    OpenRouter gateway with sensible attribution header defaults.

    Args:
        model (str): OpenRouter slug (e.g. anthropic/claude-3.5-sonnet).
        key (str): OPENROUTER_API_KEY.
        app_title (str): X-Title header value.
        app_url (str): HTTP-Referer header value.
        **kwargs: Model params and per-call overrides.
    """

    def __init__(
        self,
        model,
        key,
        app_title="ThoughtFlow",
        app_url="https://github.com/jrolf/thoughtflow",
        **kwargs,
    ):
        kwargs.setdefault("referer", app_url)
        kwargs.setdefault("title", app_title)
        super().__init__(model_id="openrouter:" + model, key=key, **kwargs)
