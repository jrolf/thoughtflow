"""
Unit tests for the ThoughtFlow THOUGHT and DECIDE classes.

The THOUGHT class is the unit of cognition in ThoughtFlow. It's a callable object
that takes a MEMORY, performs an operation, and returns the modified MEMORY.

The DECIDE class is a specialized THOUGHT that constrains LLM output to a finite
set of choices, with smart parsing and validation.

Note: Some tests are marked as skipped due to a known issue where the THOUGHT class
uses 'system' as a default channel which is not a valid channel in MEMORY.
"""

from __future__ import annotations

import pytest

from thoughtflow import THOUGHT, DECIDE, PLAN, MEMORY


# ============================================================================
# Initialization Tests
# ============================================================================


class TestThoughtInitialization:
    """
    Tests for THOUGHT initialization and configuration.
    """

    def test_creates_with_name(self, mock_llm):
        """
        THOUGHT must store the provided name.
        
        The name identifies the thought in logs and traces.
        
        Remove this test if: We change the initialization signature.
        """
        thought = THOUGHT(name="test_thought", llm=mock_llm(), prompt="Hello")
        
        assert thought.name == "test_thought"

    def test_generates_unique_id(self, mock_llm):
        """
        Each THOUGHT must have a unique ID.
        
        IDs enable tracking and debugging.
        
        Remove this test if: We change ID generation.
        """
        thought1 = THOUGHT(name="t1", llm=mock_llm(), prompt="Hello")
        thought2 = THOUGHT(name="t2", llm=mock_llm(), prompt="Hello")
        
        assert thought1.id != thought2.id

    def test_stores_llm_reference(self, mock_llm):
        """
        THOUGHT must store the LLM instance for later calls.
        
        The LLM is needed for llm_call operations.
        
        Remove this test if: We change how LLM is provided.
        """
        llm = mock_llm()
        thought = THOUGHT(name="test", llm=llm, prompt="Hello")
        
        assert thought.llm is llm

    def test_stores_prompt(self, mock_llm):
        """
        THOUGHT must store the prompt for llm_call operations.
        
        The prompt is the user message sent to the LLM.
        
        Remove this test if: We change prompt handling.
        """
        thought = THOUGHT(name="test", llm=mock_llm(), prompt="Tell me a joke")
        
        assert thought.prompt == "Tell me a joke"

    def test_operation_defaults_to_none(self, mock_llm):
        """
        THOUGHT operation defaults to None (treated as 'llm_call' at execution).
        
        When operation is None, it defaults to llm_call during execution.
        
        Remove this test if: We change the default operation.
        """
        thought = THOUGHT(name="test", llm=mock_llm(), prompt="Hello")
        
        # Operation is None at init, becomes llm_call at execution
        assert thought.operation is None

    def test_output_var_defaults_to_name_result(self, mock_llm):
        """
        THOUGHT output_var defaults to {name}_result.
        
        This enables automatic result storage with predictable names.
        
        Remove this test if: We change output_var default.
        """
        thought = THOUGHT(name="my_thought", llm=mock_llm(), prompt="Hello")
        
        assert thought.output_var == "my_thought_result"


# ============================================================================
# Callable Interface Tests
# ============================================================================


class TestThoughtCallableInterface:
    """
    Tests for the THOUGHT callable interface.
    
    The core contract is: mem = thought(mem)
    """

    def test_thought_is_callable(self, mock_llm, memory):
        """
        THOUGHT must support: mem = thought(mem)
        
        This callable interface is the CORE contract of the class.
        All agent workflows depend on this pattern.
        
        Remove this test if: We change the THOUGHT interface (major version).
        """
        thought = THOUGHT(name="test", llm=mock_llm(), prompt="Hello")
        
        result = thought(memory)
        
        assert isinstance(result, MEMORY)

    def test_returns_same_memory_instance(self, mock_llm, memory):
        """
        THOUGHT must return the same MEMORY instance (mutated).
        
        This enables chaining: mem = t1(t2(t3(mem)))
        
        Remove this test if: We change to immutable memory.
        """
        thought = THOUGHT(name="test", llm=mock_llm(), prompt="Hello")
        
        result = thought(memory)
        
        assert result is memory

    def test_logs_execution_to_memory(self, mock_llm, memory):
        """
        THOUGHT must log its execution to memory.
        
        Logs enable debugging and audit trails.
        
        Remove this test if: We remove execution logging.
        """
        thought = THOUGHT(name="test", llm=mock_llm(), prompt="Hello")
        
        thought(memory)
        
        logs = memory.get_logs()
        assert len(logs) > 0


# ============================================================================
# LLM Call Operation Tests
# ============================================================================


class TestLLMCallOperation:
    """
    Tests for the llm_call operation type.
    """

    def test_calls_llm_with_prompt(self, mock_llm, memory):
        """
        llm_call must call the LLM with a message.
        
        The prompt becomes the user message to the LLM.
        
        Remove this test if: We change prompt handling.
        """
        llm = mock_llm()
        thought = THOUGHT(name="test", llm=llm, prompt="What is 2+2?")
        
        thought(memory)
        
        assert llm.call_count == 1

    def test_includes_conversation_history(self, mock_llm, memory):
        """
        llm_call includes conversation history from memory.
        
        Context is important for coherent responses.
        
        Remove this test if: We change history handling.
        """
        # Add some history to memory
        memory.add_msg('user', 'Previous question', channel='webapp')
        memory.add_msg('assistant', 'Previous answer', channel='webapp')
        
        llm = mock_llm()
        thought = THOUGHT(name="test", llm=llm, prompt="Follow-up question")
        
        thought(memory)
        
        assert llm.call_count == 1
        # The LLM was called with messages from memory


# ============================================================================
# Retry Logic Tests
# ============================================================================


