"""
Integration smoke tests for ThoughtFlow Decision Models (DM and DECIDE).

These tests make real HTTP calls to OpenRouter's Decisions API. They are
skipped unless THOUGHTFLOW_INTEGRATION_TESTS=1 and OPENROUTER_API_KEY is set.

Running:
    THOUGHTFLOW_INTEGRATION_TESTS=1 pytest tests/integration/test_dm_providers.py -v
"""

from __future__ import annotations

import os

import pytest

from thoughtflow import DECIDE, DM, MEMORY


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("THOUGHTFLOW_INTEGRATION_TESTS") != "1",
        reason="Integration tests disabled. Set THOUGHTFLOW_INTEGRATION_TESTS=1 to enable.",
    ),
]


@pytest.mark.skipif(
    not os.getenv("OPENROUTER_API_KEY"),
    reason="OPENROUTER_API_KEY not set",
)
class TestOpenRouterDMIntegration:
    """Live smoke tests for OpenRouter decision models (TypeSafe Jev and Liquid d1)."""

    def test_jev_multi_question_call_and_replay(self):
        memory = MEMORY()
        dm = DM(
            "openrouter:typesafe/jev-1.14",
            key=os.getenv("OPENROUTER_API_KEY"),
            referer="https://github.com/jrolf/thoughtflow",
            title="ThoughtFlow",
        ).record(memory)

        state = {
            "ticket": "I was billed twice on invoice #4021 and need the duplicate charge refunded."
        }
        questions = {
            "dept": {
                "type": "choice",
                "instructions": "Which team owns this ticket?",
                "choices": {
                    "billing": "Invoices, duplicate charges, and refunds",
                    "engineering": "Crashes, bugs, and outages",
                },
            },
            "is_refund": {
                "type": "noul",
                "instructions": "Is the customer requesting money back?",
            },
            "urgency": {
                "type": "score",
                "instructions": "How urgent is this issue?",
                "levels": ["Low", "Medium", "High"],
            },
        }

        live_res = dm.call(state, questions)
        assert live_res["answers"]["dept"]["value"] == "billing"
        assert live_res["answers"]["is_refund"]["value"] is True
        assert 0.0 <= live_res["answers"]["urgency"]["value"] <= 2.0
        assert live_res["usage"]["prompt_tokens"] > 0

        rehydrated = MEMORY.from_json(memory.to_json())
        replay_dm = DM.replay(rehydrated)
        replay_res = replay_dm.call(state, questions)
        assert replay_res["answers"] == live_res["answers"]

    def test_decide_with_liquid_d1(self):
        dm = DM(
            "openrouter:liquid/d1.2",
            key=os.getenv("OPENROUTER_API_KEY"),
        )
        route = DECIDE(
            name="route",
            model=dm,
            choices={
                "billing": "Payments, invoices, and subscription charges",
                "tech": "Application crashes and broken features",
            },
            prompt="Route this support message: {last_user_msg}",
            include_history=False,
        )

        mem = MEMORY()
        mem.add_msg("user", "The mobile app crashes immediately when I tap Settings.")
        mem = route(mem)

        assert mem.get_var("route_result") == "tech"
        outcome = mem.get_var("route_outcome")
        assert outcome["ok"] is True
        assert outcome["source"] == "model"
        assert outcome["confidence"] is not None
