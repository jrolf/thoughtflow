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
