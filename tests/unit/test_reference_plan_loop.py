"""Deterministic tests for the copy-and-edit plan loop reference."""

import importlib.util
from pathlib import Path

import pytest

from thoughtflow import CHRON, MEMORY


EXAMPLE = (
    Path(__file__).resolve().parents[2]
    / "examples/reference/plan_commit_reflect_loop.py"
)
spec = importlib.util.spec_from_file_location("reference_plan_loop", EXAMPLE)
ref = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ref)


def one_task(action, params=None):
    """Build one native PLAN step for focused loop tests."""
    return [
        [
            {
                "action": action,
                "params": params or {},
                "reason": "Exercise {} in the focused test.".format(action),
            }
        ]
    ]


class TestReceipts:
    """Protect the canonical local receipt contract."""

    def test_factories_return_fresh_isolated_valid_receipts(self):
        data = {"items": []}
        first = ref.receipt_ok("done", data=data, extra={"tag": {"n": 1}})
        second = ref.receipt_ok("done")
        data["items"].append("changed")

        assert first is not second
        assert first["data"] == {"items": []}
        assert ref.is_receipt(first)
        assert ref.is_receipt(ref.receipt_failed("boom"))
        assert ref.is_receipt(ref.receipt_partial("part", gaps=["later"]))

    @pytest.mark.parametrize(
        "factory,args",
        [
            (ref.receipt_ok, (3,)),
            (ref.receipt_failed, ("",)),
            (ref.receipt_failed, (3,)),
            (ref.receipt_partial, ("part", "not-a-list")),
        ],
    )
    def test_factories_reject_malformed_required_fields(self, factory, args):
        with pytest.raises(ValueError):
            factory(*args)

    def test_validator_enforces_status_specific_fields(self):
        assert not ref.is_receipt({"status": "ok"})
        assert not ref.is_receipt({"status": "failed", "error": "x"})
        assert not ref.is_receipt(
            {"status": "partial", "summary": "x", "gaps": "later"}
        )

    def test_extra_cannot_replace_reserved_fields(self):
        with pytest.raises(ValueError, match="reserved"):
            ref.receipt_ok(extra={"status": "failed"})


class TestPlanHelpers:
    """Protect native PLAN boundary and reference semantics."""

    def test_canned_plans_have_required_non_empty_reasons(self):
        plans = [
            ref.demo_plan(0),
            ref.demo_plan(1),
            *ref.SUB_RUN_PLANS.values(),
        ]

        for plan in plans:
            for step in plan:
                for task in step:
                    assert isinstance(task.get("reason"), str)
                    assert task["reason"]

    def test_boundary_split_is_inclusive_and_non_mutating(self):
        plan = [
            [{"action": "READ_NOTE"}],
            [{"action": "REPLAN"}],
            [{"action": "SEND_MESSAGE"}],
        ]
        original = list(plan)

        committed, forecast = ref.split_at_boundary(plan, {"REPLAN"})

        assert committed == plan[:2]
        assert forecast == plan[2:]
        assert plan == original

    def test_boundary_split_rejects_mixed_control_step(self):
        plan = [[{"action": "REPLAN"}, {"action": "SEND_MESSAGE"}]]
        with pytest.raises(ValueError, match="mixes"):
            ref.split_at_boundary(plan, {"REPLAN"})

    def test_refs_preserve_whole_value_type_and_input(self):
        params = {"nested": ["{step_0_result}"]}
        result = {"status": "ok", "data": {"id": 1}}

        resolved = ref.resolve_step_refs(params, [result], current_step_index=1)

        assert resolved == {"nested": [result]}
        assert resolved["nested"][0] is not result
        assert params == {"nested": ["{step_0_result}"]}

    @pytest.mark.parametrize(
        "value,results,current,message",
        [
            ("{step_2_result}", [], 3, "missing"),
            ("{step_1_result}", [{}], 1, "forward"),
            ("{step_0_result[0].url}", [{}], 1, "unsupported"),
        ],
    )
    def test_refs_fail_clearly(self, value, results, current, message):
        with pytest.raises(ref.StepRefError, match=message):
            ref.resolve_step_refs(value, results, current_step_index=current)


