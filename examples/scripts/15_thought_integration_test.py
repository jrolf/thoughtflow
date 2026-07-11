"""
Example: exercise a THOUGHT through the full parse-validate-retry path.

Why this script exists
----------------------
Foundation Agent production feedback (WP-06) surfaced a common mistake:
authors unit-test ``validation=`` lambdas in isolation, but schema validation
runs inside ``parse_response`` **before** the callable validator. A lambda that
passes alone may never run when ``parsing_rules`` reject the payload first.

This script demonstrates the correct integration test pattern: canned LLM
responses through ``THOUGHT(...)``, asserting on ``{name}_result`` and optionally
``{name}_last_error`` when testing failure paths.

What it demonstrates
--------------------
- ``oneOf`` schema dialect for branch-shaped classification (found vs absent)
- Full pipeline order: LLM -> valid_extract (in parse_response) -> MEMORY update
- No network: MockLLM returns deterministic text

Run from the thoughtflow repo root:

    PYTHONPATH=src python examples/scripts/15_thought_integration_test.py

Or after ``pip install -e .``:

    python examples/scripts/15_thought_integration_test.py

See also: docs/concepts/thought.md, primitives/THOUGHT.md
"""

from thoughtflow import MEMORY, THOUGHT


class MockLLM:
    """
    Minimal LLM stub returning canned responses in order.

    Implements ``call(msgs, params)`` like the standard LLM interface.
    """

    def __init__(self, responses):
        self.responses = list(responses)

    def call(self, msgs, params=None):
        return self.responses[0]


def test_absent_branch_via_oneof():
    """
    Integration test: absent verdict parses through oneOf and lands on MEMORY.

    This is the pattern production harnesses should copy — not valid_extract()
    called directly on the raw string.
    """
    memory = MEMORY()
    memory.add_msg("user", "Locate the clause.", channel="api")

    thought = THOUGHT(
        name="locator",
        llm=MockLLM(["{'verdict': 'absent', 'note': 'not in doc'}"]),
        prompt="Find the clause in the document.",
        parsing_rules={
            "kind": "python",
            "format": {
                "oneOf": [
                    {"verdict": "found", "matched_span": ""},
                    {"verdict": "absent", "note": ""},
                ]
            },
        },
        max_retries=1,
    )

    memory = thought(memory)
    result = memory.get_var("locator_result")
    assert result["verdict"] == "absent"
    return result


def main():
    result = test_absent_branch_via_oneof()
    print("result:", result)
    print("OK — full THOUGHT path validated absent branch via oneOf")


if __name__ == "__main__":
    main()
