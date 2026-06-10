"""
Test harness for ThoughtFlow evaluations.

A test case is three plain things: a name, a way to set up a fresh MEMORY,
and a predicate over the MEMORY that comes back. A harness runs a flow
(any ``memory -> memory`` callable) over a list of cases and collects
results. That is the whole design — deterministic evaluation in ThoughtFlow
is ordinary Python over MEMORY, not a framework.

For fully offline, deterministic runs, build your flow around a replay LLM
(``LLM.replay(recorded_memory)``) — see thoughtflow.llm.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable

from thoughtflow.memory import MEMORY


@dataclass
class TestCase:
    """A single test case for evaluating a flow.

    Attributes:
        name: Human-readable name for the test.
        setup: Callable that prepares a fresh MEMORY (e.g. adds the user
            message). Receives the MEMORY; return value is ignored.
        check: Predicate over the result MEMORY. Returns truthy for pass.
            When omitted, the case passes if the flow completes without
            raising.
        messages: Convenience alternative to ``setup`` — a list of message
            dicts ({'role': ..., 'content': ...}) added to the fresh MEMORY
            before the flow runs. Ignored when ``setup`` is provided.
        expected: Convenience alternative to ``check`` — an exact string
            (or callable str predicate) compared against the final assistant
            message. Ignored when ``check`` is provided.
        tags: Tags for filtering/grouping tests.
        metadata: Additional test metadata.
    """

    # Tell pytest this is not a test class despite the name
    __test__ = False

    name: str
    setup: Callable[[MEMORY], Any] | None = None
    check: Callable[[MEMORY], Any] | None = None
    messages: list[dict[str, Any]] | None = None
    expected: str | Callable[[str], bool] | None = None
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def prepare(self) -> MEMORY:
        """Build the fresh MEMORY this case starts from."""
        memory = MEMORY()
        if self.setup is not None:
            self.setup(memory)
        elif self.messages:
            for msg in self.messages:
                memory.add_msg(msg.get("role", "user"), msg.get("content", ""))
        return memory

    def evaluate(self, memory: MEMORY) -> bool:
        """Evaluate the result MEMORY against this case's expectations."""
        if self.check is not None:
            return bool(self.check(memory))
        if self.expected is not None:
            response = memory.last_asst_msg(content_only=True) or ""
            if callable(self.expected):
                return bool(self.expected(response))
            return response == self.expected
        return True


@dataclass
class TestResult:
    """Result of running a single test case.

    Attributes:
        test_case: The test case that was run.
        passed: Whether the test passed.
        response: The final assistant message from the result MEMORY.
        error: Error message when the flow raised.
        duration_ms: How long the case took.
        memory: The result MEMORY (for post-hoc inspection).
    """

    # Tell pytest this is not a test class despite the name
    __test__ = False

    test_case: TestCase
    passed: bool
    response: str | None = None
    error: str | None = None
    duration_ms: int | None = None
    memory: MEMORY | None = None


@dataclass
class HarnessResults:
    """Results from running a harness.

    Attributes:
        results: Individual test results.
        metadata: Harness-level metadata.
    """

    results: list[TestResult] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total_count(self) -> int:
        """Total number of tests run."""
        return len(self.results)

    @property
    def passed_count(self) -> int:
        """Number of tests that passed."""
        return sum(1 for r in self.results if r.passed)

    @property
    def failed_count(self) -> int:
        """Number of tests that failed."""
        return self.total_count - self.passed_count

    @property
    def pass_rate(self) -> float:
        """Fraction of tests that passed (0.0 - 1.0)."""
        if self.total_count == 0:
            return 0.0
        return self.passed_count / self.total_count

    @property
    def failures(self) -> list[TestResult]:
        """The failing results, for quick inspection."""
        return [r for r in self.results if not r.passed]

    def summary(self) -> dict[str, Any]:
        """Get a summary dict of the results."""
        return {
            "total": self.total_count,
            "passed": self.passed_count,
            "failed": self.failed_count,
            "pass_rate": self.pass_rate,
            "failures": [r.test_case.name for r in self.failures],
        }


class Harness:
    """Runs a flow against a collection of test cases.

    A flow is any ``memory -> memory`` callable — a THOUGHT, an AGENT, a
    WORKFLOW, or a plain function. Each case runs in a fresh, isolated
    MEMORY; exceptions are contained as failures rather than raised.

    Example:
        >>> harness = Harness([
        ...     TestCase(
        ...         name="greeting",
        ...         setup=lambda m: m.add_msg("user", "Hello!"),
        ...         check=lambda m: "hello" in (m.last_asst_msg(content_only=True) or "").lower(),
        ...     ),
        ... ])
        >>> results = harness.run(my_flow)
        >>> assert results.failed_count == 0, results.summary()
    """

    def __init__(self, test_cases: list[TestCase] | None = None) -> None:
        """Initialize the harness, optionally with test cases."""
        self.test_cases: list[TestCase] = list(test_cases or [])

    def add(self, test_case: TestCase) -> None:
        """Add a test case to the harness."""
        self.test_cases.append(test_case)

    def add_many(self, test_cases: list[TestCase]) -> None:
        """Add multiple test cases."""
        self.test_cases.extend(test_cases)

    def filter_by_tags(self, tags: list[str]) -> list[TestCase]:
        """Return test cases matching any of the specified tags."""
        return [tc for tc in self.test_cases if any(t in tc.tags for t in tags)]

    def run(
        self,
        flow: Callable[[MEMORY], MEMORY],
        filter_tags: list[str] | None = None,
    ) -> HarnessResults:
        """Run all (or tag-filtered) test cases against a flow.

        Args:
            flow: Any ``memory -> memory`` callable.
            filter_tags: Optional tags to filter which cases run.

        Returns:
            HarnessResults with one TestResult per case.
        """
        cases = self.filter_by_tags(filter_tags) if filter_tags else self.test_cases

        results = HarnessResults()
        for case in cases:
            start = time.time()
            try:
                memory = case.prepare()
                memory = flow(memory)
                passed = case.evaluate(memory)
                results.results.append(TestResult(
                    test_case=case,
                    passed=passed,
                    response=memory.last_asst_msg(content_only=True),
                    duration_ms=int((time.time() - start) * 1000),
                    memory=memory,
                ))
            except Exception as e:
                results.results.append(TestResult(
                    test_case=case,
                    passed=False,
                    error="{}: {}".format(type(e).__name__, e),
                    duration_ms=int((time.time() - start) * 1000),
                ))
        return results