class TestSafeDispatch:
    """Protect resolve, validate, approve, dispatch ordering and restrictions."""

    def test_wrong_type_from_whole_value_ref_blocks_dispatch(self):
        called = []

        def handler(params, agent):
            called.append(params)
            return ref.receipt_ok("should not run")

        agent = ref.build_demo_agent()
        task = {
            "action": "SEND_MESSAGE",
            "params": {"text": "{step_0_result}"},
        }
        receipt = ref.execute_task(
            task,
            1,
            [{"not": "a string"}],
            agent,
            handlers={"SEND_MESSAGE": handler},
        )

        assert receipt["status"] == "failed"
        assert "must be str" in receipt["error"]
        assert called == []
        assert agent["sent_messages"] == []

    def test_resolved_params_reach_approval_and_handler(self):
        agent = ref.build_demo_agent()
        task = {
            "action": "SEND_MESSAGE",
            "params": {"text": "{step_0_result}"},
        }

        receipt = ref.execute_task(task, 1, ["resolved text"], agent)

        assert receipt["status"] == "ok"
        assert agent["sent_messages"] == ["resolved text"]

    def test_explicit_empty_catalog_cannot_fall_back_to_globals(self):
        agent = ref.build_demo_agent()
        task = {"action": "SEND_MESSAGE", "params": {"text": "unsafe"}}

        receipt = ref.execute_task(
            task,
            0,
            [],
            agent,
            catalog={},
            handlers={},
        )

        assert receipt["status"] == "failed"
        assert receipt["error"] == "unknown action 'SEND_MESSAGE'"
        assert agent["sent_messages"] == []

    def test_restricted_catalog_blocks_global_side_effect(self):
        agent = ref.build_demo_agent()
        catalog = {"READ_NOTE": ref.ACTION_CATALOG["READ_NOTE"]}
        handlers = {"READ_NOTE": ref.HANDLERS["READ_NOTE"]}

        reason = ref.inner_loop(
            agent,
            max_cycles=1,
            plan_provider=lambda cycle: one_task(
                "SEND_MESSAGE",
                {"text": "unsafe"},
            ),
            catalog=catalog,
            handlers=handlers,
        )

        assert reason == "step_failed"
        assert agent["sent_messages"] == []

    def test_approval_denial_blocks_side_effect(self):
        agent = ref.build_demo_agent()
        agent["auto_approve"] = False

        reason = ref.inner_loop(
            agent,
            max_cycles=1,
            plan_provider=lambda cycle: one_task(
                "SEND_MESSAGE",
                {"text": "blocked"},
            ),
        )

        assert reason == "step_failed"
        assert agent["sent_messages"] == []


class TestTriggerAndLifecycle:
    """Protect strict trigger and run event conventions."""

    def test_trigger_requires_explicit_fields_and_separate_dedupe_key(self):
        with pytest.raises(ValueError, match="source"):
            ref.normalize_trigger({"kind": "x", "payload": {}})
        trigger = ref.normalize_trigger(
            {
                "source": "test",
                "kind": "user_message",
                "payload": {},
                "dedupe_key": "business-key",
            }
        )
        assert trigger["id"].startswith("occ_")
        assert trigger["dedupe_key"] == "business-key"

    @pytest.mark.parametrize(
        "run_id,parent_run_id",
        [("", None), (3, None), ("child", ""), ("child", 3)],
    )
    def test_run_ids_must_be_non_empty_strings(
        self,
        memory,
        run_id,
        parent_run_id,
    ):
        with pytest.raises(ValueError):
            ref.emit_run_started(
                memory,
                run_id,
                {"source": "test", "kind": "x"},
                parent_run_id=parent_run_id,
            )

    def test_terminal_reason_is_bounded_and_terminal_is_unique(self, memory):
        trigger = {"id": "run-1", "source": "test", "kind": "user_message"}
        ref.emit_run_started(memory, "run-1", trigger, parent_run_id="parent-1")
        with pytest.raises(ValueError, match="unsupported terminal"):
            ref.emit_run_terminal(memory, "run-1", "invented", success=False)
        ref.emit_run_terminal(memory, "run-1", "done", success=True)
        with pytest.raises(ValueError, match="already emitted"):
            ref.emit_run_terminal(memory, "run-1", "done", success=True)

        events = memory.get_emits()
        assert events[0]["payload"]["parent_run_id"] == "parent-1"
        assert events[1]["payload"]["metrics"] == {}


