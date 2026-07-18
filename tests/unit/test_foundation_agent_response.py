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


class EnvelopePlan(PLAN):
    """Unwrap a common model envelope while counting normalization calls."""

    def normalize_plan(self, parsed_result):
        """Return the nested native PLAN shape when a steps envelope is present."""
        self.normalize_calls = getattr(self, "normalize_calls", 0) + 1
        if isinstance(parsed_result, dict) and "steps" in parsed_result:
            return parsed_result["steps"]
        return parsed_result


class TestSubclassValidationCompatibility:
    """Custom THOUGHT.validate overrides remain active in the retry pipeline."""

    def test_validate_override_controls_retry_and_success(self, mock_llm, memory):
        class CustomThought(THOUGHT):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.validated = []

            def validate(self, parsed_result):
                self.validated.append(parsed_result)
                if parsed_result == "accepted":
                    return True, ""
                return False, "custom rejection"

        llm = mock_llm(responses=["rejected", "accepted"])
        thought = CustomThought(
            name="custom_validation",
            llm=llm,
            prompt="Answer",
            max_retries=2,
        )

        thought(memory)

        assert thought.validated == ["rejected", "accepted"]
        assert llm.call_count == 2
        assert memory.get_var("custom_validation_result") == "accepted"


class TestPlanNormalizePipeline:
    """WP-LEGO-07 GO: normalized output is returned and stored."""

    def test_end_to_end_stores_normalized_plan(self, mock_llm, memory):
        wrapped = '{"steps": [[{"action": "search", "reason": "Gather data."}]]}'
        plan = EnvelopePlan(
            name="envelope",
            llm=mock_llm(responses=[wrapped]),
            prompt="Plan: {goal}",
            actions={"search": "Search"},
            max_retries=1,
        )
        memory.set_var("goal", "research")
        plan(memory)

        stored = memory.get_var("envelope_result")
        expected = [[{"action": "search", "reason": "Gather data."}]]
        assert stored == expected
        assert plan.last_result == expected

    def test_direct_validate_still_normalizes_once(self, mock_llm):
        plan = EnvelopePlan(
            name="envelope",
            llm=mock_llm(),
            prompt="Plan",
            actions={"search": "Search"},
        )
        raw = {"steps": [[{"action": "search", "reason": "Need data."}]]}
        valid, reason = plan.validate(raw)
        assert valid is True
        assert reason == ""
        assert plan.normalize_calls == 1

    def test_retry_returns_normalized_plan(self, mock_llm, memory):
        bad = '{"steps": [[{"action": "missing", "reason": "Bad action."}]]}'
        good = '{"steps": [[{"action": "search", "reason": "Fixed plan."}]]}'
        plan = EnvelopePlan(
            name="retry_env",
            llm=mock_llm(responses=[bad, good]),
            prompt="Plan",
            actions={"search": "Search"},
            max_retries=2,
        )
        plan(memory)

        stored = memory.get_var("retry_env_result")
        assert stored == [[{"action": "search", "reason": "Fixed plan."}]]

    def test_normalize_exception_retries_and_stores_success(
        self,
        mock_llm,
        memory,
    ):
        class RetryNormalizePlan(EnvelopePlan):
            """Fail the first deterministic normalization attempt."""

            def normalize_plan(self, parsed_result):
                """Raise once, then perform normal envelope unwrapping."""
                self.attempts = getattr(self, "attempts", 0) + 1
                if self.attempts == 1:
                    raise ValueError("temporary normalization failure")
                return super().normalize_plan(parsed_result)

        wrapped = '{"steps": [[{"action": "search", "reason": "Recovered."}]]}'
        llm = mock_llm(responses=[wrapped])
        plan = RetryNormalizePlan(
            name="retry_normalize",
            llm=llm,
            prompt="Plan",
            actions={"search": "Search"},
            max_retries=2,
        )

        plan(memory)

        expected = [[{"action": "search", "reason": "Recovered."}]]
        assert llm.call_count == 2
        assert plan.attempts == 2
        assert memory.get_var("retry_normalize_result") == expected
        error = memory.get_var("retry_normalize_last_error")
        assert error["reason"] == "temporary normalization failure"
        assert error["attempts"][0]["attempt"] == 1

    def test_custom_validate_override_controls_retry_and_storage(
        self,
        mock_llm,
        memory,
    ):
        class CustomValidatePlan(PLAN):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.validated = []

            def validate(self, parsed_result):
                self.validated.append(parsed_result)
                if parsed_result == "accepted":
                    return True, ""
                return False, "custom plan rejection"

        llm = mock_llm(responses=["rejected", "accepted"])
        plan = CustomValidatePlan(
            name="custom_plan_validation",
            llm=llm,
            prompt="Plan",
            actions={"search": "Search"},
            max_retries=2,
        )

        plan(memory)

        assert plan.validated == ["rejected", "accepted"]
        assert llm.call_count == 2
        assert memory.get_var("custom_plan_validation_result") == "accepted"


