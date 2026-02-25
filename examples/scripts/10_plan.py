#!/usr/bin/env python3
"""
ThoughtFlow Example 10: PLAN — Structured Multi-Step Planning

Demonstrates the PLAN class for generating structured execution plans:
- Simple actions (descriptions only)
- Actions with parameter schemas
- Plan structure: steps (sequential) containing tasks (parallel)
- Required "reason" field explaining each task
- Validation of actions and parameters
- Step result references

Prerequisites:
    pip install thoughtflow
    export OPENAI_API_KEY=sk-...  (for LLM examples)

Run:
    python examples/10_plan.py
"""

import json
from thoughtflow import MEMORY, PLAN


# Create a mock LLM for examples that don't need real API calls
class MockLLM:
    """A mock LLM that returns predefined responses for demonstration."""
    
    def __init__(self, responses=None):
        self.responses = responses or ["Mock response"]
        self.call_count = 0
        self.last_msgs = None
    
    def call(self, msgs, params=None, **kwargs):
        """Mock LLM call that returns predefined responses."""
        self.last_msgs = msgs
        response = self.responses[min(self.call_count, len(self.responses) - 1)]
        self.call_count += 1
        return [response]


def main():
    print("--- ThoughtFlow PLAN Demo ---\n")
    
    # =========================================================================
    # Part 1: Simple Actions (Descriptions Only)
    # =========================================================================
    print("=== Part 1: Simple Actions ===\n")
    
    # Mock response: a valid plan
    mock_plan = json.dumps([
        [{"action": "search", "reason": "Gather initial information about the topic."}],
        [{"action": "analyze", "reason": "Extract key insights from search results."}],
        [{"action": "summarize", "reason": "Condense findings into a clear summary."}],
    ])
    
    mock_llm = MockLLM(responses=[mock_plan])
    memory = MEMORY()
    
    planner = PLAN(
        name="simple_plan",
        llm=mock_llm,
        actions={
            "search": "Search the web for information",
            "analyze": "Analyze content for insights",
            "summarize": "Create a summary",
        },
        prompt="Create a plan to: {goal}",
    )
    
    memory.set_var("goal", "Research ThoughtFlow library")
    memory = planner(memory)
    
    plan = memory.get_var("simple_plan_result")
    print(f"Generated plan with {len(plan)} steps:")
    for i, step in enumerate(plan):
        print(f"  Step {i}: {len(step)} task(s)")
        for task in step:
            print(f"    - {task['action']}: {task['reason']}")

    # =========================================================================
    # Part 2: Actions with Parameter Schemas
    # =========================================================================
    print("\n=== Part 2: Actions with Parameters ===\n")
    
    mock_plan = json.dumps([
        [{"action": "search", "params": {"query": "ThoughtFlow Python", "max_results": 10},
          "reason": "Search for comprehensive information with adequate results."}],
        [{"action": "fetch", "params": {"url": "https://github.com/jrolf/thoughtflow"},
          "reason": "Retrieve the official repository for authoritative docs."}],
    ])
    
    mock_llm = MockLLM(responses=[mock_plan])
    memory = MEMORY()
    
    planner = PLAN(
        name="param_plan",
        llm=mock_llm,
        actions={
            "search": {
                "description": "Search for information",
                "params": {"query": "str", "max_results": "int?"}  # ? = optional
            },
            "fetch": {
                "description": "Fetch a resource",
                "params": {"url": "str"}
            },
        },
        prompt="Create a plan to: {goal}",
    )
    
    memory.set_var("goal", "Research and document ThoughtFlow")
    memory = planner(memory)
    
    plan = memory.get_var("param_plan_result")
    print("Generated plan with parameters:")
    for i, step in enumerate(plan):
        for task in step:
            print(f"  Step {i}: {task['action']}")
            print(f"    params: {task.get('params', {})}")
            print(f"    reason: {task['reason']}")

    # =========================================================================
    # Part 3: Parallel Tasks
    # =========================================================================
    print("\n=== Part 3: Parallel Tasks ===\n")
    
    mock_plan = json.dumps([
        [
            {"action": "search", "params": {"query": "ThoughtFlow features"},
             "reason": "Search for feature documentation."},
            {"action": "search", "params": {"query": "ThoughtFlow examples"},
             "reason": "Find usage examples in parallel."},
        ],
        [
            {"action": "summarize", "params": {"text": "{step_0_result}"},
             "reason": "Combine parallel search results into summary."},
        ],
    ])
    
    mock_llm = MockLLM(responses=[mock_plan])
    memory = MEMORY()
    
    planner = PLAN(
        name="parallel_plan",
        llm=mock_llm,
        actions={
            "search": {"description": "Search", "params": {"query": "str"}},
            "summarize": {"description": "Summarize", "params": {"text": "str"}},
        },
        prompt="Create a plan with parallel tasks: {goal}",
    )
    
    memory.set_var("goal", "Gather and summarize ThoughtFlow information")
    memory = planner(memory)
    
    plan = memory.get_var("parallel_plan_result")
    print("Plan with parallel execution:")
    for i, step in enumerate(plan):
        if len(step) > 1:
            print(f"  Step {i}: {len(step)} PARALLEL tasks")
        else:
            print(f"  Step {i}: 1 task")
        for task in step:
            print(f"    - {task['action']}: {task['reason'][:50]}...")

    # =========================================================================
    # Part 4: Validation
    # =========================================================================
    print("\n=== Part 4: Validation ===\n")
    
    planner = PLAN(
        name="validate_test",
        llm=MockLLM(),
        actions={
            "search": {"description": "Search", "params": {"query": "str"}},
            "notify": {"description": "Notify", "params": {"message": "str"}},
        },
        prompt="Test",
        max_steps=3,
        max_parallel=2,
    )
    
    # Valid plan
    valid_plan = [
        [{"action": "search", "params": {"query": "test"}, "reason": "Test search."}],
        [{"action": "notify", "params": {"message": "done"}, "reason": "Alert completion."}],
    ]
    is_valid, reason = planner.validate(valid_plan)
    print(f"Valid plan: {is_valid}")
    
    # Missing reason
    invalid_1 = [[{"action": "search", "params": {"query": "test"}}]]
    is_valid, reason = planner.validate(invalid_1)
    print(f"Missing reason: {is_valid} - {reason[:50]}")
    
    # Unknown action
    invalid_2 = [[{"action": "unknown", "reason": "Test."}]]
    is_valid, reason = planner.validate(invalid_2)
    print(f"Unknown action: {is_valid} - {reason[:50]}")
    
    # Missing required param
    invalid_3 = [[{"action": "search", "params": {}, "reason": "Test."}]]
    is_valid, reason = planner.validate(invalid_3)
    print(f"Missing param: {is_valid} - {reason[:50]}")
    
    # Too many steps
    invalid_4 = [
        [{"action": "search", "params": {"query": "1"}, "reason": "Step 1."}],
        [{"action": "search", "params": {"query": "2"}, "reason": "Step 2."}],
        [{"action": "search", "params": {"query": "3"}, "reason": "Step 3."}],
        [{"action": "search", "params": {"query": "4"}, "reason": "Step 4."}],
    ]
    is_valid, reason = planner.validate(invalid_4)
    print(f"Too many steps: {is_valid} - {reason[:50]}")

    # =========================================================================
    # Part 5: Format Actions
    # =========================================================================
    print("\n=== Part 5: Prompt Formatting ===\n")
    
    planner = PLAN(
        name="format_demo",
        llm=MockLLM(),
        actions={
            "search": {"description": "Search the web", "params": {"query": "str", "limit": "int?"}},
            "analyze": "Analyze content for insights",
            "notify": {"description": "Send notification", "params": {"msg": "str"}},
        },
        prompt="Demo",
    )
    
    print("Formatted actions shown to LLM:")
    print(planner._format_actions())

    # =========================================================================
    # Part 6: Serialization
    # =========================================================================
    print("\n=== Part 6: Serialization ===\n")
    
    planner = PLAN(
        name="serialize_demo",
        llm=MockLLM(),
        actions={"search": "Search", "notify": "Notify"},
        prompt="Test",
        max_steps=5,
        max_parallel=3,
    )
    
    data = planner.to_dict()
    print("Serialized PLAN:")
    print(f"  name: {data['name']}")
    print(f"  actions: {data['actions']}")
    print(f"  max_steps: {data['max_steps']}")
    print(f"  max_parallel: {data['max_parallel']}")
    print(f"  _class: {data['_class']}")
    
    # Reconstruct
    restored = PLAN.from_dict(data, llm=MockLLM())
    print(f"\nRestored: {restored}")

    # =========================================================================
    # Part 7: String Representations
    # =========================================================================
    print("\n=== Part 7: String Representations ===\n")
    
    planner = PLAN(
        name="repr_demo",
        llm=MockLLM(),
        actions={"a": "Action A", "b": "Action B", "c": "Action C"},
        prompt="Demo",
    )
    
    print(f"repr(): {repr(planner)}")
    print(f"str():  {str(planner)}")

    # =========================================================================
    # Part 8: Real-World Example — Research Workflow
    # =========================================================================
    print("\n=== Part 8: Real-World Example ===\n")
    
    # Simulate a research workflow plan
    mock_plan = json.dumps([
        [
            {"action": "search_web", "params": {"query": "ThoughtFlow Python library features"},
             "reason": "Gather feature information from multiple sources."},
            {"action": "search_web", "params": {"query": "ThoughtFlow vs LangChain comparison"},
             "reason": "Find comparative analysis to understand positioning."},
        ],
        [
            {"action": "fetch_page", "params": {"url": "{step_0_result[0].url}"},
             "reason": "Retrieve most relevant page from first search."},
            {"action": "fetch_page", "params": {"url": "https://pypi.org/project/thoughtflow/"},
             "reason": "Get official PyPI page for authoritative info."},
        ],
        [
            {"action": "extract_info", "params": {"content": "{step_1_result}", "focus": "key features"},
             "reason": "Extract key features from fetched content."},
        ],
        [
            {"action": "create_summary", "params": {"data": "{step_2_result}", "format": "bullet_points"},
             "reason": "Compile findings into structured summary."},
            {"action": "notify_user", "params": {"message": "Research complete", "channel": "slack"},
             "reason": "Alert the team that research is ready for review."},
        ],
    ])
    
    mock_llm = MockLLM(responses=[mock_plan])
    memory = MEMORY()
    
    research_planner = PLAN(
        name="research_workflow",
        llm=mock_llm,
        actions={
            "search_web": {
                "description": "Search the web for information",
                "params": {"query": "str", "max_results": "int?"}
            },
            "fetch_page": {
                "description": "Fetch content from a URL",
                "params": {"url": "str"}
            },
            "extract_info": {
                "description": "Extract specific information from content",
                "params": {"content": "str", "focus": "str?"}
            },
            "create_summary": {
                "description": "Create a formatted summary",
                "params": {"data": "str", "format": "str?"}
            },
            "notify_user": {
                "description": "Send notification to user",
                "params": {"message": "str", "channel": "str?"}
            },
        },
        prompt="""Create a research plan for: {goal}

Context: {context}

Requirements:
- Start with parallel searches to gather diverse information
- Fetch authoritative sources
- Extract and summarize key findings
- Notify when complete""",
        max_steps=10,
        max_parallel=3,
    )
    
    memory.set_var("goal", "Evaluate ThoughtFlow for our AI project")
    memory.set_var("context", "Team needs to decide on an LLM framework")
    memory = research_planner(memory)
    
    plan = memory.get_var("research_workflow_result")
    
    print("Research Workflow Plan:")
    print("-" * 50)
    for i, step in enumerate(plan):
        parallel_note = " (PARALLEL)" if len(step) > 1 else ""
        print(f"\nStep {i}{parallel_note}:")
        for task in step:
            print(f"  Action: {task['action']}")
            if task.get('params'):
                params_str = ", ".join(f"{k}={v}" for k, v in task['params'].items())
                print(f"  Params: {params_str[:60]}...")
            print(f"  Reason: {task['reason']}")

    # =========================================================================
    # Summary
    # =========================================================================
    print("\n=== Summary ===")
    print("""
    PLAN generates structured multi-step execution plans:
    
    1. Output Structure:
       Plan = List[List[Dict]]
       - Outer list: Steps (executed sequentially)
       - Inner list: Tasks (can execute in parallel)
       - Dict: {"action": "...", "params": {...}, "reason": "..."}
    
    2. Actions Format:
       - Simple: {"action": "Description"}
       - With params: {"action": {"description": "...", "params": {"arg": "type?"}}}
       - Use "?" suffix for optional params
    
    3. Required Fields:
       - action: Which action to execute
       - reason: 1-3 sentence explanation (required)
       - params: Optional, validated against schema if provided
    
    4. Step References:
       - Tasks can reference {step_N_result} from previous steps
    
    5. Validation:
       - Action names must be in defined actions
       - Required params must be present
       - Reason field must exist and be non-empty
       - Respects max_steps and max_parallel limits
    
    6. Defaults:
       - max_retries: 3
       - max_steps: 10
       - max_parallel: 5
    
    Use PLAN for:
    - Research workflows
    - Multi-step data processing
    - Complex task orchestration
    - Any scenario requiring structured, explainable plans
    """)


if __name__ == "__main__":
    main()
