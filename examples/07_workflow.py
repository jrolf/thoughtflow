#!/usr/bin/env python3
"""
ThoughtFlow Example 07: Multi-Step Agent Workflow

Demonstrates how to build a complete agent workflow by combining
multiple THOUGHTs and ACTIONs. This example shows a "Research Assistant"
that can plan research, search for information, and synthesize findings.

Key patterns demonstrated:
- Defining multiple specialized THOUGHTs
- Creating ACTIONs for external operations
- Chaining THOUGHT -> ACTION -> THOUGHT
- Passing data between steps via MEMORY
- Conditional execution based on results
- Error handling in workflows

Prerequisites:
    pip install thoughtflow
    export OPENAI_API_KEY=sk-...  (optional, uses mock LLM by default)

Run:
    python examples/07_workflow.py
"""

import os
from thoughtflow import MEMORY, THOUGHT, ACTION, LLM


# =============================================================================
# Mock Components (for demo without API calls)
# =============================================================================

class MockLLM:
    """Mock LLM that returns predefined responses based on prompt keywords."""
    
    def __init__(self):
        self.call_count = 0
    
    def call(self, msgs, params=None, **kwargs):
        self.call_count += 1
        
        # Get the last user message to determine response
        user_msg = ""
        for msg in msgs:
            if msg.get("role") == "user":
                user_msg = msg.get("content", "")
        
        # Return different responses based on context
        if "plan" in user_msg.lower() or "break down" in user_msg.lower():
            return ["""
```python
{
    'research_plan': [
        {'step': 1, 'action': 'search', 'query': 'ThoughtFlow framework overview'},
        {'step': 2, 'action': 'search', 'query': 'ThoughtFlow vs LangChain comparison'},
        {'step': 3, 'action': 'synthesize', 'inputs': ['step1_result', 'step2_result']}
    ],
    'estimated_time': '5 minutes'
}
```
            """]
        elif "synthesize" in user_msg.lower() or "combine" in user_msg.lower():
            return ["""
Based on my research, here's a synthesis:

ThoughtFlow is a minimal, explicit Python framework for building LLM applications.
Unlike LangChain, it emphasizes:
1. Tiny surface area with few powerful primitives
2. Explicit state management via MEMORY
3. Portable, testable designs
4. Zero required dependencies

Key components: LLM, MEMORY, THOUGHT, ACTION.
            """]
        else:
            return ["Here's some research information about the requested topic."]


def mock_search(memory, query, max_results=3):
    """Mock search function that returns simulated results."""
    # Simulate search results
    results = {
        "ThoughtFlow framework overview": [
            {"title": "ThoughtFlow: Minimal LLM Framework", "snippet": "A Pythonic approach to LLM systems..."},
            {"title": "Getting Started with ThoughtFlow", "snippet": "Learn the core primitives..."},
        ],
        "ThoughtFlow vs LangChain comparison": [
            {"title": "Comparing LLM Frameworks", "snippet": "ThoughtFlow takes a different approach..."},
            {"title": "When to Use ThoughtFlow", "snippet": "For explicit, testable systems..."},
        ]
    }
    
    return {
        "query": query,
        "results": results.get(query, [{"title": "Generic Result", "snippet": "Information about " + query}]),
        "count": len(results.get(query, [{"title": "Generic Result"}]))
    }


def save_report(memory, title, content, format="markdown"):
    """Mock function to save a research report."""
    report_id = f"report_{hash(title) % 10000:04d}"
    return {
        "id": report_id,
        "title": title,
        "format": format,
        "saved": True,
        "content_length": len(content)
    }


# =============================================================================
# Workflow Definition
# =============================================================================

def create_research_agent():
    """Create the components for a research assistant agent."""
    
    # Use mock LLM (replace with real LLM if API key is available)
    if os.getenv("OPENAI_API_KEY"):
        llm = LLM("openai:gpt-4o-mini", key=os.environ["OPENAI_API_KEY"])
    else:
        llm = MockLLM()
    
    # --- THOUGHT: Plan Research ---
    plan_thought = THOUGHT(
        name="plan_research",
        llm=llm,
        prompt="""
        You are a research planner. Given the user's research topic, create a structured plan.
        
        Topic: {research_topic}
        
        Return a Python dict with:
        - research_plan: list of steps with 'step', 'action', 'query' or 'inputs'
        - estimated_time: string estimate
        
        Actions can be: 'search', 'synthesize'
        """,
        parsing_rules={
            "kind": "python",
            "format": {
                "research_plan": [],
                "estimated_time": ""
            }
        },
        description="Creates a structured research plan",
        channel="api"
    )
    
    # --- THOUGHT: Synthesize Results ---
    synthesize_thought = THOUGHT(
        name="synthesize",
        llm=llm,
        prompt="""
        You are a research synthesizer. Combine the following search results into a coherent summary.
        
        Search Results:
        {search_results}
        
        Original Topic: {research_topic}
        
        Provide a clear, well-organized synthesis of the findings.
        """,
        description="Combines search results into a summary",
        channel="api"
    )
    
    # --- THOUGHT: Check Completion ---
    check_thought = THOUGHT(
        name="check_complete",
        operation="conditional",
        condition=lambda mem, ctx: mem.get_var("synthesis_result") is not None,
        if_true={"complete": True, "status": "Research complete"},
        if_false={"complete": False, "status": "Research incomplete"},
        description="Checks if research is complete"
    )
    
    # --- ACTION: Search ---
    search_action = ACTION(
        name="search",
        fn=mock_search,
        config={"max_results": 5},
        description="Search for information on a query"
    )
    
    # --- ACTION: Save Report ---
    save_action = ACTION(
        name="save_report",
        fn=save_report,
        config={"format": "markdown"},
        description="Save the final research report"
    )
    
    return {
        "plan": plan_thought,
        "synthesize": synthesize_thought,
        "check_complete": check_thought,
        "search": search_action,
        "save_report": save_action,
    }