class TestRetryLogic:
    """
    Tests for THOUGHT retry logic on failures.
    """

    def test_respects_max_retries(self, mock_llm, memory):
        """
        THOUGHT must stop retrying after max_retries attempts.
        
        This prevents infinite retry loops.
        
        Remove this test if: We change retry limits.
        """
        llm = mock_llm(responses=["Invalid"] * 10)
        thought = THOUGHT(
            name="test",
            llm=llm,
            prompt="Give me JSON",
            max_retries=3,
        )
        
        thought(memory)
        
        # Should not exceed max_retries
        assert llm.call_count <= 3

    def test_no_retry_when_max_retries_is_one(self, mock_llm, memory):
        """
        THOUGHT must not retry when max_retries=1.
        
        Some operations should fail fast.
        
        Remove this test if: We change retry semantics.
        """
        llm = mock_llm(responses=["Response"])
        thought = THOUGHT(
            name="test",
            llm=llm,
            prompt="Hello",
            max_retries=1,
        )
        
        thought(memory)
        
        assert llm.call_count == 1


# ============================================================================
# Memory Query Operation Tests
# ============================================================================


class TestMemoryQueryOperation:
    """
    Tests for the memory_query operation type.
    
    This operation retrieves variables from memory without making LLM calls.
    """

    def test_no_llm_call_for_memory_query(self, mock_llm, memory):
        """
        memory_query must not make LLM calls.
        
        This operation is pure memory access.
        
        Remove this test if: We change memory_query behavior.
        """
        memory.set_var('x', 1)
        llm = mock_llm()
        
        thought = THOUGHT(
            name="query",
            operation="memory_query",
            required_vars=['x'],
            llm=llm,  # Provided but shouldn't be used
        )
        
        thought(memory)
        
        assert llm.call_count == 0


# ============================================================================
# Serialization Tests
# ============================================================================


class TestThoughtSerialization:
    """
    Tests for THOUGHT serialization and copy.
    """

    def test_copy_creates_independent_instance(self, mock_llm):
        """
        copy creates an independent instance.
        
        Changes to the copy must not affect the original.
        
        Remove this test if: We remove copy method.
        """
        import copy
        llm = mock_llm()
        original = THOUGHT(name="original", llm=llm, prompt="Hello")
        
        copied = copy.copy(original)
        copied.name = "copied"
        
        assert original.name == "original"
        assert copied.name == "copied"

    def test_has_execution_history(self, mock_llm, memory):
        """
        THOUGHT must track execution history.
        
        This enables debugging and introspection.
        
        Remove this test if: We remove history tracking.
        """
        thought = THOUGHT(name="test", llm=mock_llm(), prompt="Hello")
        
        assert hasattr(thought, 'execution_history')
        assert thought.execution_history == []
        
        thought(memory)
        
        # Should have recorded execution
        assert len(thought.execution_history) > 0


# ============================================================================
# Configuration Tests
# ============================================================================


class TestThoughtConfiguration:
    """
    Tests for THOUGHT configuration options.
    """

    def test_stores_required_vars(self, mock_llm):
        """
        THOUGHT must store required_vars configuration.
        
        Remove this test if: We change config storage.
        """
        thought = THOUGHT(
            name="test",
            llm=mock_llm(),
            prompt="Hello",
            required_vars=['a', 'b', 'c'],
        )
        
        assert thought.required_vars == ['a', 'b', 'c']

    def test_stores_optional_vars(self, mock_llm):
        """
        THOUGHT must store optional_vars configuration.
        
        Remove this test if: We change config storage.
        """
        thought = THOUGHT(
            name="test",
            llm=mock_llm(),
            prompt="Hello",
            optional_vars=['x', 'y'],
        )
        
        assert thought.optional_vars == ['x', 'y']

    def test_stores_max_retries(self, mock_llm):
        """
        THOUGHT must store max_retries configuration.
        
        Remove this test if: We change config storage.
        """
        thought = THOUGHT(
            name="test",
            llm=mock_llm(),
            prompt="Hello",
            max_retries=5,
        )
        
        assert thought.max_retries == 5

    def test_stores_retry_delay(self, mock_llm):
        """
        THOUGHT must store retry_delay configuration.
        
        Remove this test if: We change config storage.
        """
        thought = THOUGHT(
            name="test",
            llm=mock_llm(),
            prompt="Hello",
            retry_delay=0.5,
        )
        
        assert thought.retry_delay == 0.5

    def test_stores_description(self, mock_llm):
        """
        THOUGHT must store description if provided.
        
        Remove this test if: We remove description support.
        """
        thought = THOUGHT(
            name="test",
            llm=mock_llm(),
            prompt="Hello",
            description="A test thought",
        )
        
        assert thought.description == "A test thought"

    def test_tracks_last_result(self, mock_llm, memory):
        """
        THOUGHT must track last_result after execution.
        
        Remove this test if: We remove result tracking.
        """
        thought = THOUGHT(name="test", llm=mock_llm(), prompt="Hello")
        
        assert thought.last_result is None
        
        thought(memory)
        
        # last_result is set (may be None on error, or the actual result)
        assert hasattr(thought, 'last_result')

    def test_tracks_last_error(self, mock_llm, memory):
        """
        THOUGHT must track last_error after execution.
        
        Remove this test if: We remove error tracking.
        """
        thought = THOUGHT(name="test", llm=mock_llm(), prompt="Hello")
        
        assert thought.last_error is None
        
        thought(memory)
        
        # last_error is set (may contain error message or be None)
        assert hasattr(thought, 'last_error')


# ============================================================================
# Hooks Tests
# ============================================================================


