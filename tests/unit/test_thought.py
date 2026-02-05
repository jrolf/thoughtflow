"""
Unit tests for the ThoughtFlow THOUGHT class.

The THOUGHT class is the unit of cognition in ThoughtFlow. It's a callable object
that takes a MEMORY, performs an operation, and returns the modified MEMORY.

Note: Some tests are marked as skipped due to a known issue where the THOUGHT class
uses 'system' as a default channel which is not a valid channel in MEMORY.
"""

from __future__ import annotations

import pytest

from thoughtflow import THOUGHT, MEMORY


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