class TestLoops:
    """Protect successful, failed, bounded, and fallback loop behavior."""

    def test_outer_loop_finishes_with_exact_reason_and_lifecycle(self):
        agent = ref.build_demo_agent()

        reason = ref.outer_loop(
            {"source": "test", "kind": "user_message", "payload": {}},
            agent,
        )

        assert reason == "done"
        assert agent["sent_messages"] == ["Hello from cycle 0"]
        assert [event["kind"] for event in agent["memory"].get_emits()] == [
            "run_started",
            "run_completed",
        ]

    def test_outer_loop_rest_short_circuits(self):
        agent = ref.build_demo_agent()
        reason = ref.outer_loop(
            {"source": "test", "kind": "heartbeat", "payload": {}},
            agent,
        )
        assert reason == "triage_rest"
        assert agent["sent_messages"] == []

    def test_task_budget_stops_before_third_task(self):
        agent = ref.build_demo_agent()
        plan = one_task("READ_NOTE", {"note_id": "intro"}) * 3

        reason = ref.inner_loop(
            agent,
            max_cycles=1,
            max_tasks=2,
            plan_provider=lambda cycle: plan,
        )

        assert reason == "task_budget"

    def test_boundary_tail_is_forecast_and_fallback_never_sends(self):
        agent = ref.build_demo_agent()
        plan = [
            [{"action": "READ_NOTE", "params": {"note_id": "intro"}}],
            [{"action": "REPLAN"}],
            [{"action": "SEND_MESSAGE", "params": {"text": "forecast"}}],
        ]

        reason = ref.inner_loop(
            agent,
            max_cycles=1,
            plan_provider=lambda cycle: plan,
        )

        logs = agent["memory"].get_events(event_types=["log"])
        assert reason == "max_cycles"
        assert agent["sent_messages"] == []
        assert any("fallback required" in event["content"] for event in logs)


class TestSubRunAndChron:
    """Protect explicit child isolation and public CHRON adaptation."""

    def test_sub_run_success_does_not_mutate_parent(self):
        parent = MEMORY()
        parent.set_var("marker", "parent")

        receipt, outputs = ref.run_sub_loop(parent, ["READ_NOTE"])

        assert receipt["status"] == "ok"
        assert receipt["data"]["reason"] == "reflection_done"
        assert outputs == {}
        assert parent.get_var("marker") == "parent"
        assert len(parent.get_events()) == 1

    @pytest.mark.parametrize("allowed", [[], ["UNKNOWN"]])
    def test_sub_run_rejects_empty_or_unknown_actions(self, allowed):
        with pytest.raises(ValueError, match="allowed_actions|unknown"):
            ref.run_sub_loop(MEMORY(), allowed)

    def test_sub_run_reports_denied_action_as_failure(self):
        receipt, outputs = ref.run_sub_loop(MEMORY(), ["SEND_MESSAGE"])
        assert receipt["status"] == "failed"
        assert receipt["data"]["reason"] == "step_failed"
        assert outputs == {}

    def test_sub_run_reports_cycle_exhaustion_as_partial(self):
        receipt, outputs = ref.run_sub_loop(MEMORY(), ["REPLAN"])
        assert receipt["status"] == "partial"
        assert receipt["gaps"] == ["max_cycles"]
        assert outputs == {}

    def test_sub_run_rejects_non_json_output_without_raising(self):
        receipt, outputs = ref.run_sub_loop(
            MEMORY(),
            ["READ_NOTE"],
            output_keys=["memory"],
        )

        assert receipt["status"] == "failed"
        assert receipt["data"]["rejected_output"] == "memory"
        assert outputs == {}

    def test_chron_adapter_uses_public_fire_and_fresh_execution_ids(self):
        seen = []
        template = ref.build_demo_agent()
        template["product_state"] = {"executions": []}

        def capture(trigger, agent, run_id=None):
            seen.append((trigger["id"], run_id))
            agent["product_state"]["executions"].append(trigger["id"])
            seen.append(list(agent["product_state"]["executions"]))

        chron = CHRON(name="test")
        adapter = ref.make_chron_outer_loop_adapter(
            capture,
            template,
        )
        chron.add("job", every=3600, action=adapter)

        first = chron.fire("job")
        second = chron.fire("job")

        assert first["status"] == second["status"] == "ok"
        first_ids = seen[0]
        first_nested_state = seen[1]
        second_ids = seen[2]
        second_nested_state = seen[3]
        assert first_ids[0] == first_ids[1]
        assert second_ids[0] == second_ids[1]
        assert first_ids[0] != second_ids[0]
        assert first_nested_state == [first_ids[0]]
        assert second_nested_state == [second_ids[0]]
        assert template["product_state"]["executions"] == []