class TestTemplateModeAndHistory:
    """WP-LEGO-04: opt-in template rendering and history control."""

    def test_defaults_preserve_format_and_history(self, mock_llm):
        thought = THOUGHT(name="defaults", llm=mock_llm(), prompt="Hello {name}")
        assert thought.template_mode == "format"
        assert thought.include_history is True

    def test_substitute_preserves_literal_json_braces(self, mock_llm, memory):
        thought = THOUGHT(
            name="json_prompt",
            llm=mock_llm(),
            prompt='Return JSON like {"status": "ok"} for {topic}',
            template_mode="substitute",
        )
        memory.set_var("topic", "demo")
        rendered = thought.build_prompt(memory)
        assert '{"status": "ok"}' in rendered
        assert rendered.endswith("for demo")

    def test_format_mode_preserves_dict_prompt_sections(self, mock_llm, memory):
        thought = THOUGHT(
            name="dict_prompt",
            llm=mock_llm(),
            prompt={"task": 'Keep {"status": "ok"} for {topic}'},
        )
        memory.set_var("topic", "demo")

        rendered = thought.build_prompt(memory)

        assert '{"status": "ok"}' in rendered
        assert "{topic}" in rendered

    def test_substitute_renders_system_prompt(self, mock_llm, memory):
        thought = THOUGHT(
            name="system_prompt",
            llm=mock_llm(),
            prompt="Answer",
            system_prompt='Keep {"status": "ok"} for {topic}',
            template_mode="substitute",
            include_history=False,
        )
        memory.set_var("topic", "demo")

        messages = thought.build_msgs(memory)

        assert messages[0]["content"] == 'Keep {"status": "ok"} for demo'

    def test_substitute_leaves_unknown_placeholders(self, mock_llm, memory):
        thought = THOUGHT(
            name="unknown",
            llm=mock_llm(),
            prompt="Known {known}, unknown {missing}",
            template_mode="substitute",
        )
        memory.set_var("known", "value")
        rendered = thought.build_prompt(memory)
        assert "Known value" in rendered
        assert "{missing}" in rendered

    def test_substitute_does_not_replace_bare_word_messages(self, mock_llm, memory):
        thought = THOUGHT(
            name="messages_word",
            llm=mock_llm(),
            prompt="Review prior messages and summarize {topic}",
            template_mode="substitute",
        )
        memory.set_var("topic", "ThoughtFlow")
        memory.set_var("messages", "SHOULD_NOT_APPEAR")
        rendered = thought.build_prompt(memory)
        assert "prior messages" in rendered
        assert "SHOULD_NOT_APPEAR" not in rendered
        assert rendered.endswith("ThoughtFlow")

    def test_substitute_overlapping_names_only_replaces_braced_keys(
        self, mock_llm, memory
    ):
        thought = THOUGHT(
            name="overlap",
            llm=mock_llm(),
            prompt="topic={topic} and literal topic word",
            template_mode="substitute",
        )
        memory.set_var("topic", "AI")
        rendered = thought.build_prompt(memory)
        assert rendered == "topic=AI and literal topic word"

    def test_include_history_false_sends_system_and_user_only(self, mock_llm, memory):
        llm = mock_llm(responses=["done"])
        thought = THOUGHT(
            name="no_history",
            llm=llm,
            prompt="Answer: {last_user_msg}",
            system_prompt="You are helpful",
            include_history=False,
        )
        memory.add_msg("user", "Earlier turn", channel="api")
        memory.add_msg("assistant", "Earlier reply", channel="api")
        memory.add_msg("user", "Current question", channel="api")
        thought(memory)

        msgs = llm.calls[0]["msgs"]
        assert len(msgs) == 2
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"
        assert "Earlier turn" not in msgs[1]["content"]
        assert "Current question" in msgs[1]["content"]

    def test_history_is_not_rewritten_by_context(self, mock_llm, memory):
        llm = mock_llm(responses=["done"])
        thought = THOUGHT(
            name="history_safe",
            llm=llm,
            prompt="Follow up on messages",
            template_mode="substitute",
        )
        memory.add_msg("user", "Please review messages in the chat", channel="api")
        memory.set_var("messages", "INJECTED")
        thought(memory)

        history_contents = [
            m["content"] for m in llm.calls[0]["msgs"] if m["role"] == "user"
        ][:-1]
        assert history_contents == ["Please review messages in the chat"]

    def test_included_history_uses_llm_message_projection(self, mock_llm, memory):
        thought = THOUGHT(
            name="projected_history",
            llm=mock_llm(),
            prompt="Continue",
        )
        memory.add_msg(
            "user",
            "Stored turn",
            channel="api",
            metadata={"internal": True},
        )

        messages = thought.build_msgs(memory)

        assert messages[0] == {"role": "user", "content": "Stored turn"}

    def test_context_uses_latest_memory_variable_value(self, mock_llm, memory):
        thought = THOUGHT(
            name="latest_value",
            llm=mock_llm(),
            prompt="{topic}",
        )
        memory.set_var("topic", "first")
        memory.set_var("topic", "latest")

        context = thought.get_context(memory)

        assert context["topic"] == "latest"

    def test_serialization_roundtrip_preserves_template_flags(self, mock_llm):
        original = THOUGHT(
            name="serial",
            llm=mock_llm(),
            prompt="Hello {name}",
            template_mode="substitute",
            include_history=False,
        )
        restored = THOUGHT.from_dict(original.to_dict(), llm=mock_llm())
        assert restored.template_mode == "substitute"
        assert restored.include_history is False

    def test_copy_preserves_template_flags(self, mock_llm):
        original = THOUGHT(
            name="copy_me",
            llm=mock_llm(),
            prompt="Hello",
            template_mode="substitute",
            include_history=False,
        )
        copied = original.copy()
        assert copied.template_mode == "substitute"
        assert copied.include_history is False
        assert copied.id != original.id

    def test_invalid_template_mode_raises(self, mock_llm):
        with pytest.raises(ValueError, match="template_mode"):
            THOUGHT(
                name="bad_mode",
                llm=mock_llm(),
                prompt="x",
                template_mode="unsafe",
            )

    @pytest.mark.parametrize("invalid", ["false", 0, 1, None, []])
    def test_invalid_include_history_raises_at_construction(
        self,
        mock_llm,
        invalid,
    ):
        with pytest.raises(ValueError, match="include_history must be a bool"):
            THOUGHT(
                name="bad_history",
                llm=mock_llm(),
                prompt="x",
                include_history=invalid,
            )

    def test_invalid_include_history_in_config_raises_when_read(
        self,
        mock_llm,
        memory,
    ):
        thought = THOUGHT(
            name="mutated_history",
            llm=mock_llm(),
            prompt="x",
        )
        thought.config["include_history"] = "false"

        with pytest.raises(ValueError, match="include_history must be a bool"):
            thought.build_msgs(memory)