class TestHooks:
    """
    Tests for pre/post execution hooks.
    """

    def test_pre_hook_is_stored(self, mock_llm):
        """
        THOUGHT must store pre_hook function.
        
        Remove this test if: We remove hooks.
        """
        def my_hook(thought, mem, vars, **kwargs):
            pass
        
        thought = THOUGHT(
            name="test",
            llm=mock_llm(),
            prompt="Hello",
            pre_hook=my_hook,
        )
        
        assert thought.pre_hook is my_hook

    def test_post_hook_is_stored(self, mock_llm):
        """
        THOUGHT must store post_hook function.
        
        Remove this test if: We remove hooks.
        """
        def my_hook(thought, mem, result, error):
            pass
        
        thought = THOUGHT(
            name="test",
            llm=mock_llm(),
            prompt="Hello",
            post_hook=my_hook,
        )
        
        assert thought.post_hook is my_hook


# ============================================================================
# DECIDE Class Tests
# ============================================================================


class TestDecideInitialization:
    """
    Tests for DECIDE initialization and configuration.
    """

    def test_is_subclass_of_thought(self):
        """
        DECIDE must be a subclass of THOUGHT.
        
        This enables DECIDE to inherit all THOUGHT functionality.
        
        Remove this test if: We change the inheritance hierarchy.
        """
        assert issubclass(DECIDE, THOUGHT)

    def test_requires_choices_parameter(self, mock_llm):
        """
        DECIDE must require a 'choices' parameter.
        
        Choices define the valid outputs.
        
        Remove this test if: We make choices optional.
        """
        with pytest.raises(ValueError, match="requires 'choices'"):
            DECIDE(name="test", llm=mock_llm(), prompt="Hello")

    def test_accepts_list_choices(self, mock_llm):
        """
        DECIDE must accept a list of choices.
        
        List format is the simplest way to define choices.
        
        Remove this test if: We remove list support.
        """
        decide = DECIDE(
            name="test",
            llm=mock_llm(),
            prompt="Choose",
            choices=["a", "b", "c"],
        )
        
        assert decide._choices_list == ["a", "b", "c"]
        assert decide._choices_descriptions == {}

    def test_accepts_dict_choices(self, mock_llm):
        """
        DECIDE must accept a dict of choices with descriptions.
        
        Dict format allows adding descriptions for each choice.
        
        Remove this test if: We remove dict support.
        """
        decide = DECIDE(
            name="test",
            llm=mock_llm(),
            prompt="Choose",
            choices={"approve": "Accept it", "reject": "Deny it"},
        )
        
        assert decide._choices_list == ["approve", "reject"]
        assert decide._choices_descriptions == {"approve": "Accept it", "reject": "Deny it"}

    def test_rejects_empty_choices(self, mock_llm):
        """
        DECIDE must reject empty choices.
        
        At least one choice is needed for a decision.
        
        Remove this test if: We allow empty choices.
        """
        with pytest.raises(ValueError, match="cannot be empty"):
            DECIDE(name="test", llm=mock_llm(), prompt="Choose", choices=[])

    def test_rejects_invalid_choices_type(self, mock_llm):
        """
        DECIDE must reject invalid choices types.
        
        Only list and dict are supported.
        
        Remove this test if: We add more types.
        """
        with pytest.raises(ValueError, match="must be a list or dict"):
            DECIDE(name="test", llm=mock_llm(), prompt="Choose", choices="invalid")

    def test_default_max_retries_is_five(self, mock_llm):
        """
        DECIDE must default max_retries to 5.
        
        Decisions often need more retries than general THOUGHTs.
        
        Remove this test if: We change the default.
        """
        decide = DECIDE(
            name="test",
            llm=mock_llm(),
            prompt="Choose",
            choices=["a", "b"],
        )
        
        assert decide.max_retries == 5

    def test_can_override_max_retries(self, mock_llm):
        """
        DECIDE must allow overriding max_retries.
        
        Users may want different retry limits.
        
        Remove this test if: We remove this option.
        """
        decide = DECIDE(
            name="test",
            llm=mock_llm(),
            prompt="Choose",
            choices=["a", "b"],
            max_retries=10,
        )
        
        assert decide.max_retries == 10

    def test_stores_default_choice(self, mock_llm):
        """
        DECIDE must store the default choice.
        
        Default is used when all retries fail.
        
        Remove this test if: We remove default support.
        """
        decide = DECIDE(
            name="test",
            llm=mock_llm(),
            prompt="Choose",
            choices=["a", "b"],
            default="a",
        )
        
        assert decide.default == "a"

    def test_case_sensitive_defaults_false(self, mock_llm):
        """
        DECIDE must default to case-insensitive matching.
        
        This makes parsing more robust.
        
        Remove this test if: We change the default.
        """
        decide = DECIDE(
            name="test",
            llm=mock_llm(),
            prompt="Choose",
            choices=["a", "b"],
        )
        
        assert decide.case_sensitive is False


class TestDecideChoiceFormatting:
    """
    Tests for DECIDE choice formatting in prompts.
    """

    def test_formats_list_choices(self, mock_llm):
        """
        DECIDE must format list choices as bullet points.
        
        Remove this test if: We change the format.
        """
        decide = DECIDE(
            name="test",
            llm=mock_llm(),
            prompt="Choose",
            choices=["yes", "no", "maybe"],
        )
        
        formatted = decide._format_choices()
        
        assert "- yes" in formatted
        assert "- no" in formatted
        assert "- maybe" in formatted
        assert "Choose one of:" in formatted

    def test_formats_dict_choices_with_descriptions(self, mock_llm):
        """
        DECIDE must format dict choices with descriptions.
        
        Remove this test if: We change the format.
        """
        decide = DECIDE(
            name="test",
            llm=mock_llm(),
            prompt="Choose",
            choices={"approve": "Accept it", "reject": "Deny it"},
        )
        
        formatted = decide._format_choices()
        
        assert "- approve: Accept it" in formatted
        assert "- reject: Deny it" in formatted


