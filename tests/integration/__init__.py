"""
Integration tests for ThoughtFlow.

Integration tests:
- Hit real APIs (require API keys)
- Are slower and may cost money
- Run only on main branch or explicit trigger
- Use markers: @pytest.mark.integration

To run integration tests:
    THOUGHTFLOW_INTEGRATION_TESTS=1 pytest tests/integration/ -v
"""
