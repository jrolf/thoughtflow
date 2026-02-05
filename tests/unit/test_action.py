"""
Unit tests for the ThoughtFlow ACTION class.

The ACTION class wraps external operations (functions) with consistent
logging, result storage, and execution tracking. It provides:
- Automatic logging of inputs, outputs, and timing
- Error handling and recording
- Execution history tracking
- Integration with MEMORY for state storage

ACTIONs are the bridge between LLM cognition (THOUGHT) and real-world effects.
"""

from __future__ import annotations

import time
import pytest

from thoughtflow import ACTION, MEMORY


# ============================================================================
# Initialization Tests
# ============================================================================


class TestActionInitialization:
    """
    Tests for ACTION initialization and configuration.
    """

    def test_creates_with_name(self):
        """
        ACTION must store the provided name.
        
        The name identifies the action in logs and traces.
        
        Remove this test if: We change the initialization signature.
        """
        action = ACTION(name="send_email", fn=lambda mem: None)
        
        assert action.name == "send_email"

    def test_generates_unique_id(self):
        """
        Each ACTION must have a unique ID.
        
        IDs enable tracking and debugging.
        
        Remove this test if: We change ID generation.
        """
        action1 = ACTION(name="a1", fn=lambda mem: None)
        action2 = ACTION(name="a2", fn=lambda mem: None)
        
        assert action1.id != action2.id

    def test_stores_function_reference(self):
        """
        ACTION must store the function for later execution.
        
        The function is called when the action is invoked.
        
        Remove this test if: We change how functions are stored.
        """
        def my_func(mem):
            return "result"
        
        action = ACTION(name="test", fn=my_func)
        
        assert action.fn is my_func

    def test_stores_optional_description(self):
        """
        ACTION must store the optional description.
        
        Descriptions help document what the action does.
        
        Remove this test if: We remove description support.
        """
        action = ACTION(
            name="test",
            fn=lambda mem: None,
            description="This action sends an email",
        )
        
        assert "email" in action.description.lower()

    def test_default_description_includes_name(self):
        """
        ACTION default description must include the action name.
        
        Remove this test if: We change default description.
        """
        action = ACTION(name="my_action", fn=lambda mem: None)
        
        assert "my_action" in action.description

    def test_result_key_defaults_to_name_result(self):
        """
        ACTION result_key must default to {name}_result.
        
        Remove this test if: We change result_key default.
        """
        action = ACTION(name="compute", fn=lambda mem: None)
        
        assert action.result_key == "compute_result"


# ============================================================================
# Execution Tests
# ============================================================================


class TestActionExecution:
    """
    Tests for ACTION execution behavior.
    """

    def test_calls_function_with_memory(self, memory):
        """
        ACTION must call the function with the memory object.
        
        The function receives memory as the first argument.
        
        Remove this test if: We change function signature.
        """
        received_memory = []
        
        def capture_memory(mem):
            received_memory.append(mem)
            return "done"
        
        action = ACTION(name="test", fn=capture_memory)
        action(memory)
        
        assert received_memory[0] is memory

    def test_returns_memory_instance(self, memory):
        """
        ACTION must return the memory instance.
        
        This enables chaining: mem = action1(action2(mem))
        
        Remove this test if: We change return type.
        """
        action = ACTION(name="test", fn=lambda mem: "result")
        result = action(memory)
        
        assert result is memory

    def test_stores_result_in_memory(self, memory):
        """
        ACTION must store the result in memory at result_key.
        
        This enables accessing results via memory.get_var().
        
        Remove this test if: We change result storage.
        """
        def compute(mem):
            return "computed value"
        
        action = ACTION(name="compute", fn=compute)
        action(memory)
        
        assert memory.get_var("compute_result") == "computed value"

    def test_logs_execution_to_memory(self, memory):
        """
        ACTION must log its execution to memory.
        
        Logs enable debugging and audit trails.
        
        Remove this test if: We remove execution logging.
        """
        action = ACTION(name="test_action", fn=lambda mem: "ok")
        action(memory)
        
        logs = memory.get_logs()
        assert len(logs) > 0

    def test_passes_kwargs_to_function(self, memory):
        """
        ACTION must pass kwargs to the function.
        
        This enables parameterizing action execution.
        
        Remove this test if: We change kwarg handling.
        """
        received_kwargs = []
        
        def capture_kwargs(mem, **kwargs):
            received_kwargs.append(kwargs)
            return "done"
        
        action = ACTION(name="test", fn=capture_kwargs)
        action(memory, param1="value1", param2=42)
        
        assert received_kwargs[0] == {'param1': 'value1', 'param2': 42}

    def test_config_provides_default_kwargs(self, memory):
        """
        ACTION config must provide default kwargs.
        
        Config values can be overridden at call time.
        
        Remove this test if: We remove config support.
        """
        received_kwargs = []
        
        def capture_kwargs(mem, **kwargs):
            received_kwargs.append(kwargs)
            return "done"
        
        action = ACTION(
            name="test",
            fn=capture_kwargs,
            config={'default_param': 'default_value'},
        )
        action(memory)
        
        assert received_kwargs[0]['default_param'] == 'default_value'


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestActionErrorHandling:
    """
    Tests for ACTION error handling behavior.
    """

    def test_logs_error_to_memory(self, memory):
        """
        ACTION must log errors to memory.
        
        Error logs enable debugging after the fact.
        
        Remove this test if: We remove error logging.
        """
        def failing_func(mem):
            raise ValueError("Something went wrong")
        
        action = ACTION(name="failing", fn=failing_func)
        
        # Call the action (it catches exceptions)
        action(memory)
        
        logs = memory.get_logs()
        log_content = ' '.join(l['content'] for l in logs)
        # Should mention error
        assert 'error' in log_content.lower() or 'exception' in log_content.lower() or 'wrong' in log_content.lower()

    def test_stores_error_in_last_error(self, memory):
        """
        ACTION must store the error in last_error.
        
        This enables checking what went wrong.
        
        Remove this test if: We change error tracking.
        """
        def failing_func(mem):
            raise ValueError("Error message")
        
        action = ACTION(name="failing", fn=failing_func)
        action(memory)
        
        assert action.last_error is not None
        assert "Error message" in str(action.last_error)