def run_research_workflow(topic):
    """Execute the research workflow for a given topic."""
    
    print(f"=== Starting Research Workflow ===")
    print(f"Topic: {topic}\n")
    
    # Initialize memory with the research topic
    memory = MEMORY()
    memory.set_var("research_topic", topic, desc="User's research topic")
    memory.add_msg("user", f"Research topic: {topic}", channel="api")
    
    # Get agent components
    agent = create_research_agent()
    
    # -------------------------------------------------------------------------
    # Step 1: Plan the research
    # -------------------------------------------------------------------------
    print("--- Step 1: Planning Research ---")
    memory = agent["plan"](memory)
    
    plan = memory.get_var("plan_research_result")
    if plan:
        print(f"Plan created with {len(plan.get('research_plan', []))} steps")
        print(f"Estimated time: {plan.get('estimated_time', 'unknown')}")
    else:
        print("Failed to create plan")
        return memory
    
    # -------------------------------------------------------------------------
    # Step 2: Execute search steps from plan
    # -------------------------------------------------------------------------
    print("\n--- Step 2: Executing Searches ---")
    
    search_results = []
    for step in plan.get("research_plan", []):
        if step.get("action") == "search":
            query = step.get("query", "")
            print(f"  Searching: {query}")
            
            # Execute search action with specific query
            memory = agent["search"](memory, query=query)
            result = memory.get_var("search_result")
            
            if result:
                search_results.append({
                    "step": step.get("step"),
                    "query": query,
                    "results": result.get("results", [])
                })
                print(f"    Found {result.get('count', 0)} results")
    
    # Store aggregated search results
    memory.set_var("search_results", search_results, desc="Aggregated search results")
    
    # -------------------------------------------------------------------------
    # Step 3: Synthesize findings
    # -------------------------------------------------------------------------
    print("\n--- Step 3: Synthesizing Results ---")
    
    # Format search results for synthesis prompt
    formatted_results = ""
    for sr in search_results:
        formatted_results += f"\nQuery: {sr['query']}\n"
        for r in sr['results']:
            formatted_results += f"  - {r['title']}: {r['snippet']}\n"
    
    memory.set_var("search_results", formatted_results, desc="Formatted for synthesis")
    
    memory = agent["synthesize"](memory)
    synthesis = memory.get_var("synthesize_result")
    
    if synthesis:
        print("Synthesis complete!")
        # Store as synthesis_result for the check_complete thought
        memory.set_var("synthesis_result", synthesis)
    
    # -------------------------------------------------------------------------
    # Step 4: Check completion and save
    # -------------------------------------------------------------------------
    print("\n--- Step 4: Finalizing ---")
    
    memory = agent["check_complete"](memory)
    status = memory.get_var("check_complete_result")
    
    if status and status.get("complete"):
        print(f"Status: {status.get('status')}")
        
        # Save the report
        memory = agent["save_report"](
            memory, 
            title=f"Research: {topic}",
            content=str(synthesis)
        )
        save_result = memory.get_var("save_report_result")
        print(f"Report saved: {save_result.get('id')}")
    else:
        print("Research incomplete - would trigger retry logic")
    
    return memory


def main():
    print("--- ThoughtFlow Multi-Step Workflow Demo ---\n")
    
    # Run the research workflow
    memory = run_research_workflow("ThoughtFlow Python Framework")
    
    # =========================================================================
    # Show Workflow Results
    # =========================================================================
    print("\n" + "=" * 60)
    print("=== Workflow Results ===")
    print("=" * 60)
    
    print("\n--- Final Synthesis ---")
    synthesis = memory.get_var("synthesis_result") or memory.get_var("synthesize_result")
    if synthesis:
        # Truncate for display
        display = str(synthesis)[:500]
        if len(str(synthesis)) > 500:
            display += "..."
        print(display)
    
    print("\n--- Memory State ---")
    print(f"Total variables: {len(memory.get_all_vars())}")
    print(f"Total messages: {len(memory.get_msgs())}")
    print(f"Total logs: {len(memory.get_logs())}")
    
    print("\n--- Execution Logs ---")
    for log in memory.get_logs(limit=10):
        content = log['content']
        if len(content) > 80:
            content = content[:80] + "..."
        print(f"  {content}")
    
    # =========================================================================
    # Key Patterns Summary
    # =========================================================================
    print("\n" + "=" * 60)
    print("=== Workflow Patterns ===")
    print("=" * 60)
    print("""
    1. COMPONENT DEFINITION:
       - Define THOUGHTs for reasoning/planning/synthesis
       - Define ACTIONs for external operations
       - Store components in a dict for easy access
    
    2. STATE MANAGEMENT:
       - All state flows through MEMORY
       - Variables pass data between steps
       - Messages track conversation history
       - Logs provide audit trail
    
    3. WORKFLOW EXECUTION:
       mem = thought(mem)  # Execute thought
       mem = action(mem)   # Execute action
       result = mem.get_var("name_result")  # Get result
    
    4. CONDITIONAL LOGIC:
       - Use conditional THOUGHT for branching
       - Check results with memory.get_var()
       - Handle errors via thought.last_error
    
    5. DATA FLOW:
       plan_thought -> creates research_plan
       search_action -> uses plan, creates search_result
       synthesize_thought -> uses search_results, creates synthesis
       save_action -> uses synthesis, creates save_result
    """)


if __name__ == "__main__":
    main()