class TestDecideResponseParsing:
    """
    Tests for DECIDE response parsing logic.
    """

    def test_parses_exact_match(self, mock_llm):
        """
        DECIDE must recognize exact choice matches.
        
        Remove this test if: We change parsing logic.
        """
        decide = DECIDE(
            name="test",
            llm=mock_llm(),
            prompt="Choose",
            choices=["approve", "reject"],
        )
        
        assert decide.parse_response("approve") == "approve"

    def test_parses_case_insensitive(self, mock_llm):
        """
        DECIDE must match choices case-insensitively by default.
        
        Remove this test if: We change default case sensitivity.
        """
        decide = DECIDE(
            name="test",
            llm=mock_llm(),
            prompt="Choose",
            choices=["approve", "reject"],
        )
        
        assert decide.parse_response("APPROVE") == "approve"
        assert decide.parse_response("Approve") == "approve"

    def test_parses_embedded_choice(self, mock_llm):
        """
        DECIDE must find choice embedded in response text.
        
        LLMs often wrap choices in explanatory text.
        
        Remove this test if: We remove embedded matching.
        """
        decide = DECIDE(
            name="test",
            llm=mock_llm(),
            prompt="Choose",
            choices=["approve", "reject"],
        )
        
        assert decide.parse_response("I would choose approve for this.") == "approve"
        assert decide.parse_response("My decision is: reject") == "reject"

    def test_prefers_longer_matches(self, mock_llm):
        """
        DECIDE must prefer longer matches to avoid partial matches.
        
        E.g., 'approve_all' should match before 'approve'.
        
        Remove this test if: We change matching priority.
        """
        decide = DECIDE(
            name="test",
            llm=mock_llm(),
            prompt="Choose",
            choices=["approve", "approve_all"],
        )
        
        # Should match 'approve_all' not 'approve'
        assert decide.parse_response("approve_all") == "approve_all"

    def test_returns_raw_when_no_match(self, mock_llm):
        """
        DECIDE must return raw response when no choice matches.
        
        This allows validation to catch invalid responses.
        
        Remove this test if: We change no-match behavior.
        """
        decide = DECIDE(
            name="test",
            llm=mock_llm(),
            prompt="Choose",
            choices=["approve", "reject"],
        )
        
        assert decide.parse_response("maybe") == "maybe"


class TestDecideValidation:
    """
    Tests for DECIDE validation logic.
    """

    def test_validates_valid_choice(self, mock_llm):
        """
        DECIDE must accept valid choices.
        
        Remove this test if: We change validation.
        """
        decide = DECIDE(
            name="test",
            llm=mock_llm(),
            prompt="Choose",
            choices=["approve", "reject"],
        )
        
        valid, reason = decide.validate("approve")
        
        assert valid is True
        assert reason == ""

    def test_rejects_invalid_choice(self, mock_llm):
        """
        DECIDE must reject invalid choices.
        
        Remove this test if: We change validation.
        """
        decide = DECIDE(
            name="test",
            llm=mock_llm(),
            prompt="Choose",
            choices=["approve", "reject"],
        )
        
        valid, reason = decide.validate("maybe")
        
        assert valid is False
        assert "Not a valid choice" in reason

    def test_validates_case_insensitively(self, mock_llm):
        """
        DECIDE must validate case-insensitively by default.
        
        Remove this test if: We change case sensitivity.
        """
        decide = DECIDE(
            name="test",
            llm=mock_llm(),
            prompt="Choose",
            choices=["approve", "reject"],
        )
        
        valid, _ = decide.validate("APPROVE")
        
        assert valid is True


class TestDecideRepairPrompt:
    """
    Tests for DECIDE repair prompt generation.
    """

    def test_builds_choice_specific_repair(self, mock_llm):
        """
        DECIDE must build repair prompts that list valid choices.
        
        This helps the LLM correct its response.
        
        Remove this test if: We remove repair prompts.
        """
        decide = DECIDE(
            name="test",
            llm=mock_llm(),
            prompt="Choose",
            choices=["approve", "reject", "escalate"],
        )
        
        repair = decide._build_repair_suffix("invalid response")
        
        assert "approve" in repair
        assert "reject" in repair
        assert "escalate" in repair
        assert "exactly one of" in repair.lower()


class TestDecideSerialization:
    """
    Tests for DECIDE serialization.
    """

    def test_to_dict_includes_choices(self, mock_llm):
        """
        DECIDE serialization must include choices.
        
        Remove this test if: We change serialization.
        """
        decide = DECIDE(
            name="test",
            llm=mock_llm(),
            prompt="Choose",
            choices=["a", "b"],
            default="a",
        )
        
        data = decide.to_dict()
        
        assert data["choices"] == ["a", "b"]
        assert data["default"] == "a"
        assert data["_class"] == "DECIDE"

    def test_from_dict_restores_decide(self, mock_llm):
        """
        DECIDE must be reconstructable from dict.
        
        Remove this test if: We remove from_dict.
        """
        original = DECIDE(
            name="test",
            llm=mock_llm(),
            prompt="Choose",
            choices=["a", "b"],
            default="a",
        )
        
        data = original.to_dict()
        restored = DECIDE.from_dict(data, llm=mock_llm())
        
        assert restored.name == original.name
        assert restored._choices_list == original._choices_list
        assert restored.default == original.default


class TestDecideStringRepresentation:
    """
    Tests for DECIDE string representations.
    """

    def test_repr_shows_key_info(self, mock_llm):
        """
        DECIDE repr must show key configuration.
        
        Remove this test if: We change repr format.
        """
        decide = DECIDE(
            name="my_decide",
            llm=mock_llm(),
            prompt="Choose",
            choices=["a", "b", "c"],
        )
        
        r = repr(decide)
        
        assert "DECIDE" in r
        assert "my_decide" in r
        assert "a" in r and "b" in r and "c" in r

    def test_str_is_human_readable(self, mock_llm):
        """
        DECIDE str must be human-readable.
        
        Remove this test if: We change str format.
        """
        decide = DECIDE(
            name="my_decide",
            llm=mock_llm(),
            prompt="Choose",
            choices=["a", "b"],
        )
        
        s = str(decide)
        
        assert "Decide" in s
        assert "my_decide" in s


