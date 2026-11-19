"""
Cross-primitive crash and edge-case sweep (#51).

Exercises boundary inputs (empty strings, Unicode/emoji, nested JSON braces,
malformed model outputs, missing files/commands, thread-pool fan-out, and JSON
round-trips) across ThoughtFlow's core primitives so edge-case inputs degrade
cleanly rather than raising unexpected exceptions.
"""

from __future__ import annotations

import json

from thoughtflow import (
    ACTION,
    AGENT,
    CHAT,
    CHRON,
    DECIDE,
    DELEGATE,
    MEMORY,
    NOOP,
    PLAN,
    READ,
    RUN,
    THOUGHT,
    TOOL,
    WORKFLOW,
    map_thought,
    run_plan,
)
from thoughtflow._util import render_vars, require_grounded_quotes
from thoughtflow.embed import cosine_retrieve, cosine_similarity


class _StaticLLM:
    """Minimal deterministic LLM stub for hermetic boundary testing."""

    def __init__(self, reply=""):
        self.reply = reply
        self.last_error = None
        self.last_finish_reason = "stop"
        self.last_usage = {"prompt_tokens": 1, "completion_tokens": 1}

    def call(self, msgs, params=None, output_schema=None):
        if callable(self.reply):
            return [self.reply(msgs, params, output_schema)]
        return [self.reply]


class TestCrossPrimitiveCrashSweep:
    """Systematic boundary and stress checks across ThoughtFlow primitives."""

    def test_memory_unicode_slim_merge_and_atomic_save_roundtrip(self, tmp_path):
        mem_a = MEMORY()
        payload_text = "こんにちは 🚀 café — line1\nline2 {\"json\": [1, 2, 3]}"
        mem_a.add_msg("user", payload_text, channel="api")
        assert mem_a.upsert("bio", payload_text, metadata={"lang": "mixed"}) is True
        assert mem_a.upsert("bio", payload_text, metadata={"lang": "mixed"}) is False

        mem_b = mem_a.copy()
        mem_b.set_var("branch_only", {"nested": [True, None, 0, ""]})
        mem_a = mem_a.merge(mem_b)
        assert mem_a.get_var("branch_only") == {"nested": [True, None, 0, ""]}

        out_file = tmp_path / "session.json"
        mem_a.save(str(out_file), slim=True)
        reloaded = MEMORY.from_json(str(out_file))
        assert reloaded.get_var("bio") == payload_text
        assert reloaded.last_user_msg(content_only=True) == payload_text

    def test_thought_decide_plan_degrade_gracefully_on_empty_and_garbage_replies(self):
        empty_llm = _StaticLLM("")
        mem = MEMORY()

        t = THOUGHT(name="empty_t", llm=empty_llm, prompt="Hello", max_retries=1)
        mem = t(mem)
        assert mem.get_var("empty_t_result") is None
        assert mem.get_var("empty_t_outcome")["ok"] is False
        assert mem.get_var("empty_t_outcome")["error_class"] == "empty"

        d = DECIDE(
            name="garbage_d",
            llm=_StaticLLM("completely unrelated prose"),
            choices=["yes", "no"],
            abstain=True,
            default="fallback",
            max_retries=1,
        )
        assert d.run({"x": 1}, memory=mem) == "fallback"
        assert mem.get_var("garbage_d_source") == "default"

        p = PLAN(
            name="bad_p",
            llm=_StaticLLM("not a json array"),
            prompt="Goal",
            actions={"noop": "Do nothing"},
            max_retries=1,
        )
        mem = p(mem)
        assert mem.get_var("bad_p_result") is None
        assert mem.get_var("bad_p_outcome")["ok"] is False

    def test_actions_workflow_chron_and_chat_handle_errors_and_empty_inputs(self, tmp_path):
        mem = MEMORY()
        missing = READ(name="r", path=str(tmp_path / "does_not_exist.json"))
        bad_run = RUN(name="sh", command="exit 3", on_error="ignore")
        noop = NOOP(name="n")

        wf = WORKFLOW(name="resilient_wf", on_error="continue")
        wf.step(missing, name="read_step")
        wf.step(bad_run, name="run_step")
        wf.step(noop, name="noop_step")
        mem = wf(mem)

        assert mem.get_var("r_status") == "error"
        assert mem.get_var("sh_status") == "error"
        assert mem.get_var("n_status") == "ok"

        # CHRON empty tick & state file round-trip
        chron = CHRON(state_file=str(tmp_path / "chron_state.json"))
        chron.add("every_hour", schedule="@hourly", action=lambda m: m, memory=MEMORY())
        due = chron.tick()
        assert isinstance(due, list)

        # CHAT single scripted turn
        responder = THOUGHT(name="reply", llm=_StaticLLM("Hello back!"), prompt="{last_user_msg}")
        chat = CHAT(responder)
        assert chat.turn("Ping") == "Hello back!"

    def test_concurrent_fanout_and_stateless_helpers_edge_cases(self):
        import pytest

        with pytest.raises(ValueError):
            cosine_similarity([], [])
        assert cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0
        assert cosine_retrieve([1.0, 0.0], []) == []

        assert render_vars(None) == "(none)"
        validator = require_grounded_quotes("", min_quotes=1)
        ok, _ = validator('"anything"')
        assert ok is False

        # Concurrent map_thought + run_plan + DELEGATE.dispatch_many
        step = THOUGHT(
            name="echo",
            llm=_StaticLLM(lambda msgs, p, s: msgs[-1]["content"]),
            prompt="v={item}",
            include_history=False,
        )
        base = MEMORY()
        mapped = map_thought(step, base, items=list(range(8)), parallel=True)
        assert [m["result"] for m in mapped] == ["v={}".format(i) for i in range(8)]

        delg = DELEGATE(agents={"a": lambda m: "ok_a", "b": lambda m: (_ for _ in ()).throw(ValueError("boom"))})
        reports = delg.dispatch_many(base, [("a", "go"), ("b", "go")], parallel=True)
        assert reports[0]["ok"] is True and reports[1]["ok"] is False

        receipts = run_plan([], base, {})
        assert receipts == []

        act1 = ACTION(name="p1", fn=lambda m, v: v * 2)
        act2 = ACTION(name="p2", fn=lambda m, v: v + 10)
        par_mem = MEMORY()
        par_rec = run_plan(
            [[
                {"action": "p1", "params": {"v": 3}, "reason": "double"},
                {"action": "p2", "params": {"v": 4}, "reason": "offset"},
            ]],
            par_mem,
            [act1, act2],
            parallel_inner=True,
        )
        assert [r["result"] for r in par_rec] == [6, 14]
        assert par_mem.get_var("p1_result") == 6
        assert par_mem.get_var("p2_result") == 14
        assert TOOL.from_action(act1, parameters={"v": {"type": "integer"}}, memory=par_mem)({"v": 5}) == 10

        # AGENT with zero tools and single response
        agent = AGENT(llm=_StaticLLM("direct reply"), tools=[], name="solo")
        out_mem = agent(MEMORY())
        assert out_mem.get_var("solo_result") is not None
        assert json.loads(out_mem.to_json(slim=True))["vars"]["solo_result"] is not None
