"""
Test harness for ThoughtFlow evaluations.

A test case is three plain things: a name, a way to set up a fresh MEMORY,
and a predicate over the MEMORY that comes back. A harness runs a flow
(any ``memory -> memory`` callable) over a list of cases and collects
results. That is the whole design — deterministic evaluation in ThoughtFlow
is ordinary Python over MEMORY, not a framework.

For fully offline, deterministic runs, build your flow around a replay LLM
(``LLM.replay(recorded_memory)`` or ``LLM.cassette(path, live=...)``) — see
``thoughtflow.llm``.
"""

from __future__ import annotations

import json
import math
import os
import tempfile
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from thoughtflow.llm import _accumulate_usage_into, _empty_usage_ledger
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
        passed, _reason, _observed = self.evaluate_with_detail(memory)
        return passed

    def evaluate_with_detail(
        self, memory: MEMORY
    ) -> tuple[bool, str | None, Any]:
        """Evaluate expectations and return (passed, failure_reason, observed)."""
        if self.check is not None:
            verdict = self.check(memory)
            if isinstance(verdict, tuple) and len(verdict) >= 2:
                ok = bool(verdict[0])
                why = str(verdict[1]) if verdict[1] is not None else None
                observed = verdict[2] if len(verdict) >= 3 else None
                return ok, (None if ok else (why or "check returned False")), observed
            ok = bool(verdict)
            return ok, (None if ok else "check returned False"), None
        if self.expected is not None:
            response = memory.last_asst_msg(content_only=True) or ""
            if callable(self.expected):
                ok = bool(self.expected(response))
                reason = None if ok else "expected predicate returned False for {!r}".format(response)
                return ok, reason, response
            ok = response == self.expected
            reason = None if ok else "expected {!r}, got {!r}".format(self.expected, response)
            return ok, reason, response
        return True, None, None


def _collect_absorbed_errors(memory: MEMORY | None) -> list[dict[str, Any]]:
    """Extract structured THOUGHT/primitive failures absorbed inside ``memory``."""
    if memory is None:
        return []
    absorbed: list[dict[str, Any]] = []
    seen_thoughts: set[str] = set()

    if hasattr(memory, "get_all_vars") and callable(getattr(memory, "get_all_vars", None)):
        all_vars = memory.get_all_vars()
    elif hasattr(memory, "vars") and isinstance(memory.vars, dict):
        all_vars = memory.vars
    else:
        all_vars = {}

    for key, val in all_vars.items():
        if key.endswith("_outcome") and isinstance(val, dict) and val.get("ok") is False:
            thought_name = key[:-len("_outcome")]
            seen_thoughts.add(thought_name)
            absorbed.append({
                "source": thought_name,
                "error_class": val.get("error_class"),
                "reason": val.get("error"),
                "attempts": val.get("attempts"),
            })

    for key, val in all_vars.items():
        if key.endswith("_last_error") and isinstance(val, dict):
            thought_name = key[:-len("_last_error")]
            if thought_name in seen_thoughts:
                continue
            absorbed.append({
                "source": thought_name,
                "error_class": val.get("failure_kind"),
                "reason": val.get("reason"),
                "attempts": len(val.get("attempts") or []),
            })

    return absorbed


def _collect_memory_usage(memory: MEMORY | None) -> dict[str, Any]:
    """
    Aggregate token and cost usage recorded inside ``memory``.

    Reads ``'usage'`` emit events first; if none were emitted directly onto the
    flow memory, falls back to usage attached to recorded exchanges.

    Args:
        memory: Result MEMORY from one trial execution.

    Returns:
        dict: Standard usage ledger with ``calls``, token counts, and ``cost``.
    """
    ledger = _empty_usage_ledger()
    if memory is None:
        return ledger

    if hasattr(memory, "get_emits") and callable(getattr(memory, "get_emits", None)):
        emits = memory.get_emits("usage")
        if emits:
            for emit_event in emits:
                payload = emit_event.get("payload")
                if isinstance(payload, dict):
                    _accumulate_usage_into(ledger, payload)
            return ledger

    if hasattr(memory, "get_exchanges") and callable(getattr(memory, "get_exchanges", None)):
        for exchange in memory.get_exchanges():
            ex_usage = exchange.get("usage")
            if ex_usage is None:
                resp = exchange.get("response")
                if isinstance(resp, list) and resp and isinstance(resp[0], dict):
                    ex_usage = resp[0].get("usage")
            if isinstance(ex_usage, dict):
                _accumulate_usage_into(ledger, ex_usage)

    return ledger