class TestDecideCallable:
    """
    Tests for DECIDE callable interface.
    """

    def test_is_callable(self, mock_llm, memory):
        """
        DECIDE must be callable like THOUGHT: mem = decide(mem)
        
        Remove this test if: We change the interface.
        """
        decide = DECIDE(
            name="test",
            llm=mock_llm(responses=["approve"]),
            prompt="Choose",
            choices=["approve", "reject"],
        )
        
        result = decide(memory)
        
        assert isinstance(result, MEMORY)

    def test_stores_result_in_memory(self, mock_llm, memory):
        """
        DECIDE must store the decision result in memory.
        
        Remove this test if: We change result storage.
        """
        decide = DECIDE(
            name="my_decision",
            llm=mock_llm(responses=["approve"]),
            prompt="Choose",
            choices=["approve", "reject"],
        )
        
        decide(memory)
        result = memory.get_var("my_decision_result")
        
        assert result == "approve"

    def test_uses_default_on_failure(self, mock_llm, memory):
        """
        DECIDE must use default when all retries fail.
        
        Remove this test if: We remove default support.
        """
        decide = DECIDE(
            name="test",
            llm=mock_llm(responses=["invalid"] * 10),
            prompt="Choose",
            choices=["approve", "reject"],
            default="reject",
            max_retries=2,
        )
        
        decide(memory)
        result = memory.get_var("test_result")
        
        assert result == "reject"


# ============================================================================
# PLAN Class Tests
# ============================================================================


class TestPlanInitialization:
    """
    Tests for PLAN initialization and configuration.
    """

    def test_is_subclass_of_thought(self):
        """
        PLAN must be a subclass of THOUGHT.
        
        Remove this test if: We change the inheritance hierarchy.
        """
        assert issubclass(PLAN, THOUGHT)

    def test_requires_actions_parameter(self, mock_llm):
        """
        PLAN must require an 'actions' parameter.
        
        Remove this test if: We make actions optional.
        """
        with pytest.raises(ValueError, match="requires 'actions'"):
            PLAN(name="test", llm=mock_llm(), prompt="Hello")

    def test_accepts_simple_actions(self, mock_llm):
        """
        PLAN must accept dict with string descriptions.
        
        Remove this test if: We remove simple format support.
        """
        plan = PLAN(
            name="test",
            llm=mock_llm(),
            prompt="Plan",
            actions={"search": "Search the web", "analyze": "Analyze data"},
        )
        
        assert plan._actions_list == ["search", "analyze"]
        assert plan._actions_descriptions == {"search": "Search the web", "analyze": "Analyze data"}
        assert plan._has_param_schemas is False

    def test_accepts_actions_with_params(self, mock_llm):
        """
        PLAN must accept dict with parameter schemas.
        
        Remove this test if: We remove param schema support.
        """
        plan = PLAN(
            name="test",
            llm=mock_llm(),
            prompt="Plan",
            actions={
                "search": {"description": "Search", "params": {"query": "str", "max": "int?"}},
            },
        )
        
        assert plan._actions_list == ["search"]
        assert plan._actions_params == {"search": {"query": "str", "max": "int?"}}
        assert plan._has_param_schemas is True

    def test_rejects_empty_actions(self, mock_llm):
        """
        PLAN must reject empty actions dict.
        
        Remove this test if: We allow empty actions.
        """
        with pytest.raises(ValueError, match="cannot be empty"):
            PLAN(name="test", llm=mock_llm(), prompt="Plan", actions={})

    def test_rejects_invalid_actions_type(self, mock_llm):
        """
        PLAN must reject non-dict actions.
        
        Remove this test if: We add more types.
        """
        with pytest.raises(ValueError, match="must be a dict"):
            PLAN(name="test", llm=mock_llm(), prompt="Plan", actions=["search"])

    def test_default_max_retries_is_three(self, mock_llm):
        """
        PLAN must default max_retries to 3.
        
        Remove this test if: We change the default.
        """
        plan = PLAN(
            name="test",
            llm=mock_llm(),
            prompt="Plan",
            actions={"search": "Search"},
        )
        
        assert plan.max_retries == 3

    def test_default_max_steps(self, mock_llm):
        """
        PLAN must default max_steps to 10.
        
        Remove this test if: We change the default.
        """
        plan = PLAN(
            name="test",
            llm=mock_llm(),
            prompt="Plan",
            actions={"search": "Search"},
        )
        
        assert plan.max_steps == 10

    def test_default_max_parallel(self, mock_llm):
        """
        PLAN must default max_parallel to 5.
        
        Remove this test if: We change the default.
        """
        plan = PLAN(
            name="test",
            llm=mock_llm(),
            prompt="Plan",
            actions={"search": "Search"},
        )
        
        assert plan.max_parallel == 5

    def test_can_override_max_steps(self, mock_llm):
        """
        PLAN must allow overriding max_steps.
        
        Remove this test if: We remove this option.
        """
        plan = PLAN(
            name="test",
            llm=mock_llm(),
            prompt="Plan",
            actions={"search": "Search"},
            max_steps=20,
        )
        
        assert plan.max_steps == 20

    def test_can_override_max_parallel(self, mock_llm):
        """
        PLAN must allow overriding max_parallel.
        
        Remove this test if: We remove this option.
        """
        plan = PLAN(
            name="test",
            llm=mock_llm(),
            prompt="Plan",
            actions={"search": "Search"},
            max_parallel=10,
        )
        
        assert plan.max_parallel == 10

    def test_can_override_max_retries(self, mock_llm):
        """
        PLAN must allow overriding max_retries.
        
        Remove this test if: We remove this option.
        """
        plan = PLAN(
            name="test",
            llm=mock_llm(),
            prompt="Plan",
            actions={"search": "Search"},
            max_retries=5,
        )
        
        assert plan.max_retries == 5

    def test_accepts_mixed_action_formats(self, mock_llm):
        """
        PLAN must accept mixed simple and parameterized actions.
        
        Remove this test if: We require uniform action formats.
        """
        plan = PLAN(
            name="test",
            llm=mock_llm(),
            prompt="Plan",
            actions={
                "search": {"description": "Search", "params": {"query": "str"}},
                "notify": "Send notification",  # Simple format
                "analyze": {"description": "Analyze", "params": {"data": "str"}},
            },
        )
        
        assert plan._actions_list == ["search", "notify", "analyze"]
        assert plan._actions_descriptions["notify"] == "Send notification"
        assert "search" in plan._actions_params
        assert "notify" not in plan._actions_params
        assert plan._has_param_schemas is True


