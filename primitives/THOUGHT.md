# THOUGHT

> The atomic unit of cognition — the fundamental building block for LLM-based reasoning.

## Philosophy

THOUGHT is the discrete unit of cognition in ThoughtFlow. It answers the question: what is one step of reasoning? The equation is THOUGHT = Prompt + Context + LLM + Parsing + Validation. A thought takes a prompt template, fills it with context from MEMORY, sends it to an LLM, parses the response, validates it, and optionally retries if validation fails. By making this a first-class primitive, ThoughtFlow gives you a composable, traceable way to build multi-step cognitive systems.

THOUGHT exists because raw LLM calls are messy. Models add prose, code fences, and formatting you did not ask for. They sometimes return invalid JSON or miss required keys. THOUGHT encapsulates the full cycle — prompt construction, LLM invocation, parsing, validation, retry — so that higher-level primitives (AGENT, WORKFLOW) can compose clean steps without reimplementing this logic. It also enforces the framework contract: `memory = thought(memory)` or `memory = thought(memory, vars)`.

## How It Works

THOUGHT is callable. When you invoke it with a MEMORY (and optionally a vars dict), it dispatches to one of four operation types: llm_call, memory_query, variable_set, or conditional. For llm_call, it builds messages from the prompt template and context, calls the LLM, parses the response with a built-in or custom parser, validates with a built-in or custom validator, and retries with a repair prompt if validation fails. The result is stored in memory as `{name}_result`.

Prompt templates use `{variable}` placeholders filled from memory context. Parsers include text, json, list, custom callables, and schema-based parsing via valid_extract. Validators include any, has_keys:k1,k2, list_min_len:N, and custom callables. Pre and post hooks allow custom processing before and after execution. DECIDE and PLAN are subclasses that specialize THOUGHT for constrained choice and multi-step planning.

## Inputs & Configuration

| Parameter | Description |
|-----------|-------------|
| name | Unique identifier for this thought |
| llm | LLM instance (required for llm_call) |
| prompt | Template string with {variable} placeholders, or dict for variable_set |
| operation | llm_call, memory_query, variable_set, or conditional |
| system_prompt | Optional system prompt for LLM context |
| parser | text, json, list, or callable |
| parsing_rules | Schema for valid_extract (e.g., {'kind': 'python', 'format': []}) |
| validator | any, has_keys:k1,k2, list_min_len:N, or callable |
| max_retries | Retry attempts on validation failure |
| retry_delay | Delay between retries in seconds |
| required_vars | Variables required from memory |
| optional_vars | Optional variables from memory |
| output_var | Variable name for result (default: {name}_result) |
| pre_hook, post_hook | Callables for custom processing |
| channel | Channel for message tracking |
| add_reflection | Whether to add reflection on success |

## Usage

```python
from thoughtflow import MEMORY, THOUGHT, LLM

memory = MEMORY()
memory.add_msg('user', 'Summarize the key points.', channel='api')
llm = LLM(model_id='openai:gpt-4o-mini', key='...')

thought = THOUGHT(
    name='summarize',
    llm=llm,
    prompt='Summarize the last user message: {last_user_msg}',
    operation='llm_call'
)
memory = thought(memory)
result = memory.get_var('summarize_result')
```

```python
# Memory query (no LLM)
thought = THOUGHT(
    name='get_context',
    operation='memory_query',
    required_vars=['user_name', 'session_id']
)
memory = thought(memory)

# Variable set
thought = THOUGHT(
    name='init',
    operation='variable_set',
    prompt={'status': 'active', 'count': 0}
)
memory = thought(memory)
```

## Relationship to Other Primitives

THOUGHT consumes LLM (for llm_call) and MEMORY (for context and result storage). It is composed by AGENT (as atomic steps), WORKFLOW (as orchestrated steps), and CHAT (as the underlying turn logic). DECIDE and PLAN extend THOUGHT for specific patterns. ACTION is distinct — imperative operations invoked by code, not by LLM selection.

## Considerations for Future Development

- Native output_schema passthrough to LLM for providers with structured output
- Streaming passthrough when THOUGHT wraps an LLM call
- DECIDE and PLAN documented in their own primitive files
- Execution history and tracing integration with workflow observability
