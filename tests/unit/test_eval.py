"""
Unit tests for the ThoughtFlow eval harness.

The harness runs a flow (any memory -> memory callable) over test cases,
each in a fresh isolated MEMORY, containing exceptions as failures.
"""

from __future__ import annotations

from thoughtflow import MEMORY
from thoughtflow.eval import Harness, TestCase


def echo_flow(memory):
    """A trivial flow: respond to the last user message."""
    user_msg = memory.last_user_msg(content_only=True) or ""
    memory.add_msg("assistant", "Echo: {}".format(user_msg))
    return memory


def exploding_flow(memory):
    """A flow that always raises."""
    raise RuntimeError("boom")


class TestTestCase:
    """Tests for TestCase setup and evaluation."""

    def test_setup_callable_prepares_memory(self):
        """setup= must run against a fresh MEMORY."""
        case = TestCase(name="t", setup=lambda m: m.add_msg("user", "Hi"))
        memory = case.prepare()

        assert memory.last_user_msg(content_only=True) == "Hi"

    def test_messages_convenience_prepares_memory(self):
        """messages= must populate the fresh MEMORY."""
        case = TestCase(name="t", messages=[{"role": "user", "content": "Hi"}])
        memory = case.prepare()

        assert memory.last_user_msg(content_only=True) == "Hi"

    def test_check_predicate_evaluates_memory(self):
        """check= must receive the result MEMORY."""
        case = TestCase(
            name="t",
            check=lambda m: m.get_var("score") == 10,
        )
        memory = MEMORY()
        memory.set_var("score", 10)

        assert case.evaluate(memory) is True

    def test_expected_string_compares_last_assistant_msg(self):
        """expected= as a string must compare against the final response."""
        case = TestCase(name="t", expected="Echo: Hi")
        memory = MEMORY()
        memory.add_msg("assistant", "Echo: Hi")

        assert case.evaluate(memory) is True

    def test_expected_callable_validates_response(self):
        """expected= as a callable must receive the response string."""
        case = TestCase(name="t", expected=lambda r: "echo" in r.lower())
        memory = MEMORY()
        memory.add_msg("assistant", "Echo: Hi")

        assert case.evaluate(memory) is True

    def test_no_expectations_passes_on_completion(self):
        """A case with no check/expected passes when the flow completes."""
        case = TestCase(name="t")
        assert case.evaluate(MEMORY()) is True