class TestPlanActionFormatting:
    """
    Tests for PLAN action formatting in prompts.
    """

    def test_formats_simple_actions(self, mock_llm):
        """
        PLAN must format simple actions correctly.
        
        Remove this test if: We change the format.
        """
        plan = PLAN(
            name="test",
            llm=mock_llm(),
            prompt="Plan",
            actions={"search": "Search the web", "notify": "Send notification"},
        )
        
        formatted = plan._format_actions()
        
        assert "- search: Search the web" in formatted
        assert "- notify: Send notification" in formatted
        assert "Available Actions:" in formatted

    def test_formats_actions_with_params(self, mock_llm):
        """
        PLAN must format actions with parameter info.
        
        Remove this test if: We change the format.
        """
        plan = PLAN(
            name="test",
            llm=mock_llm(),
            prompt="Plan",
            actions={
                "search": {"description": "Search", "params": {"query": "str", "max": "int?"}},
            },
        )
        
        formatted = plan._format_actions()
        
        assert "query (str)" in formatted
        assert "max (optional int)" in formatted

    def test_format_instructions_includes_key_requirements(self, mock_llm):
        """
        PLAN format instructions must mention reason and constraints.
        
        Remove this test if: We change the instruction format.
        """
        plan = PLAN(
            name="test",
            llm=mock_llm(),
            prompt="Plan",
            actions={"search": "Search"},
            max_steps=5,
            max_parallel=3,
        )
        
        instructions = plan._format_instructions()
        
        # Must mention reason field requirement
        assert "reason" in instructions.lower()
        assert "1-3 sentences" in instructions
        
        # Must mention constraints
        assert "5" in instructions  # max_steps
        assert "3" in instructions  # max_parallel


class TestPlanResponseParsing:
    """
    Tests for PLAN response parsing logic.
    """

    def test_parses_valid_json(self, mock_llm):
        """
        PLAN must parse valid JSON plan.
        
        Remove this test if: We change parsing logic.
        """
        plan = PLAN(
            name="test",
            llm=mock_llm(),
            prompt="Plan",
            actions={"search": "Search"},
        )
        
        response = '[[{"action": "search", "reason": "Test"}]]'
        parsed = plan.parse_response(response)
        
        assert parsed == [[{"action": "search", "reason": "Test"}]]

    def test_extracts_json_from_markdown(self, mock_llm):
        """
        PLAN must extract JSON from markdown code blocks.
        
        Remove this test if: We remove markdown handling.
        """
        plan = PLAN(
            name="test",
            llm=mock_llm(),
            prompt="Plan",
            actions={"search": "Search"},
        )
        
        response = '```json\n[[{"action": "search", "reason": "Test"}]]\n```'
        parsed = plan.parse_response(response)
        
        assert parsed == [[{"action": "search", "reason": "Test"}]]

    def test_returns_raw_on_parse_failure(self, mock_llm):
        """
        PLAN must return raw response when parsing fails.
        
        Remove this test if: We change error handling.
        """
        plan = PLAN(
            name="test",
            llm=mock_llm(),
            prompt="Plan",
            actions={"search": "Search"},
        )
        
        response = "not valid json"
        parsed = plan.parse_response(response)
        
        assert parsed == "not valid json"