# ============================================================================
# Execution History Tests
# ============================================================================


class TestActionExecutionHistory:
    """
    Tests for ACTION execution history tracking.
    """

    def test_tracks_execution_count(self, memory):
        """
        ACTION must track how many times it has been executed.
        
        This enables monitoring and rate limiting.
        
        Remove this test if: We remove execution tracking.
        """
        action = ACTION(name="counter", fn=lambda mem: "ok")
        
        assert action.execution_count == 0
        
        action(memory)
        assert action.execution_count == 1
        
        action(memory)
        assert action.execution_count == 2

    def test_records_last_result(self, memory):
        """
        ACTION must record the last execution result.
        
        This enables checking the most recent output.
        
        Remove this test if: We remove result recording.
        """
        action = ACTION(name="counter", fn=lambda mem: "latest result")
        
        action(memory)
        
        assert action.last_result == "latest result"

    def test_tracks_execution_history(self, memory):
        """
        ACTION must track execution history with timing.
        
        Remove this test if: We remove history tracking.
        """
        action = ACTION(name="test", fn=lambda mem: "ok")
        
        assert action.execution_history == []
        
        action(memory)
        
        assert len(action.execution_history) > 0

    def test_execution_history_includes_timing(self, memory):
        """
        Execution history must include timing information.
        
        Remove this test if: We change history format.
        """
        def slow_func(mem):
            time.sleep(0.01)  # 10ms
            return "done"
        
        action = ACTION(name="slow", fn=slow_func)
        action(memory)
        
        history_entry = action.execution_history[-1]
        assert 'duration_ms' in history_entry
        assert history_entry['duration_ms'] >= 10


# ============================================================================
# Serialization Tests
# ============================================================================


class TestActionSerialization:
    """
    Tests for ACTION serialization and deserialization.
    """

    def test_to_dict_captures_config(self):
        """
        to_dict must capture action configuration (not the function).
        
        Configuration can be serialized, but functions cannot.
        
        Remove this test if: We remove serialization.
        """
        action = ACTION(
            name="test_action",
            fn=lambda mem: None,
            description="Test description",
            result_key="custom_result",
        )
        
        data = action.to_dict()
        
        assert data['name'] == 'test_action'
        assert data['description'] == 'Test description'
        assert data['result_key'] == 'custom_result'

    def test_to_dict_excludes_function(self):
        """
        to_dict must exclude the function (not serializable).
        
        Functions can't be JSON serialized.
        
        Remove this test if: We add function serialization.
        """
        def my_func(mem):
            return 42
        
        action = ACTION(name="test", fn=my_func)
        data = action.to_dict()
        
        # Should not include the actual function
        assert 'fn' not in data or data['fn'] is None

    def test_from_dict_restores_config(self):
        """
        from_dict must restore configuration from dict using a function registry.
        
        Since functions can't be serialized, they must be provided via registry.
        
        Remove this test if: We change deserialization.
        """
        def my_func(mem):
            return 42
        
        original = ACTION(
            name="test",
            fn=my_func,
            description="Test desc",
            result_key="my_result",
        )
        data = original.to_dict()
        
        # Function must be provided via registry
        fn_registry = {'my_func': my_func}
        restored = ACTION.from_dict(data, fn_registry)
        
        assert restored.name == "test"
        assert restored.description == "Test desc"
        assert restored.result_key == "my_result"
        assert restored.fn is my_func
