"""
Regression tests for Foundation Agent production feedback response plan.

Covers opt-in production-lane features and automatic improvements from
.PLANS/FOUNDATION_AGENT_RESPONSE_PLAN.md without requiring live LLM calls.
"""

from __future__ import annotations

import pytest

from thoughtflow import THOUGHT, PLAN
from thoughtflow._util import valid_extract, scan_none_exemplars


class TestValidationReturnCoercion:
    """WP-02: bare-bool validation returns must not crash unpack."""

    def test_bare_bool_true_accepted(self, mock_llm):
        thought = THOUGHT(
            name="bool_val",
            llm=mock_llm(),
            prompt="x",
            validation=lambda r: True,
        )
        valid, why = thought.validate({"any": "thing"})
        assert valid is True
        assert "bool" in why

    def test_bare_bool_false_rejected(self, mock_llm):
        thought = THOUGHT(
            name="bool_val",
            llm=mock_llm(),
            prompt="x",
            validation=lambda r: False,
        )
        valid, why = thought.validate({})
        assert valid is False


class TestStructuredFailureVisibility:
    """WP-03: failures leave structured traces on MEMORY."""

    def test_last_error_var_on_schema_failure(self, mock_llm, memory):
        thought = THOUGHT(
            name="locator",
            llm=mock_llm(responses=['{"verdict": "absent", "note": "gone"}']),
            prompt="Find it",
            parsing_rules={
                "kind": "python",
                "format": {"verdict": "", "matched_span": ""},
            },
            max_retries=1,
        )
        memory.add_msg("user", "go", channel="api")
        thought(memory)

        err = memory.get_var("locator_last_error")
        assert err is not None
        assert err["failure_kind"] == "schema"
        assert memory.get_var("locator_attempts") == 1

    def test_on_failure_hook_fires(self, mock_llm, memory):
        events = []

        def on_failure(thought, attempt, failure_kind, reason, raw_response=None):
            events.append({
                "attempt": attempt,
                "failure_kind": failure_kind,
                "reason": reason,
            })

        thought = THOUGHT(
            name="hooked",
            llm=mock_llm(responses=["not json at all"]),
            prompt="x",
            parsing_rules={"kind": "python", "format": {}},
            max_retries=1,
            on_failure=on_failure,
        )
        memory.add_msg("user", "go", channel="api")
        thought(memory)

        assert len(events) == 1
        assert events[0]["failure_kind"] == "schema"


class TestOneOfSchema:
    """WP-09: optional oneOf dialect for branch-shaped thoughts."""

    def test_absent_branch_validates(self):
        rules = {
            "kind": "python",
            "format": {
                "oneOf": [
                    {"verdict": "found", "matched_span": ""},
                    {"verdict": "absent", "note": ""},
                ]
            },
        }
        text = "{'verdict': 'absent', 'note': 'not here'}"
        result = valid_extract(text, rules)
        assert result["verdict"] == "absent"

    def test_found_branch_validates(self):
        rules = {
            "kind": "python",
            "format": {
                "oneOf": [
                    {"verdict": "found", "matched_span": ""},
                    {"verdict": "absent", "note": ""},
                ]
            },
        }
        text = "{'verdict': 'found', 'matched_span': 'hello'}"
        result = valid_extract(text, rules)
        assert result["matched_span"] == "hello"


class TestValidationRescueMode:
    """WP-10: opt-in rescue lets callable accept schema misses."""

    def test_rescue_accepts_absent_verdict(self, mock_llm, memory):
        def rescue_validator(parsed, schema_error=None):
            if parsed.get("verdict") == "absent":
                return True, "absent ok"
            return False, "bad"

        thought = THOUGHT(
            name="rescue",
            llm=mock_llm(responses=['{"verdict": "absent", "note": "x"}']),
            prompt="locate",
            parsing_rules={
                "kind": "python",
                "format": {"verdict": "", "matched_span": ""},
            },
            validation=rescue_validator,
            validation_mode="rescue",
            max_retries=1,
        )
        memory.add_msg("user", "go", channel="api")
        thought(memory)

        assert memory.get_var("rescue_result") == {
            "verdict": "absent",
            "note": "x",
        }


class TestStrictSchema:
    """WP-01: opt-in strict_schema catches None exemplar trap."""

    def test_strict_schema_raises_on_none_exemplar(self, mock_llm):
        with pytest.raises(ValueError) as exc:
            THOUGHT(
                name="wish",
                llm=mock_llm(),
                prompt="reflect",
                parsing_rules={"kind": "python", "format": {"wish": None}},
                strict_schema=True,
            )
        assert "strict_schema" in str(exc.value)

    def test_none_exemplar_allowed_without_strict(self, mock_llm):
        thought = THOUGHT(
            name="wish",
            llm=mock_llm(),
            prompt="reflect",
            parsing_rules={"kind": "python", "format": {"wish": None}},
        )
        assert thought is not None

    def test_scan_none_exemplars_finds_paths(self):
        schema = {"wish": None, "note": ""}
        paths = scan_none_exemplars(schema)
        assert "format.wish" in paths


class TestPlanNormalizeHook:
    """WP-08: normalize_plan runs before validation."""

    def test_subclass_unwrap_string_plan(self, mock_llm):
        class UnwrapPlan(PLAN):
            def normalize_plan(self, parsed_result):
                if isinstance(parsed_result, str):
                    import json
                    return json.loads(parsed_result)
                return parsed_result

        plan = UnwrapPlan(
            name="unwrap",
            llm=mock_llm(),
            prompt="Plan",
            actions={"search": "Search"},
        )
        raw = '[[{"action": "search", "reason": "Need data."}]]'
        valid, reason = plan.validate(raw)
        assert valid is True


class TestPlanAggregateParams:
    """WP-07: aggregate missing param errors."""

    def test_lists_all_missing_params(self, mock_llm):
        plan = PLAN(
            name="multi",
            llm=mock_llm(),
            prompt="Plan",
            actions={
                "compose": {
                    "description": "Compose",
                    "params": {"channel": "str", "intent": "str"},
                },
            },
        )
        bad = [[{"action": "compose", "params": {}, "reason": "Write."}]]
        valid, reason = plan.validate(bad)
        assert valid is False
        assert "channel" in reason
        assert "intent" in reason
        assert "requires params:" in reason


class TestHoldMsg:
    """WP-13: hold_msg defers assistant messages until success."""

    def test_failed_attempt_not_in_memory_when_hold_msg(self, mock_llm, memory):
        thought = THOUGHT(
            name="clean",
            llm=mock_llm(responses=["garbage"]),
            prompt="x",
            parsing_rules={"kind": "python", "format": {}},
            max_retries=1,
            hold_msg=True,
        )
        memory.add_msg("user", "go", channel="api")
        before = len(memory.get_msgs())
        thought(memory)
        after = len(memory.get_msgs())
        assert after == before