def _merge_usage_ledgers(ledgers: list[dict[str, Any]]) -> dict[str, Any]:
    """Sum multiple pre-aggregated usage ledger dicts into a single ledger."""
    merged = _empty_usage_ledger()
    for item in ledgers:
        if not isinstance(item, dict):
            continue
        merged["calls"] += int(item.get("calls") or 0)
        merged["prompt_tokens"] += int(item.get("prompt_tokens") or 0)
        merged["completion_tokens"] += int(item.get("completion_tokens") or 0)
        merged["total_tokens"] += int(item.get("total_tokens") or 0)
        merged["reasoning_tokens"] += int(item.get("reasoning_tokens") or 0)
        merged["cached_tokens"] += int(item.get("cached_tokens") or 0)
        merged["cost"] = round(merged["cost"] + float(item.get("cost") or 0.0), 10)
    return merged


def _json_safe_value(value: Any) -> Any:
    """Coerce arbitrary observed/metadata values into JSON-serializable primitives."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_json_safe_value(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _json_safe_value(v) for k, v in value.items()}
    return repr(value)


@dataclass
class TestResult:
    """Result of running a single test case (across 1 or more trials).

    Attributes:
        test_case: The test case that was run.
        passed: Whether the case met ``pass_threshold`` across its trials.
        response: Final assistant message from the last (or failing) trial MEMORY.
        error: Error message when the flow or check raised.
        reason: Human-readable explanation when ``passed`` is False.
        observed: Observed value surfaced by ``expected`` or a 3-tuple ``check``.
        absorbed_errors: Structured errors absorbed by primitives during the run.
        duration_ms: Total wall-clock duration across all trials for this case.
        memory: Result MEMORY (preserved even when the flow or check raises).
        trials: Number of independent trials run for this case (default 1).
        passes: Number of trials that passed.
        pass_rate: Fraction of trials that passed in ``[0.0, 1.0]``.
        usage: Aggregated token and cost usage across all trials of this case.
    """

    # Tell pytest this is not a test class despite the name
    __test__ = False

    test_case: TestCase
    passed: bool
    response: str | None = None
    error: str | None = None
    reason: str | None = None
    observed: Any = None
    absorbed_errors: list[dict[str, Any]] = field(default_factory=list)
    duration_ms: int | None = None
    memory: MEMORY | None = None
    trials: int = 1
    passes: int | None = None
    pass_rate: float | None = None
    usage: dict[str, Any] = field(default_factory=_empty_usage_ledger)

    def __post_init__(self) -> None:
        """Populate default ``passes`` and ``pass_rate`` when constructed directly."""
        if self.trials < 1:
            self.trials = 1
        if self.passes is None:
            self.passes = self.trials if self.passed else 0
        if self.pass_rate is None:
            self.pass_rate = self.passes / self.trials

    def to_dict(self) -> dict[str, Any]:
        """Serialize this result to a portable JSON-ready dict (excluding live MEMORY)."""
        return {
            "name": self.test_case.name,
            "tags": list(self.test_case.tags),
            "case_metadata": _json_safe_value(self.test_case.metadata),
            "passed": self.passed,
            "trials": self.trials,
            "passes": self.passes,
            "pass_rate": self.pass_rate,
            "response": self.response,
            "error": self.error,
            "reason": self.reason,
            "observed": _json_safe_value(self.observed),
            "absorbed_errors": _json_safe_value(self.absorbed_errors),
            "duration_ms": self.duration_ms,
            "usage": dict(self.usage),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TestResult:
        """Rehydrate a ``TestResult`` from a serialized dictionary."""
        case = TestCase(
            name=str(data.get("name", "")),
            tags=list(data.get("tags") or []),
            metadata=dict(data.get("case_metadata") or {}),
        )
        return cls(
            test_case=case,
            passed=bool(data.get("passed", False)),
            response=data.get("response"),
            error=data.get("error"),
            reason=data.get("reason"),
            observed=data.get("observed"),
            absorbed_errors=list(data.get("absorbed_errors") or []),
            duration_ms=data.get("duration_ms"),
            memory=None,
            trials=int(data.get("trials", 1)),
            passes=data.get("passes"),
            pass_rate=data.get("pass_rate"),
            usage=_merge_usage_ledgers([data.get("usage") or {}]),
        )


@dataclass
class HarnessResults:
    """Results from running a harness.

    Attributes:
        results: Individual test results (one per case).
        metadata: Harness-level metadata (e.g. ``trials``, ``strict``).
    """

    results: list[TestResult] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total_count(self) -> int:
        """Total number of test cases run."""
        return len(self.results)

    @property
    def passed_count(self) -> int:
        """Number of cases whose trial pass rate met ``pass_threshold``."""
        return sum(1 for r in self.results if r.passed)

    @property
    def failed_count(self) -> int:
        """Number of cases that failed."""
        return self.total_count - self.passed_count

    @property
    def pass_rate(self) -> float:
        """Mean empirical pass rate across all cases and trials (0.0 - 1.0)."""
        if self.total_count == 0:
            return 0.0
        total_rate = sum(
            (r.pass_rate if r.pass_rate is not None else (1.0 if r.passed else 0.0))
            for r in self.results
        )
        return total_rate / self.total_count

    @property
    def usage(self) -> dict[str, Any]:
        """Total token and cost usage aggregated across all cases and trials."""
        return _merge_usage_ledgers([r.usage for r in self.results])

    @property
    def total_cost(self) -> float:
        """Total monetary cost across all cases and trials."""
        return float(self.usage.get("cost") or 0.0)

    @property
    def failures(self) -> list[TestResult]:
        """The failing results, for quick inspection."""
        return [r for r in self.results if not r.passed]

    def summary(self) -> dict[str, Any]:
        """Get a summary dict of the results, including trials and usage."""
        absorbed_cases = [
            r.test_case.name for r in self.results if r.absorbed_errors
        ]
        return {
            "total": self.total_count,
            "passed": self.passed_count,
            "failed": self.failed_count,
            "pass_rate": self.pass_rate,
            "trials": self.metadata.get("trials", 1),
            "failures": [r.test_case.name for r in self.failures],
            "cases_with_absorbed_errors": absorbed_cases,
            "usage": self.usage,
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize the full evaluation report to a JSON-compatible dictionary."""
        return {
            "version": "1.0",
            "metadata": _json_safe_value(self.metadata),
            "summary": self.summary(),
            "results": [r.to_dict() for r in self.results],
        }

    def to_json(self, indent: int | None = 2) -> str:
        """Serialize the evaluation report to a JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def save(self, path: str | os.PathLike[str], indent: int | None = 2) -> None:
        """
        Atomically write serialized results to ``path`` for CI baselining.

        Args:
            path: Destination JSON file path.
            indent: JSON indentation (default 2).
        """
        target = os.path.abspath(os.fspath(path))
        parent = os.path.dirname(target)
        if parent:
            os.makedirs(parent, exist_ok=True)
        payload = self.to_json(indent=indent)
        fd, tmp_path = tempfile.mkstemp(prefix=".harness_", suffix=".tmp", dir=parent or None)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
            os.replace(tmp_path, target)
        except Exception:
            if os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
            raise

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HarnessResults:
        """Rehydrate ``HarnessResults`` from a dictionary produced by ``to_dict``."""
        items = [TestResult.from_dict(r) for r in (data.get("results") or [])]
        meta = dict(data.get("metadata") or {})
        return cls(results=items, metadata=meta)

    @classmethod
    def load(cls, source: str | os.PathLike[str]) -> HarnessResults:
        """
        Load serialized ``HarnessResults`` from a JSON file path or JSON string.

        Args:
            source: Path to a saved JSON file, or a raw JSON string.

        Returns:
            HarnessResults: Rehydrated results ready for ``compare()``.
        """
        text_or_path = os.fspath(source)
        if os.path.isfile(text_or_path):
            with open(text_or_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        else:
            data = json.loads(text_or_path)
        return cls.from_dict(data)

    def compare(
        self,
        baseline: HarnessResults | dict[str, Any] | str | os.PathLike[str],
        min_delta: float | None = None,
    ) -> dict[str, Any]:
        """
        Compare these candidate results against a ``baseline`` with noise awareness.

        Single-trial evaluations on small suites exhibit substantial binomial
        and discretization noise (for example, 1 case in a 15-case suite is
        ``0.067``, and run-to-run spread on stochastic models routinely reaches
        ``0.13-0.20``). ``compare()`` estimates a conservative ``noise_floor``
        from suite size, trial counts, and empirical pass rates so hill-climbing
        loops only accept genuine signal (``exceeds_noise == True``).

        Args:
            baseline: Baseline ``HarnessResults``, ``to_dict()`` dict, or JSON path.
            min_delta: Optional explicit minimum delta threshold overriding the
                automatic statistical ``noise_floor``.

        Returns:
            dict: Comparison summary with ``delta``, ``candidate_pass_rate``,
            ``baseline_pass_rate``, ``noise_floor``, ``exceeds_noise``,
            ``direction`` (``'improved'``, ``'regressed'``, or ``'tie'``),
            ``improvements``, ``regressions``, and ``cost_delta``.
        """
        if isinstance(baseline, HarnessResults):
            base = baseline
        elif isinstance(baseline, dict):
            base = HarnessResults.from_dict(baseline)
        else:
            base = HarnessResults.load(baseline)

        cand_rate = self.pass_rate
        base_rate = base.pass_rate
        delta = round(cand_rate - base_rate, 6)

        cand_by_name = {r.test_case.name: r for r in self.results}
        base_by_name = {r.test_case.name: r for r in base.results}
        shared_names = [name for name in cand_by_name if name in base_by_name]

        improvements: list[str] = []
        regressions: list[str] = []
        for name in shared_names:
            c_r = cand_by_name[name].pass_rate or 0.0
            b_r = base_by_name[name].pass_rate or 0.0
            if c_r > b_r + 1e-9:
                improvements.append(name)
            elif c_r < b_r - 1e-9:
                regressions.append(name)

        n_cases = max(1, len(shared_names) or max(self.total_count, base.total_count))
        cand_trials = max(
            1,
            int(
                self.metadata.get("trials")
                or (min((r.trials for r in self.results), default=1))
            ),
        )
        base_trials = max(
            1,
            int(
                base.metadata.get("trials")
                or (min((r.trials for r in base.results), default=1))
            ),
        )

        if min_delta is not None:
            noise_floor = float(min_delta)
        else:
            # Binomial standard error across (N * trials) plus single-unit quantization floor
            var_cand = (cand_rate * max(0.0, 1.0 - cand_rate)) / (n_cases * cand_trials)
            var_base = (base_rate * max(0.0, 1.0 - base_rate)) / (n_cases * base_trials)
            se_diff = math.sqrt(var_cand + var_base)
            unit_step = 1.0 / (n_cases * min(cand_trials, base_trials))
            noise_floor = round(max(unit_step, 1.645 * se_diff), 6)

        exceeds_noise = abs(delta) > noise_floor + 1e-9
        if abs(delta) <= 1e-9:
            direction = "tie"
        elif delta > 0:
            direction = "improved"
        else:
            direction = "regressed"

        cost_delta = round(self.total_cost - base.total_cost, 10)
        tokens_delta = int(self.usage["total_tokens"]) - int(base.usage["total_tokens"])

        return {
            "delta": delta,
            "candidate_pass_rate": round(cand_rate, 6),
            "baseline_pass_rate": round(base_rate, 6),
            "noise_floor": noise_floor,
            "exceeds_noise": exceeds_noise,
            "direction": direction,
            "shared_cases": len(shared_names),
            "improvements": improvements,
            "regressions": regressions,
            "cost_delta": cost_delta,
            "tokens_delta": tokens_delta,
        }


class Harness:
    """Runs a flow against a collection of test cases.

    A flow is any ``memory -> memory`` callable — a THOUGHT, an AGENT, a
    WORKFLOW, or a plain function. Each trial runs in a fresh, isolated
    MEMORY; exceptions are contained as failures rather than raised.

    Example:
        >>> harness = Harness([
        ...     TestCase(
        ...         name="greeting",
        ...         setup=lambda m: m.add_msg("user", "Hello!"),
        ...         check=lambda m: "hello" in (m.last_asst_msg(content_only=True) or "").lower(),
        ...     ),
        ... ])
        >>> results = harness.run(my_flow, trials=3)
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

    @staticmethod
    def load(source: str | os.PathLike[str]) -> HarnessResults:
        """Load saved ``HarnessResults`` from a JSON file path or JSON string."""
        return HarnessResults.load(source)

    def _run_single_trial(
        self,
        case: TestCase,
        flow: Callable[[MEMORY], MEMORY],
        strict: bool,
    ) -> dict[str, Any]:
        """Execute one isolated trial of ``case`` against ``flow``."""
        start = time.time()
        memory: MEMORY | None = None
        try:
            memory = case.prepare()
            returned = flow(memory)
            if returned is not None:
                memory = returned
            passed, reason, observed = case.evaluate_with_detail(memory)
            absorbed = _collect_absorbed_errors(memory)
            if strict and absorbed and passed:
                passed = False
                first = absorbed[0]
                reason = "strict mode: absorbed error in '{}' ({}: {})".format(
                    first.get("source"),
                    first.get("error_class"),
                    first.get("reason"),
                )
            return {
                "passed": passed,
                "response": memory.last_asst_msg(content_only=True) if memory is not None else None,
                "error": None,
                "reason": reason,
                "observed": observed,
                "absorbed_errors": absorbed,
                "duration_ms": int((time.time() - start) * 1000),
                "memory": memory,
                "usage": _collect_memory_usage(memory),
            }
        except Exception as e:
            err_str = "{}: {}".format(type(e).__name__, e)
            absorbed = _collect_absorbed_errors(memory)
            resp = None
            if memory is not None and hasattr(memory, "last_asst_msg"):
                resp = memory.last_asst_msg(content_only=True)
            return {
                "passed": False,
                "response": resp,
                "error": err_str,
                "reason": err_str,
                "observed": None,
                "absorbed_errors": absorbed,
                "duration_ms": int((time.time() - start) * 1000),
                "memory": memory,
                "usage": _collect_memory_usage(memory),
            }

    def run(
        self,
        flow: Callable[[MEMORY], MEMORY],
        filter_tags: list[str] | None = None,
        strict: bool = False,
        trials: int = 1,
        pass_threshold: float = 1.0,
    ) -> HarnessResults:
        """Run all (or tag-filtered) test cases against a flow.

        Args:
            flow: Any ``memory -> memory`` callable.
            filter_tags: Optional tags to filter which cases run.
            strict: When True, any trial whose resulting MEMORY contains
                absorbed primitive failures (e.g. a failed THOUGHT or
                ReplayMissError) is marked failed even if ``check`` passed.
            trials: Number of independent trials per case (default 1).
            pass_threshold: Minimum per-case ``pass_rate`` in ``(0.0, 1.0]``
                required for ``TestResult.passed`` to be True (default 1.0).

        Returns:
            HarnessResults with one TestResult per case.

        Raises:
            ValueError: When ``trials < 1`` or ``pass_threshold`` is outside ``(0.0, 1.0]``.
        """
        if isinstance(trials, bool) or not isinstance(trials, int) or trials < 1:
            raise ValueError("'trials' must be a positive integer, got {!r}.".format(trials))
        if not (0.0 < float(pass_threshold) <= 1.0):
            raise ValueError(
                "'pass_threshold' must be in (0.0, 1.0], got {!r}.".format(pass_threshold)
            )

        cases = self.filter_by_tags(filter_tags) if filter_tags else self.test_cases
        results = HarnessResults(
            metadata={
                "trials": trials,
                "strict": strict,
                "pass_threshold": float(pass_threshold),
            }
        )

        for case in cases:
            trial_runs = [
                self._run_single_trial(case, flow, strict=strict)
                for _ in range(trials)
            ]
            passes = sum(1 for tr in trial_runs if tr["passed"])
            rate = passes / trials
            case_passed = rate + 1e-12 >= float(pass_threshold)

            # Surface the first failing trial's diagnostics when not all trials passed,
            # otherwise retain the final passing trial's artifacts.
            representative = next(
                (tr for tr in trial_runs if not tr["passed"]),
                trial_runs[-1],
            )
            all_absorbed: list[dict[str, Any]] = []
            for tr in trial_runs:
                all_absorbed.extend(tr["absorbed_errors"])

            reason = representative["reason"]
            if not case_passed and reason is None and passes < trials:
                reason = "passed {}/{} trials (threshold {:.2f})".format(
                    passes, trials, float(pass_threshold)
                )
            elif case_passed:
                reason = None

            results.results.append(
                TestResult(
                    test_case=case,
                    passed=case_passed,
                    response=representative["response"],
                    error=representative["error"] if not case_passed else None,
                    reason=reason,
                    observed=representative["observed"],
                    absorbed_errors=all_absorbed,
                    duration_ms=sum(tr["duration_ms"] for tr in trial_runs),
                    memory=representative["memory"],
                    trials=trials,
                    passes=passes,
                    pass_rate=rate,
                    usage=_merge_usage_ledgers([tr["usage"] for tr in trial_runs]),
                )
            )

        return results