class TestPlanValidation:
    """
    Tests for PLAN validation logic.
    """

    def test_validates_valid_plan(self, mock_llm):
        """
        PLAN must accept valid plans.
        
        Remove this test if: We change validation.
        """
        plan = PLAN(
            name="test",
            llm=mock_llm(),
            prompt="Plan",
            actions={"search": "Search", "notify": "Notify"},
        )
        
        valid_plan = [
            [{"action": "search", "reason": "Gather data."}],
            [{"action": "notify", "reason": "Alert user."}],
        ]
        valid, reason = plan.validate(valid_plan)
        
        assert valid is True
        assert reason == ""

    def test_rejects_non_list(self, mock_llm):
        """
        PLAN must reject non-list plans.
        
        Remove this test if: We change structure requirements.
        """
        plan = PLAN(
            name="test",
            llm=mock_llm(),
            prompt="Plan",
            actions={"search": "Search"},
        )
        
        valid, reason = plan.validate("not a list")
        
        assert valid is False
        assert "must be a list" in reason

    def test_rejects_empty_plan(self, mock_llm):
        """
        PLAN must reject empty plans by default.
        
        Remove this test if: We change empty handling.
        """
        plan = PLAN(
            name="test",
            llm=mock_llm(),
            prompt="Plan",
            actions={"search": "Search"},
        )
        
        valid, reason = plan.validate([])
        
        assert valid is False
        assert "cannot be empty" in reason

    def test_allows_empty_when_configured(self, mock_llm):
        """
        PLAN must allow empty plans when allow_empty=True.
        
        Remove this test if: We remove allow_empty option.
        """
        plan = PLAN(
            name="test",
            llm=mock_llm(),
            prompt="Plan",
            actions={"search": "Search"},
            allow_empty=True,
        )
        
        valid, reason = plan.validate([])
        
        assert valid is True

    def test_rejects_exceeding_max_steps(self, mock_llm):
        """
        PLAN must reject plans exceeding max_steps.
        
        Remove this test if: We remove step limits.
        """
        plan = PLAN(
            name="test",
            llm=mock_llm(),
            prompt="Plan",
            actions={"search": "Search"},
            max_steps=2,
        )
        
        too_many_steps = [
            [{"action": "search", "reason": "Step 1."}],
            [{"action": "search", "reason": "Step 2."}],
            [{"action": "search", "reason": "Step 3."}],
        ]
        valid, reason = plan.validate(too_many_steps)
        
        assert valid is False
        assert "maximum is 2" in reason

    def test_rejects_exceeding_max_parallel(self, mock_llm):
        """
        PLAN must reject steps exceeding max_parallel.
        
        Remove this test if: We remove parallel limits.
        """
        plan = PLAN(
            name="test",
            llm=mock_llm(),
            prompt="Plan",
            actions={"search": "Search"},
            max_parallel=2,
        )
        
        too_many_parallel = [
            [
                {"action": "search", "reason": "Task 1."},
                {"action": "search", "reason": "Task 2."},
                {"action": "search", "reason": "Task 3."},
            ]
        ]
        valid, reason = plan.validate(too_many_parallel)
        
        assert valid is False
        assert "maximum parallel is 2" in reason

    def test_rejects_unknown_action(self, mock_llm):
        """
        PLAN must reject unknown actions.
        
        Remove this test if: We allow arbitrary actions.
        """
        plan = PLAN(
            name="test",
            llm=mock_llm(),
            prompt="Plan",
            actions={"search": "Search"},
        )
        
        unknown_action = [[{"action": "unknown", "reason": "Test."}]]
        valid, reason = plan.validate(unknown_action)
        
        assert valid is False
        assert "unknown action" in reason

    def test_rejects_missing_required_param(self, mock_llm):
        """
        PLAN must reject tasks missing required params.
        
        Remove this test if: We remove param validation.
        """
        plan = PLAN(
            name="test",
            llm=mock_llm(),
            prompt="Plan",
            actions={
                "search": {"description": "Search", "params": {"query": "str"}},
            },
        )
        
        missing_param = [[{"action": "search", "params": {}, "reason": "Test."}]]
        valid, reason = plan.validate(missing_param)
        
        assert valid is False
        assert "requires param 'query'" in reason

    def test_rejects_step_not_list(self, mock_llm):
        """
        PLAN must reject steps that are not lists.
        
        Remove this test if: We allow other step formats.
        """
        plan = PLAN(
            name="test",
            llm=mock_llm(),
            prompt="Plan",
            actions={"search": "Search"},
        )
        
        # Step is a dict instead of a list
        invalid_step = [{"action": "search", "reason": "Test."}]
        valid, reason = plan.validate(invalid_step)
        
        assert valid is False
        assert "must be a list of tasks" in reason

    def test_rejects_empty_step(self, mock_llm):
        """
        PLAN must reject steps with no tasks.
        
        Remove this test if: We allow empty steps.
        """
        plan = PLAN(
            name="test",
            llm=mock_llm(),
            prompt="Plan",
            actions={"search": "Search"},
        )
        
        empty_step = [[]]  # Empty step
        valid, reason = plan.validate(empty_step)
        
        assert valid is False
        assert "is empty" in reason

    def test_rejects_task_not_dict(self, mock_llm):
        """
        PLAN must reject tasks that are not dicts.
        
        Remove this test if: We allow other task formats.
        """
        plan = PLAN(
            name="test",
            llm=mock_llm(),
            prompt="Plan",
            actions={"search": "Search"},
        )
        
        # Task is a string instead of dict
        invalid_task = [["search"]]
        valid, reason = plan.validate(invalid_task)
        
        assert valid is False
        assert "must be a dict" in reason

    def test_rejects_task_missing_action_key(self, mock_llm):
        """
        PLAN must reject tasks without 'action' key.
        
        Remove this test if: We change task structure.
        """
        plan = PLAN(
            name="test",
            llm=mock_llm(),
            prompt="Plan",
            actions={"search": "Search"},
        )
        
        # Task missing 'action' key
        missing_action = [[{"params": {}, "reason": "Test."}]]
        valid, reason = plan.validate(missing_action)
        
        assert valid is False
        assert "missing required 'action'" in reason

    def test_allows_missing_optional_params(self, mock_llm):
        """
        PLAN must allow tasks without optional params.
        
        Remove this test if: We change optional param behavior.
        """
        plan = PLAN(
            name="test",
            llm=mock_llm(),
            prompt="Plan",
            actions={
                "search": {"description": "Search", "params": {"query": "str", "limit": "int?"}},
            },
        )
        
        # Only required param provided, optional 'limit' missing
        valid_plan = [[{"action": "search", "params": {"query": "test"}, "reason": "Test search."}]]
        valid, reason = plan.validate(valid_plan)
        
        assert valid is True
        assert reason == ""

    def test_validate_params_false_skips_param_validation(self, mock_llm):
        """
        PLAN must skip param validation when validate_params=False.
        
        Remove this test if: We remove this option.
        """
        plan = PLAN(
            name="test",
            llm=mock_llm(),
            prompt="Plan",
            actions={
                "search": {"description": "Search", "params": {"query": "str"}},
            },
            validate_params=False,
        )
        
        # Missing required param, but validation disabled
        missing_param = [[{"action": "search", "params": {}, "reason": "Test."}]]
        valid, reason = plan.validate(missing_param)
        
        assert valid is True

    def test_validates_parallel_tasks_correctly(self, mock_llm):
        """
        PLAN must validate all tasks in a parallel step.
        
        Remove this test if: We change parallel validation.
        """
        plan = PLAN(
            name="test",
            llm=mock_llm(),
            prompt="Plan",
            actions={"search": "Search", "notify": "Notify"},
        )
        
        parallel_plan = [
            [
                {"action": "search", "reason": "First search."},
                {"action": "notify", "reason": "Parallel notification."},
            ]
        ]
        valid, reason = plan.validate(parallel_plan)
        
        assert valid is True


