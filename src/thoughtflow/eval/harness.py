"""
Test harness for ThoughtFlow evaluations.

Provides structured test cases and evaluation harnesses for
systematic agent testing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from thoughtflow.agent import Agent
    from thoughtflow.message import MessageList


@dataclass
class TestCase:
    """A single test case for agent evaluation.

    Attributes:
        name: Human-readable name for the test.
        messages: Input messages for the test.
        params: Optional call parameters.
        expected: Expected response (exact match or callable validator).
        tags: Tags for filtering/grouping tests.
        metadata: Additional test metadata.
    """

    name: str
    messages: MessageList
    params: dict[str, Any] | None = None
    expected: str | Callable[[str], bool] | None = None
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self, response: str) -> bool:
        """Validate a response against expectations.

        Args:
            response: The agent's response.

        Returns:
            True if valid, False otherwise.
        """
        if self.expected is None:
            return True
        if callable(self.expected):
            return self.expected(response)
        return response == self.expected


@dataclass
class TestResult:
    """Result of running a test case.

    Attributes:
        test_case: The test case that was run.
        passed: Whether the test passed.
        response: The agent's response.
        error: Error message if the test failed.
        duration_ms: How long the test took.
        metadata: Additional result metadata.
    """

    test_case: TestCase
    passed: bool
    response: str | None = None
    error: str | None = None
    duration_ms: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class Harness:
    """Test harness for running evaluation suites.

    The Harness provides a structured way to:
    - Define test cases
    - Run them against agents
    - Collect and analyze results

    Example:
        >>> harness = Harness()
        >>>
        >>> # Add test cases
        >>> harness.add(TestCase(
        ...     name="greeting",
        ...     messages=[{"role": "user", "content": "Hello!"}],
        ...     expected=lambda r: "hello" in r.lower()
        ... ))
        >>>
        >>> # Run all tests
        >>> results = harness.run(agent)
        >>>
        >>> # Check results
        >>> print(f"Passed: {results.passed_count}/{results.total_count}")
    """

    def __init__(self) -> None:
        """Initialize an empty harness."""
        self.test_cases: list[TestCase] = []

    def add(self, test_case: TestCase) -> None:
        """Add a test case to the harness.

        Args:
            test_case: The test case to add.
        """
        self.test_cases.append(test_case)

    def add_many(self, test_cases: list[TestCase]) -> None:
        """Add multiple test cases.

        Args:
            test_cases: List of test cases to add.
        """
        self.test_cases.extend(test_cases)

    def filter_by_tags(self, tags: list[str]) -> list[TestCase]:
        """Filter test cases by tags.

        Args:
            tags: Tags to filter by.

        Returns:
            Test cases matching any of the specified tags.
        """
        return [tc for tc in self.test_cases if any(t in tc.tags for t in tags)]

    def run(
        self,
        agent: Agent,
        filter_tags: list[str] | None = None,
    ) -> HarnessResults:
        """Run all test cases against an agent.

        Args:
            agent: The agent to test.
            filter_tags: Optional tags to filter which tests to run.

        Returns:
            HarnessResults with all test results.

        Raises:
            NotImplementedError: This is a placeholder implementation.
        """
        # TODO: Implement test execution
        raise NotImplementedError(
            "Harness.run() is not yet implemented. "
            "This is a placeholder for the ThoughtFlow alpha release."
        )


@dataclass
class HarnessResults:
    """Results from running a test harness.

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
        """Percentage of tests that passed."""
        if self.total_count == 0:
            return 0.0
        return self.passed_count / self.total_count

    def summary(self) -> dict[str, Any]:
        """Get a summary of the results.

        Returns:
            Dict with summary statistics.
        """
        return {
            "total": self.total_count,
            "passed": self.passed_count,
            "failed": self.failed_count,
            "pass_rate": self.pass_rate,
        }