class TestHarness:
    """Tests for Harness.run()."""

    def test_run_executes_all_cases(self):
        """run() must execute every case and report results."""
        harness = Harness([
            TestCase(name="a", setup=lambda m: m.add_msg("user", "one"),
                     expected="Echo: one"),
            TestCase(name="b", setup=lambda m: m.add_msg("user", "two"),
                     expected="Echo: two"),
        ])

        results = harness.run(echo_flow)

        assert results.total_count == 2
        assert results.passed_count == 2
        assert results.failed_count == 0
        assert results.pass_rate == 1.0

    def test_run_reports_failures(self):
        """A failing expectation must be reported, not raised."""
        harness = Harness([
            TestCase(name="wrong", setup=lambda m: m.add_msg("user", "x"),
                     expected="Something else"),
        ])

        results = harness.run(echo_flow)

        assert results.failed_count == 1
        assert results.failures[0].test_case.name == "wrong"
        assert results.summary()["failures"] == ["wrong"]

    def test_run_contains_exceptions_as_failures(self):
        """A flow that raises must produce a failed result with the error."""
        harness = Harness([TestCase(name="explodes")])

        results = harness.run(exploding_flow)

        assert results.failed_count == 1
        assert "RuntimeError" in results.results[0].error

    def test_cases_run_in_isolated_memories(self):
        """Each case must start from a fresh MEMORY."""
        seen_counts = []

        def counting_flow(memory):
            seen_counts.append(len(memory.get_msgs()))
            return echo_flow(memory)

        harness = Harness([
            TestCase(name="a", setup=lambda m: m.add_msg("user", "one")),
            TestCase(name="b", setup=lambda m: m.add_msg("user", "two")),
        ])
        harness.run(counting_flow)

        assert seen_counts == [1, 1]

    def test_filter_tags_limits_run(self):
        """filter_tags must run only matching cases."""
        harness = Harness([
            TestCase(name="fast", tags=["smoke"]),
            TestCase(name="slow", tags=["nightly"]),
        ])

        results = harness.run(echo_flow, filter_tags=["smoke"])

        assert results.total_count == 1
        assert results.results[0].test_case.name == "fast"

    def test_surfaces_absorbed_errors_strict_mode_and_partial_memory(self):
        """Issue #30: Harness tracks absorbed THOUGHT failures, strict mode, and partial memory."""
        from thoughtflow import LLM, THOUGHT

        empty_replay = LLM.replay(MEMORY())
        dead_step = THOUGHT(name="dead", llm=empty_replay, prompt="Hello")

        def partially_dead_flow(mem):
            mem = dead_step(mem)
            mem.add_msg("assistant", "Fallback reply")
            return mem

        case = TestCase(
            name="masked_failure",
            setup=lambda m: m.add_msg("user", "Hi"),
            check=lambda m: (m.last_asst_msg(content_only=True) == "Fallback reply", "unexpected reply"),
        )

        # Non-strict: case passes check, but absorbed_errors surfaces the dead THOUGHT
        permissive = Harness([case]).run(partially_dead_flow, strict=False)
        assert permissive.passed_count == 1
        assert len(permissive.results[0].absorbed_errors) == 1
        assert permissive.results[0].absorbed_errors[0]["error_class"] == "replay_miss"
        assert permissive.summary()["cases_with_absorbed_errors"] == ["masked_failure"]

        # Strict: absorbed error fails the case with an explicit reason
        strict_res = Harness([case]).run(partially_dead_flow, strict=True)
        assert strict_res.failed_count == 1
        assert "strict mode" in strict_res.failures[0].reason

        # Exception after mutating memory preserves partial memory on TestResult
        def crash_midway(mem):
            mem.set_var("progress", "step_1_done")
            mem.add_msg("assistant", "Partial output")
            raise ValueError("midway crash")

        crash_res = Harness([TestCase(name="crash")]).run(crash_midway)
        assert crash_res.failed_count == 1
        assert crash_res.failures[0].memory is not None
        assert crash_res.failures[0].memory.get_var("progress") == "step_1_done"
        assert crash_res.failures[0].response == "Partial output"

    def test_result_includes_memory_for_inspection(self):
        """TestResult must carry the result MEMORY for post-hoc inspection."""
        harness = Harness([
            TestCase(name="a", setup=lambda m: m.add_msg("user", "hello")),
        ])

        results = harness.run(echo_flow)

        assert results.results[0].memory is not None
        assert results.results[0].response == "Echo: hello"

    def test_add_and_add_many(self):
        """add()/add_many() must append cases."""
        harness = Harness()
        harness.add(TestCase(name="a"))
        harness.add_many([TestCase(name="b"), TestCase(name="c")])

        assert len(harness.test_cases) == 3

    def test_multi_trial_pass_rates_usage_save_load_and_compare(self, tmp_path):
        """Issue #31: Harness supports trials=N pass rates, usage/cost aggregation, save/load, and noise-aware compare."""
        counters = {"flaky": 0}

        def stochastic_flow(mem):
            name = mem.last_user_msg(content_only=True)
            mem.emit("usage", {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.001})
            if name == "flaky":
                counters["flaky"] += 1
                # Passes 3 out of 5 trials
                reply = "ok" if counters["flaky"] <= 3 else "miss"
            else:
                reply = "ok"
            mem.add_msg("assistant", reply)
            return mem

        cases = [
            TestCase(name="solid", messages=[{"role": "user", "content": "solid"}], expected="ok"),
            TestCase(name="flaky", messages=[{"role": "user", "content": "flaky"}], expected="ok"),
        ]
        results = Harness(cases).run(stochastic_flow, trials=5)

        assert results.results[0].trials == 5
        assert results.results[0].passes == 5
        assert results.results[0].pass_rate == 1.0
        assert results.results[1].passes == 3
        assert results.results[1].pass_rate == 0.6
        # Suite pass_rate averages per-case pass rates: (1.0 + 0.6) / 2 = 0.8
        assert results.pass_rate == 0.8
        assert results.usage["calls"] == 10
        assert results.usage["total_tokens"] == 150
        assert results.total_cost == 0.01

        # Save to JSON baseline and reload via Harness.load()
        baseline_file = tmp_path / "baseline.json"
        results.save(baseline_file)
        loaded = Harness.load(baseline_file)
        assert loaded.pass_rate == 0.8
        assert loaded.usage["total_tokens"] == 150

        # Small 1-case wobble on a 15-case single-trial suite does NOT exceed noise
        suite_15 = [TestCase(name="c{}".format(i), expected="ok") for i in range(15)]
        base_15 = Harness(suite_15).run(
            lambda m: (m.add_msg("assistant", "ok" if len(m.events) >= 0 else "no"), m)[1]
        )
        # Flip exactly 1 of 15 cases in baseline (12/15 vs 13/15 -> delta ~ 0.067)
        base_dict = base_15.to_dict()
        for idx_r in range(3):
            base_dict["results"][idx_r]["passed"] = False
            base_dict["results"][idx_r]["passes"] = 0
            base_dict["results"][idx_r]["pass_rate"] = 0.0
        cand_dict = base_15.to_dict()
        for idx_r in range(2):
            cand_dict["results"][idx_r]["passed"] = False
            cand_dict["results"][idx_r]["passes"] = 0
            cand_dict["results"][idx_r]["pass_rate"] = 0.0

        cand_15 = Harness.load( __import__("json").dumps(cand_dict) )
        wobble_cmp = cand_15.compare(base_dict)
        assert 0.06 < wobble_cmp["delta"] < 0.07
        assert wobble_cmp["exceeds_noise"] is False
        assert wobble_cmp["improvements"] == ["c2"]

        # Genuine jump (e.g. 0.40 -> 1.00 across 15 cases) clearly exceeds noise
        for idx_r in range(9):
            base_dict["results"][idx_r]["passed"] = False
            base_dict["results"][idx_r]["passes"] = 0
            base_dict["results"][idx_r]["pass_rate"] = 0.0
        signal_cmp = base_15.compare(base_dict)
        assert signal_cmp["delta"] == 0.6
        assert signal_cmp["exceeds_noise"] is True
        assert signal_cmp["direction"] == "improved"