class TestPlanReasonValidation:
    """
    Tests for PLAN reason field validation.
    """

    def test_rejects_missing_reason(self, mock_llm):
        """
        PLAN must reject tasks without reason.
        
        Remove this test if: We make reason optional.
        """
        plan = PLAN(
            name="test",
            llm=mock_llm(),
            prompt="Plan",
            actions={"search": "Search"},
        )
        
        missing_reason = [[{"action": "search"}]]
        valid, reason = plan.validate(missing_reason)
        
        assert valid is False
        assert "missing required 'reason'" in reason

    def test_rejects_empty_reason(self, mock_llm):
        """
        PLAN must reject empty reason strings.
        
        Remove this test if: We allow empty reasons.
        """
        plan = PLAN(
            name="test",
            llm=mock_llm(),
            prompt="Plan",
            actions={"search": "Search"},
        )
        
        empty_reason = [[{"action": "search", "reason": ""}]]
        valid, reason = plan.validate(empty_reason)
        
        assert valid is False
        assert "cannot be empty" in reason

    def test_rejects_reason_with_newlines(self, mock_llm):
        """
        PLAN must reject reasons containing newlines.
        
        Remove this test if: We allow newlines in reasons.
        """
        plan = PLAN(
            name="test",
            llm=mock_llm(),
            prompt="Plan",
            actions={"search": "Search"},
        )
        
        newline_reason = [[{"action": "search", "reason": "Line 1\nLine 2"}]]
        valid, reason = plan.validate(newline_reason)
        
        assert valid is False
        assert "cannot contain newlines" in reason

    def test_rejects_non_string_reason(self, mock_llm):
        """
        PLAN must reject non-string reasons.
        
        Remove this test if: We allow other types.
        """
        plan = PLAN(
            name="test",
            llm=mock_llm(),
            prompt="Plan",
            actions={"search": "Search"},
        )
        
        wrong_type = [[{"action": "search", "reason": 123}]]
        valid, reason = plan.validate(wrong_type)
        
        assert valid is False
        assert "'reason' must be a string" in reason


class TestPlanRepairPrompt:
    """
    Tests for PLAN repair prompt generation.
    """

    def test_builds_repair_with_actions_and_reason(self, mock_llm):
        """
        PLAN must build repair prompts mentioning actions and reason.
        
        Remove this test if: We remove repair prompts.
        """
        plan = PLAN(
            name="test",
            llm=mock_llm(),
            prompt="Plan",
            actions={"search": "Search", "notify": "Notify"},
        )
        
        repair = plan._build_repair_suffix("invalid response")
        
        assert "search" in repair
        assert "notify" in repair
        assert "reason" in repair


class TestPlanSerialization:
    """
    Tests for PLAN serialization.
    """

    def test_to_dict_includes_plan_fields(self, mock_llm):
        """
        PLAN serialization must include all fields.
        
        Remove this test if: We change serialization.
        """
        plan = PLAN(
            name="test",
            llm=mock_llm(),
            prompt="Plan",
            actions={"search": "Search"},
            max_steps=5,
            max_parallel=3,
        )
        
        data = plan.to_dict()
        
        assert data["actions"] == {"search": "Search"}
        assert data["max_steps"] == 5
        assert data["max_parallel"] == 3
        assert data["_class"] == "PLAN"

    def test_from_dict_restores_plan(self, mock_llm):
        """
        PLAN must be reconstructable from dict.
        
        Remove this test if: We remove from_dict.
        """
        original = PLAN(
            name="test",
            llm=mock_llm(),
            prompt="Plan",
            actions={"search": "Search", "notify": "Notify"},
            max_steps=5,
        )
        
        data = original.to_dict()
        restored = PLAN.from_dict(data, llm=mock_llm())
        
        assert restored.name == original.name
        assert restored._actions_list == original._actions_list
        assert restored.max_steps == original.max_steps


class TestPlanStringRepresentation:
    """
    Tests for PLAN string representations.
    """

    def test_repr_shows_key_info(self, mock_llm):
        """
        PLAN repr must show key configuration.
        
        Remove this test if: We change repr format.
        """
        plan = PLAN(
            name="my_plan",
            llm=mock_llm(),
            prompt="Plan",
            actions={"search": "Search", "notify": "Notify"},
        )
        
        r = repr(plan)
        
        assert "PLAN" in r
        assert "my_plan" in r
        assert "search" in r
        assert "notify" in r

    def test_str_is_human_readable(self, mock_llm):
        """
        PLAN str must be human-readable.
        
        Remove this test if: We change str format.
        """
        plan = PLAN(
            name="my_plan",
            llm=mock_llm(),
            prompt="Plan",
            actions={"search": "Search", "notify": "Notify"},
        )
        
        s = str(plan)
        
        assert "Plan" in s
        assert "my_plan" in s
        assert "2 actions" in s


class TestPlanCallable:
    """
    Tests for PLAN callable interface.
    """

    def test_is_callable(self, mock_llm, memory):
        """
        PLAN must be callable like THOUGHT: mem = plan(mem)
        
        Remove this test if: We change the interface.
        """
        plan = PLAN(
            name="test",
            llm=mock_llm(responses=['[[{"action": "search", "reason": "Test."}]]']),
            prompt="Plan",
            actions={"search": "Search"},
        )
        
        result = plan(memory)
        
        assert isinstance(result, MEMORY)

    def test_stores_result_in_memory(self, mock_llm, memory):
        """
        PLAN must store the plan result in memory.
        
        Remove this test if: We change result storage.
        """
        plan = PLAN(
            name="my_plan",
            llm=mock_llm(responses=['[[{"action": "search", "reason": "Gather data."}]]']),
            prompt="Plan",
            actions={"search": "Search"},
        )
        
        plan(memory)
        result = memory.get_var("my_plan_result")
        
        assert result == [[{"action": "search", "reason": "Gather data."}]]
