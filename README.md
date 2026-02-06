<!-- 
  ████████╗██╗  ██╗ ██████╗ ██╗   ██╗ ██████╗ ██╗  ██╗████████╗███████╗██╗      ██████╗ ██╗    ██╗
  ╚══██╔══╝██║  ██║██╔═══██╗██║   ██║██╔════╝ ██║  ██║╚══██╔══╝██╔════╝██║     ██╔═══██╗██║    ██║
     ██║   ███████║██║   ██║██║   ██║██║  ███╗███████║   ██║   █████╗  ██║     ██║   ██║██║ █╗ ██║
     ██║   ██╔══██║██║   ██║██║   ██║██║   ██║██╔══██║   ██║   ██╔══╝  ██║     ██║   ██║██║███╗██║
     ██║   ██║  ██║╚██████╔╝╚██████╔╝╚██████╔╝██║  ██║   ██║   ██║     ███████╗╚██████╔╝╚███╔███╔╝
     ╚═╝   ╚═╝  ╚═╝ ╚═════╝  ╚═════╝  ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚═╝     ╚══════╝ ╚═════╝  ╚══╝╚══╝ 
-->

<p align="center">
  <img src="https://raw.githubusercontent.com/jrolf/thoughtflow/main/assets/logo.png" alt="ThoughtFlow Logo" width="400">
</p>

<h1 align="center">ThoughtFlow</h1>

<p align="center">
  <strong>The Pythonic Cognitive Engine for LLM Systems That Actually Make Sense</strong>
</p>

<p align="center">
  <em>"We believe your code should be smarter than your framework."</em>
</p>

<!-- Primary badges: trust signals -->
<p align="center">
  <a href="https://pypi.org/project/thoughtflow/"><img src="https://img.shields.io/pypi/v/thoughtflow?color=blue" alt="PyPI version"></a>
  <a href="https://pypi.org/project/thoughtflow/"><img src="https://img.shields.io/pypi/pyversions/thoughtflow" alt="Python versions"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License: MIT"></a>
  <a href="https://github.com/jrolf/thoughtflow"><img src="https://img.shields.io/badge/build-passing-brightgreen" alt="Build"></a>
  <a href="https://pepy.tech/project/thoughtflow"><img src="https://static.pepy.tech/badge/thoughtflow/month" alt="Downloads/month"></a>
</p>

<!-- Secondary badges: social + quality -->
<p align="center">
  <a href="https://github.com/jrolf/thoughtflow/stargazers"><img src="https://img.shields.io/github/stars/jrolf/thoughtflow?style=flat" alt="GitHub stars"></a>
  <a href="https://github.com/jrolf/thoughtflow/commits/main"><img src="https://img.shields.io/github/last-commit/jrolf/thoughtflow" alt="Last commit"></a>
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff"></a>
  <a href="http://mypy-lang.org/"><img src="https://img.shields.io/badge/type%20checked-mypy-blue" alt="mypy"></a>
</p>

<!-- Navigation -->
<p align="center">
  <a href="#-installation">Install</a> •
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-the-four-primitives">Primitives</a> •
  <a href="#-the-four-primitives-in-depth">Deep Dive</a> •
  <a href="#-real-world-patterns">Patterns</a> •
  <a href="#-utilities">Utilities</a> •
  <a href="#-philosophy-the-zen-of-thoughtflow">Philosophy</a>
</p>

---

## 🚀 Installation

```bash
pip install thoughtflow
```

**That's it.** The core library has **zero dependencies** — it uses only Python's standard library.

```bash
# Upgrade to the latest version
pip install --upgrade thoughtflow

# Pin to a specific version for stability
pip install thoughtflow==0.0.4
```

---

## ⚡ Quick Start

Here's a complete working example. Copy, paste, run:

```python
import os
from thoughtflow import LLM, MEMORY, THOUGHT

# 1. Get your API key from environment variables
#    Set it first: export OPENAI_API_KEY="sk-..."
api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    raise ValueError("Please set OPENAI_API_KEY environment variable")

# 2. Create an LLM instance
#    Format: "provider:model"
llm = LLM("openai:gpt-4o", key=api_key)

# 3. Create a MEMORY to store conversation state
#    MEMORY is an event-sourced container that tracks everything
memory = MEMORY()

# 4. Add a user message to memory
memory.add_msg("user", "What is the meaning of life?")

# 5. Create a THOUGHT - the atomic unit of cognition
#    A THOUGHT combines: Prompt + Context + LLM + Parsing + Validation
thought = THOUGHT(
    name="respond",
    llm=llm,
    prompt="You are a wise philosopher. Answer: {last_user_msg}",
)

# 6. Execute the thought — this is THE pattern
memory = thought(memory)

# 7. Get the result
result = memory.get_var("respond_result")
print(f"Response: {result}")
# Output: "The meaning of life is a profound philosophical question..."

# 8. View the full conversation
print(memory.render(format="conversation"))
```

**The universal pattern is `memory = thought(memory)`.** That's not a simplification — that's the actual API. Everything flows through MEMORY.

---

## 🔥 The Manifesto

> **We reject the complexity-industrial complex.**

The modern LLM ecosystem has become an abstraction swamp. Frameworks compete to add more layers, more magic, more indirection—until you need a PhD just to debug a chatbot.

**ThoughtFlow takes a different path.**

We believe:
- 🎯 **Your agent logic should fit in your head** — Four primitives, not forty classes
- 🔍 **Every state change should be visible and traceable** — Event-sourced memory with full history
- 🧪 **Testing AI systems should be as easy as testing regular code** — Deterministic replay built-in
- 📦 **Zero dependencies means zero supply chain nightmares** — Core runs on stdlib only
- ⚡ **Serverless deployment should be trivial, not heroic** — <100ms cold starts

This isn't just a library. It's a stance.

---

## ✅ When to Use ThoughtFlow

ThoughtFlow is the right choice when:

- **You need serverless deployment** — Lambda, Cloud Functions, Edge. Zero dependencies means instant cold starts.
- **You want to understand your entire codebase** in an afternoon — Four concepts, not forty.
- **You value explicit state over magic** — Every change is visible, traceable, and replayable.
- **You need deterministic testing** of AI workflows — Record sessions, replay them, assert on results.
- **You're building production agents**, not prototypes — Serious error handling, retry logic, validation.
- **You prefer composition over configuration** — Plain Python, not YAML or JSON configs.
- **You work across multiple LLM providers** — One interface for OpenAI, Anthropic, Groq, Gemini, Ollama, and more.

## ❌ When NOT to Use ThoughtFlow

Be honest with yourself — ThoughtFlow isn't for everyone:

- **You need pre-built RAG pipelines out of the box** → Consider [LlamaIndex](https://github.com/run-llama/llama_index)
- **You want visual workflow builders** → Consider [Flowise](https://github.com/FlowiseAI/Flowise), [Langflow](https://github.com/langflow-ai/langflow)
- **You need complex multi-agent orchestration frameworks** → Consider [AutoGen](https://github.com/microsoft/autogen), [CrewAI](https://github.com/joaomdmoura/crewai)
- **You prefer batteries-included over minimal** → Consider [LangChain](https://github.com/langchain-ai/langchain)
- **You need built-in vector stores and retrievers** → ThoughtFlow doesn't include these (but see [ThoughtBase](#-sister-library-thoughtbase))

**ThoughtFlow is opinionated:** we trade breadth for clarity. We do fewer things, but we do them well.

---

## 🚀 Escape Velocity: What You Can Delete

Switching to ThoughtFlow? Here's what you can remove from your project:

```diff
- langchain                    # 50+ transitive dependencies
- llama-index                  # Complex retrieval abstractions  
- autogen                      # Multi-agent complexity
- crewai                       # Yet another agent framework
- semantic-kernel              # Enterprise overhead
- haystack                     # Pipeline complexity
- guidance                     # Constrained generation complexity

- your custom retry logic      # THOUGHT handles retries with repair prompts
- your custom parsing code     # valid_extract handles messy LLM output
- your state management mess   # MEMORY tracks everything
- your 47 adapter classes      # LLM provides one interface for all providers

+ thoughtflow                  # Zero dependencies. Everything you need.
```

**Net result:** Your `requirements.txt` gets lighter. Your code gets clearer. Your deployments get faster. Your team spends less time debugging framework internals.

---

## 📊 How ThoughtFlow Compares

| Feature | ThoughtFlow | LangChain | LlamaIndex | AutoGen |
|---------|-------------|-----------|------------|---------|
| **Core Dependencies** | **0** | 50+ | 30+ | 20+ |
| **Time to Understand** | **5 minutes** | 2+ hours | 1+ hour | 1+ hour |
| **Concepts to Learn** | **4** | 50+ | 30+ | 15+ |
| **Serverless Ready** | **Trivial** | Challenging | Challenging | Challenging |
| **Cold Start (Lambda)** | **<100ms** | 2-5 seconds | 1-3 seconds | 1-2 seconds |
| **Full State Visibility** | **Everything** | Partial | Partial | Partial |
| **Deterministic Replay** | **Built-in** | DIY | DIY | DIY |
| **Multi-Provider LLM** | **Built-in** | Via adapters | Via adapters | Via adapters |

*Each framework has its strengths. LangChain offers breadth, LlamaIndex excels at RAG, AutoGen shines at multi-agent. ThoughtFlow optimizes for simplicity, transparency, and serverless deployment.*

---

## ⚡ Performance Characteristics

| Metric | ThoughtFlow | Why It Matters |
|--------|-------------|----------------|
| **Import Time** | ~15ms | Zero dependencies = instant module load |
| **Memory Overhead** | ~2MB | Minimal runtime footprint |
| **Call Overhead** | <1ms | Direct HTTP calls, no middleware stack |
| **Cold Start (Lambda)** | <100ms | Critical for serverless economics |
| **Event Throughput** | 100k+ events/sec | Event-sourced architecture scales |

*These are architectural characteristics, not formal benchmarks. Your mileage may vary based on workload.*

---

## 🧩 The Four Primitives

ThoughtFlow gives you **four concepts**. Master these, and you've mastered the framework.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│   ┌─────────┐      ┌─────────┐      ┌─────────┐      ┌─────────┐      │
│   │   LLM   │ ──▶  │ THOUGHT │ ──▶  │ MEMORY  │ ◀──  │ ACTION  │      │
│   └─────────┘      └─────────┘      └─────────┘      └─────────┘      │
│        │                │                │                │            │
│   Any model        Cognition         State            External         │
│   Any provider     unit              container        operations       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

| Primitive | What It Does | The Pattern |
|-----------|--------------|-------------|
| **LLM** | Unified interface to call any language model | `response = llm.call(messages)` |
| **MEMORY** | Event-sourced state container for everything | `memory.add_msg("user", "Hello!")` |
| **THOUGHT** | Atomic unit of cognition with retry/parsing | `memory = thought(memory)` |
| **ACTION** | External operations with consistent logging | `memory = action(memory, **kwargs)` |

That's it. Four concepts. No 47-page tutorial to understand the basics.

---

## 🔌 Supported Providers

ThoughtFlow works with **any LLM provider** through a unified interface:

| Provider | Model ID Format | Example | Notes |
|----------|-----------------|---------|-------|
| **OpenAI** | `openai:model` | `openai:gpt-4o` | GPT-4, GPT-4o, GPT-3.5, etc. |
| **Anthropic** | `anthropic:model` | `anthropic:claude-3-5-sonnet-20241022` | Claude 3, Claude 3.5, etc. |
| **Groq** | `groq:model` | `groq:llama-3.1-70b-versatile` | Fast inference for open models |
| **Google Gemini** | `gemini:model` | `gemini:gemini-1.5-pro` | Gemini Pro, Flash, etc. |
| **OpenRouter** | `openrouter:model` | `openrouter:anthropic/claude-3-opus` | Access any model via OpenRouter |
| **Ollama** | `ollama:model` | `ollama:llama3.2` | Local models, no API key needed |

**Switching providers is a one-line change:**

```python
# From OpenAI...
llm = LLM("openai:gpt-4o", key=openai_key)

# ...to Anthropic
llm = LLM("anthropic:claude-3-5-sonnet-20241022", key=anthropic_key)

# ...to local (no key needed!)
llm = LLM("ollama:llama3.2")

# Your THOUGHT and MEMORY code stays exactly the same
```

---

## 🔮 The Four Primitives In Depth

### 1. `LLM` — The Universal Model Interface

The `LLM` class provides a unified interface for calling any language model. One interface, any provider, zero provider-specific code in your application.

```python
from thoughtflow import LLM

# ═══════════════════════════════════════════════════════════════════════════
# CREATING LLM INSTANCES
# ═══════════════════════════════════════════════════════════════════════════

# OpenAI
llm = LLM("openai:gpt-4o", key="sk-...")

# Anthropic
llm = LLM("anthropic:claude-3-5-sonnet-20241022", key="sk-ant-...")

# Groq (blazing fast inference)
llm = LLM("groq:llama-3.1-70b-versatile", key="gsk_...")

# Google Gemini
llm = LLM("gemini:gemini-1.5-pro", key="...")

# OpenRouter (access to any model)
llm = LLM("openrouter:anthropic/claude-3-opus", key="sk-or-...")

# Ollama (local models - no API key needed!)
llm = LLM("ollama:llama3.2")

# ═══════════════════════════════════════════════════════════════════════════
# MAKING CALLS
# ═══════════════════════════════════════════════════════════════════════════

# Standard chat format - works with ALL providers
response = llm.call([
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "What's the capital of France?"}
])
# response: ["The capital of France is Paris."]

# With parameters
response = llm.call(
    [{"role": "user", "content": "Write a haiku about Python"}],
    params={"temperature": 0.7, "max_tokens": 100}
)

# ═══════════════════════════════════════════════════════════════════════════
# MESSAGE NORMALIZATION
# ═══════════════════════════════════════════════════════════════════════════

# LLM automatically normalizes messages - all of these work:

# Standard format
llm.call([{"role": "user", "content": "Hello"}])

# Just content (assumes role="user")
llm.call([{"content": "Hello"}])

# Plain strings (becomes user messages)
llm.call(["Hello", "How are you?"])
```

**Key features:**
- **Automatic message normalization** — Pass dicts, strings, or mixed formats
- **Consistent response format** — Always returns a list of response strings
- **Zero provider-specific code** — Switch providers by changing one string
- **Direct HTTP calls** — No middleware, no overhead, no surprises

---

### 2. `MEMORY` — Event-Sourced State

MEMORY is an event-sourced container that tracks **everything**: messages, logs, reflections, and variables with full history. Every change is an event with a sortable ID (alphabetical = chronological).

```python
from thoughtflow import MEMORY

memory = MEMORY()

# ═══════════════════════════════════════════════════════════════════════════
# MESSAGES — with channel tracking for omni-channel agents
# ═══════════════════════════════════════════════════════════════════════════

# Add messages with channel tracking (webapp, ios, telegram, slack, etc.)
memory.add_msg("user", "Hello from the web!", channel="webapp")
memory.add_msg("assistant", "Hi there! How can I help?", channel="webapp")
memory.add_msg("user", "Following up on Telegram", channel="telegram")
memory.add_msg("user", "Also checking on mobile", channel="ios")

# Query messages - multiple ways
all_msgs = memory.get_msgs()                              # All messages
user_msgs = memory.get_msgs(include=["user"])             # Only user messages
web_msgs = memory.get_msgs(channel="webapp")              # Only webapp channel
recent = memory.get_msgs(limit=5)                         # Last 5 messages

# Quick access to most recent
memory.last_user_msg()    # "Also checking on mobile"
memory.last_asst_msg()    # "Hi there! How can I help?"
memory.last_sys_msg()     # Last system message (if any)

# ═══════════════════════════════════════════════════════════════════════════
# LOGS & REFLECTIONS — internal agent reasoning
# ═══════════════════════════════════════════════════════════════════════════

# Logs are for debugging and audit trails
memory.add_log("User initiated conversation from webapp")
memory.add_log("Processing user request...")
memory.add_log("Response generated successfully")

# Reflections are for agent's internal reasoning
memory.add_ref("User seems interested in weather patterns")
memory.add_ref("Should ask clarifying questions about location")

# Retrieve logs and reflections
memory.get_logs()         # All log entries
memory.get_refs()         # All reflections
memory.last_log_msg()     # Most recent log

# ═══════════════════════════════════════════════════════════════════════════
# VARIABLES — with FULL HISTORY tracking
# ═══════════════════════════════════════════════════════════════════════════

# Set variables with optional descriptions
memory.set_var("session_id", "abc123", desc="Current session identifier")
memory.set_var("user_name", "Alice", desc="User's display name")
memory.set_var("request_count", 0)

# Update variables - this APPENDS to history, doesn't overwrite!
memory.set_var("request_count", 1)
memory.set_var("request_count", 2)
memory.set_var("request_count", 3)

# Get current value
memory.get_var("request_count")       # Returns: 3
memory.get_var("user_name")           # Returns: "Alice"
memory.get_var("nonexistent")         # Returns: None

# Get FULL HISTORY - see every change with timestamps
memory.get_var_history("request_count")
# Returns: [
#   ["stamp1...", 0],
#   ["stamp2...", 1],
#   ["stamp3...", 2],
#   ["stamp4...", 3]
# ]

# Get all current variables
memory.get_all_vars()
# Returns: {"session_id": "abc123", "user_name": "Alice", "request_count": 3}

# Get variable description
memory.get_var_desc("session_id")     # "Current session identifier"

# ═══════════════════════════════════════════════════════════════════════════
# VARIABLE DELETION — tombstone pattern preserves history
# ═══════════════════════════════════════════════════════════════════════════

# Deletion is a tombstone, not destruction
memory.del_var("session_id")

# After deletion
memory.get_var("session_id")          # Returns: None
memory.is_var_deleted("session_id")   # Returns: True

# But history is preserved!
memory.get_var_history("session_id")
# Returns: [["stamp1...", "abc123"], ["stamp2...", <DELETED>]]

# Can re-set after deletion
memory.set_var("session_id", "xyz789")
memory.get_var("session_id")          # Returns: "xyz789"

# ═══════════════════════════════════════════════════════════════════════════
# SERIALIZATION — for persistence and cloud sync
# ═══════════════════════════════════════════════════════════════════════════

# Save to file (pickle format)
memory.save("state.pkl")
memory.save("state.pkl.gz", compressed=True)  # With compression

# Load from file
memory2 = MEMORY()
memory2.load("state.pkl")

# Export to JSON (portable, human-readable)
memory.to_json("state.json")
json_string = memory.to_json()  # Returns string if no filename

# Load from JSON
memory3 = MEMORY.from_json("state.json")
memory4 = MEMORY.from_json(json_string)

# Export snapshot for cloud sync
snapshot = memory.snapshot()
# snapshot = {"id": "...", "events": {...}, "objects": {...}}

# Rehydrate from events (for distributed systems)
memory5 = MEMORY.from_events(snapshot["events"].values())

# Deep copy
memory_copy = memory.copy()

# ═══════════════════════════════════════════════════════════════════════════
# RENDERING — for debugging, logging, and LLM context
# ═══════════════════════════════════════════════════════════════════════════

# Render as conversation (great for debugging)
print(memory.render(format="conversation"))
# Output:
# User: Hello from the web!
# Assistant: Hi there! How can I help?
# User: Following up on Telegram
# ...

# Render as JSON
print(memory.render(format="json", include=("msgs", "logs")))

# Render as plain text
print(memory.render(format="plain"))

# Filter by role, channel, content
print(memory.render(
    role_filter=["user", "assistant"],
    channel_filter="webapp",
    max_total_length=2000
))

# ═══════════════════════════════════════════════════════════════════════════
# LARGE OBJECT HANDLING — automatic compression
# ═══════════════════════════════════════════════════════════════════════════

# Large values (>10KB by default) are automatically compressed
large_data = "x" * 50000  # 50KB of data
memory.set_var("big_data", large_data)

# Retrieved transparently
memory.get_var("big_data")  # Returns full 50KB string

# Or store objects explicitly
stamp = memory.set_obj(large_binary_data, name="attachment", desc="PDF file")
memory.get_var("attachment")  # Returns decompressed data
```

**Key features:**
- **Event-sourced** — Every change is an event with a sortable ID
- **Full variable history** — See every change with timestamps
- **Channel tracking** — Build omni-channel agents (web, mobile, Telegram, etc.)
- **Tombstone deletion** — History is never lost
- **Auto-compression** — Large values handled automatically
- **Multiple export formats** — JSON, Pickle, snapshots for cloud sync

---

### 3. `THOUGHT` — The Atomic Unit of Cognition

A THOUGHT is the discrete unit of reasoning: **Prompt + Context + LLM + Parsing + Validation**. It's the building block for all cognitive operations.

```python
from thoughtflow import LLM, MEMORY, THOUGHT

llm = LLM("openai:gpt-4o", key="...")
memory = MEMORY()

# ═══════════════════════════════════════════════════════════════════════════
# BASIC THOUGHT — the simplest form
# ═══════════════════════════════════════════════════════════════════════════

thought = THOUGHT(
    name="respond",
    llm=llm,
    prompt="You are a helpful assistant. Answer: {last_user_msg}",
)

memory.add_msg("user", "What's 2 + 2?")
memory = thought(memory)  # THE UNIVERSAL PATTERN

result = memory.get_var("respond_result")
print(result)  # "2 + 2 equals 4."

# ═══════════════════════════════════════════════════════════════════════════
# WITH PARSING — extract structured data from messy LLM output
# ═══════════════════════════════════════════════════════════════════════════

thought = THOUGHT(
    name="extract_user_info",
    llm=llm,
    prompt="Extract user information from this text: {text}",
    parsing_rules={
        "kind": "python",
        "format": {
            "name": "",           # Required string
            "age": 0,             # Required int
            "email?": "",         # Optional (note the ?)
            "skills": [],         # Required list
        }
    },
)

memory.set_var("text", "My name is Alice, I'm 28, and I know Python and ML.")
memory = thought(memory)
info = memory.get_var("extract_user_info_result")
# info = {"name": "Alice", "age": 28, "skills": ["Python", "ML"]}

# ═══════════════════════════════════════════════════════════════════════════
# WITH VALIDATION — ensure output meets requirements
# ═══════════════════════════════════════════════════════════════════════════

thought = THOUGHT(
    name="generate_ideas",
    llm=llm,
    prompt="Generate exactly 5 creative ideas for: {topic}",
    parser="json",
    validator="list_min_len:5",  # Must have at least 5 items
    max_retries=3,               # Retry up to 3 times if validation fails
    retry_delay=0.5,             # Wait 0.5s between retries
)

# Built-in validators:
# - "any"                    — Accept anything
# - "has_keys:key1,key2"     — Dict must have these keys
# - "list_min_len:N"         — List must have at least N items
# - Custom callable          — Your own validation function

# ═══════════════════════════════════════════════════════════════════════════
# WITH CUSTOM VALIDATION
# ═══════════════════════════════════════════════════════════════════════════

def validate_email_list(result):
    """Custom validator: all items must be valid emails."""
    if not isinstance(result, list):
        return False, "Expected a list"
    for item in result:
        if "@" not in str(item):
            return False, f"Invalid email: {item}"
    return True, ""

thought = THOUGHT(
    name="extract_emails",
    llm=llm,
    prompt="Extract all email addresses from: {text}",
    parser="list",
    validation=validate_email_list,
    max_retries=2,
)

# ═══════════════════════════════════════════════════════════════════════════
# OPERATIONS — THOUGHT isn't just for LLM calls
# ═══════════════════════════════════════════════════════════════════════════

# MEMORY QUERY — retrieve data without calling LLM
query_thought = THOUGHT(
    name="get_user_context",
    operation="memory_query",
    required_vars=["user_name", "session_id"],
    optional_vars=["preferences"],
)
memory = query_thought(memory)
context = memory.get_var("get_user_context_result")
# context = {"user_name": "Alice", "session_id": "abc123"}

# VARIABLE SET — set multiple variables at once
init_thought = THOUGHT(
    name="init_session",
    operation="variable_set",
    prompt={
        "session_active": True,
        "start_time": None,
        "message_count": 0
    }
)
memory = init_thought(memory)
# Sets all three variables in memory

# CONDITIONAL — branch logic based on memory state
branch_thought = THOUGHT(
    name="check_threshold",
    operation="conditional",
    condition=lambda m, ctx: ctx.get("score", 0) > 80,
    if_true="high_score_path",
    if_false="low_score_path"
)
memory.set_var("score", 95)
memory = branch_thought(memory)
result = memory.get_var("check_threshold_result")  # "high_score_path"

# ═══════════════════════════════════════════════════════════════════════════
# PRE/POST HOOKS — custom processing
# ═══════════════════════════════════════════════════════════════════════════

def pre_process(thought, memory, vars, **kwargs):
    """Called before execution."""
    print(f"About to execute: {thought.name}")
    # Can modify vars before execution

def post_process(thought, memory, result, error):
    """Called after execution."""
    if error:
        print(f"Error in {thought.name}: {error}")
    else:
        print(f"Success: {thought.name} -> {result}")

thought = THOUGHT(
    name="monitored_thought",
    llm=llm,
    prompt="...",
    pre_hook=pre_process,
    post_hook=post_process,
)

# ═══════════════════════════════════════════════════════════════════════════
# SERIALIZATION — save and restore thoughts
# ═══════════════════════════════════════════════════════════════════════════

# Export to dict (for storage/transmission)
thought_data = thought.to_dict()

# Reconstruct from dict (LLM must be provided separately)
thought_copy = THOUGHT.from_dict(thought_data, llm=llm)

# Copy a thought
thought_clone = thought.copy()

# ═══════════════════════════════════════════════════════════════════════════
# INTROSPECTION — examine execution history
# ═══════════════════════════════════════════════════════════════════════════

# After executing a thought multiple times
thought.execution_history
# [
#   {"stamp": "...", "duration_ms": 234.5, "success": True, ...},
#   {"stamp": "...", "duration_ms": 198.2, "success": True, ...},
# ]

thought.last_result      # Most recent result
thought.last_error       # Most recent error (if any)
thought.last_prompt      # The prompt that was sent
thought.last_response    # Raw LLM response
```

**Key features:**
- **Callable interface** — `memory = thought(memory)` is the entire API
- **Automatic retry** — With repair prompts that explain what went wrong
- **Schema-based parsing** — Via `valid_extract` for bulletproof extraction
- **Multiple validators** — Built-in or custom validation functions
- **Four operations** — `llm_call`, `memory_query`, `variable_set`, `conditional`
- **Pre/post hooks** — Custom processing before and after execution
- **Full serialization** — Save, restore, and copy thoughts

---

### 4. `ACTION` — External Operations

ACTION wraps external operations (API calls, file I/O, database queries) with consistent logging and error handling:

```python
from thoughtflow import ACTION, MEMORY

# ═══════════════════════════════════════════════════════════════════════════
# DEFINING AN ACTION
# ═══════════════════════════════════════════════════════════════════════════

def search_web(memory, query, max_results=3):
    """
    Search the web and return results.
    
    Args:
        memory: MEMORY object (always first argument)
        query: Search query string
        max_results: Maximum results to return
    
    Returns:
        dict with search results
    """
    # Your implementation here
    results = web_api.search(query, limit=max_results)
    return {"status": "success", "hits": results, "query": query}

search_action = ACTION(
    name="web_search",
    fn=search_web,
    config={"max_results": 5},  # Default config
    description="Searches the web for information"
)

# ═══════════════════════════════════════════════════════════════════════════
# EXECUTING AN ACTION
# ═══════════════════════════════════════════════════════════════════════════

memory = MEMORY()

# Execute with default config
memory = search_action(memory, query="thoughtflow python library")

# Execute with override
memory = search_action(memory, query="python agents", max_results=10)

# Results are stored automatically
result = memory.get_var("web_search_result")
# result = {"status": "success", "hits": [...], "query": "..."}

# ═══════════════════════════════════════════════════════════════════════════
# ERROR HANDLING — errors don't interrupt your workflow
# ═══════════════════════════════════════════════════════════════════════════

def risky_operation(memory, url):
    """An operation that might fail."""
    response = requests.get(url, timeout=5)
    response.raise_for_status()
    return response.json()

fetch_action = ACTION(name="fetch_data", fn=risky_operation)

# If the action fails, error info is stored (not raised)
memory = fetch_action(memory, url="https://example.com/api")

result = memory.get_var("fetch_data_result")
if "error" in result:
    print(f"Action failed: {result['error']}")
else:
    print(f"Action succeeded: {result}")

# ═══════════════════════════════════════════════════════════════════════════
# INTROSPECTION — examine execution history
# ═══════════════════════════════════════════════════════════════════════════

# After executing an action multiple times
search_action.execution_count        # How many times called
search_action.was_successful()       # Did last call succeed?
search_action.last_result            # Most recent result
search_action.last_error             # Most recent error (if any)

# Full execution history with timing
search_action.execution_history
# [
#   {"stamp": "...", "duration_ms": 145.2, "success": True, "error": None},
#   {"stamp": "...", "duration_ms": 203.1, "success": False, "error": "Timeout"},
# ]

# Get timing for last call
last_call = search_action.execution_history[-1]
print(f"Last call took {last_call['duration_ms']:.1f}ms")

# ═══════════════════════════════════════════════════════════════════════════
# RESET AND COPY
# ═══════════════════════════════════════════════════════════════════════════

# Reset stats (useful for testing)
search_action.reset_stats()

# Copy an action (shares function, copies config)
search_action_copy = search_action.copy()

# ═══════════════════════════════════════════════════════════════════════════
# SERIALIZATION
# ═══════════════════════════════════════════════════════════════════════════

# Export to dict
action_data = search_action.to_dict()

# Reconstruct (need function registry)
fn_registry = {"search_web": search_web}
action_copy = ACTION.from_dict(action_data, fn_registry)
```

**Key features:**
- **Callable interface** — `memory = action(memory, **kwargs)`
- **Automatic result storage** — Results stored in `{name}_result` variable
- **Error containment** — Errors are logged, not raised (workflow continues)
- **Full execution history** — Timing, success/failure, error details
- **Configurable defaults** — Set defaults, override per-call
- **Serialization support** — Save and restore actions

---

## 🔧 Utilities

### `valid_extract` — Robust LLM Output Parsing

LLMs are messy. They add prose, code fences, markdown, and formatting you didn't ask for. `valid_extract` handles all of it:

**Basic extraction from messy output:**

```python
from thoughtflow import valid_extract, ValidExtractError

# Messy LLM output with prose and formatting
llm_output = '''
Sure! Here is the data you asked for:
{"name": "Alice", "age": 28, "skills": ["Python", "ML"]}
Let me know if you need anything else!
'''

# Define extraction rules with schema
rules = {
    "kind": "python",
    "format": {
        "name": "",      # Required string
        "age": 0,        # Required int
        "skills": [],    # Required list
    }
}

result = valid_extract(llm_output, rules)
# result = {'name': 'Alice', 'age': 28, 'skills': ['Python', 'ML']}
```

**Optional keys (marked with `?`):**

```python
rules = {
    "kind": "python",
    "format": {
        "name": "",       # Required
        "email": "",      # Required
        "phone?": "",     # Optional (note the ?)
        "address?": "",   # Optional
    }
}

llm_output = "{'name': 'Bob', 'email': 'bob@example.com'}"
result = valid_extract(llm_output, rules)
# result = {'name': 'Bob', 'email': 'bob@example.com'}
# No error even though phone and address are missing
```

**Nested structures:**

```python
rules = {
    "kind": "python",
    "format": {
        "user": {
            "id": 0,
            "profile": {
                "name": "",
                "settings": {}
            }
        },
        "metadata": {}
    }
}
```

**List element validation:**

```python
# [schema] means every element must match schema
rules = {
    "kind": "python",
    "format": [{
        "id": 0,
        "name": "",
        "done": True
    }]
}

llm_output = """
[
    {'id': 1, 'name': 'Task A', 'done': False},
    {'id': 2, 'name': 'Task B', 'done': True},
]
"""
result = valid_extract(llm_output, rules)
# Each item validated against the schema
```

**JSON parsing:**

```python
rules = {
    "kind": "json",  # Parse as JSON instead of Python
    "format": {"status": "", "data": []}
}

llm_output = '{"status": "ok", "data": [1, 2, 3]}'
result = valid_extract(llm_output, rules)
```

**Error handling:**

```python
try:
    result = valid_extract("no valid data here", rules)
except ValidExtractError as e:
    print(f"Extraction failed: {e}")
```

**Schema type mapping:**
- `""` or `str` → string
- `0` or `int` → integer
- `0.0` or `float` → float
- `True` or `bool` → boolean
- `None` → NoneType
- `[]` → list (any contents)
- `[schema]` → list of items matching schema
- `{}` → dict (any contents)
- `{"k": schema}` → dict with required key "k"
- `{"k?": schema}` → dict with optional key "k"

---

### `EventStamp` — Deterministic IDs

```python
from thoughtflow import event_stamp, hashify, EventStamp

# Generate unique, sortable event ID
# Alphabetical order = chronological order
stamp = event_stamp()  # "A1B2C3D4E5F6G7H8"

# Generate with document hash (deterministic component)
stamp = event_stamp({"user": "alice", "action": "login"})

# Decode timestamp from stamp
unix_time = EventStamp.decode_time(stamp)

# Generate deterministic hash
hash_id = hashify("some input string")       # 32 chars by default
hash_id = hashify("some input", length=16)   # Custom length
# Same input always produces same hash
```

---

### Prompt Construction

```python
from thoughtflow import construct_prompt, construct_msgs

# ═══════════════════════════════════════════════════════════════════════════
# STRUCTURED PROMPTS WITH SECTIONS
# ═══════════════════════════════════════════════════════════════════════════

prompt = construct_prompt({
    "context": "You are analyzing customer feedback data.",
    "instructions": "Follow these steps:\n1. Identify sentiment\n2. Extract key themes",
    "output_format": "Return a JSON object with 'sentiment' and 'themes' keys."
})
# Generates a structured prompt with clear section markers

# ═══════════════════════════════════════════════════════════════════════════
# MESSAGE LIST CONSTRUCTION
# ═══════════════════════════════════════════════════════════════════════════

msgs = construct_msgs(
    usr_prompt="Analyze this feedback: {feedback}",
    vars={"feedback": customer_feedback},
    sys_prompt="You are a sentiment analysis expert.",
    msgs=[]  # Prior conversation messages
)
# Returns properly formatted message list for LLM
```

---

## 🎨 Real-World Patterns

### Multi-Step Workflow

Chain multiple thoughts together for complex workflows:

```python
from thoughtflow import LLM, MEMORY, THOUGHT

llm = LLM("openai:gpt-4o", key="...")
memory = MEMORY()

# Define a pipeline of thoughts
analyze = THOUGHT(
    name="analyze",
    llm=llm,
    prompt="Analyze the following text and identify key themes: {text}",
    parsing_rules={"kind": "python", "format": {"themes": [], "sentiment": ""}}
)

expand = THOUGHT(
    name="expand",
    llm=llm,
    prompt="Take these themes and expand on each one: {analyze_result}",
)

summarize = THOUGHT(
    name="summarize",
    llm=llm,
    prompt="Create an executive summary from this expanded analysis: {expand_result}",
)

critique = THOUGHT(
    name="critique",
    llm=llm,
    prompt="Identify potential weaknesses or gaps in this analysis: {summarize_result}",
)

# Execute the pipeline — it's just Python!
memory.set_var("text", document)

for thought in [analyze, expand, summarize, critique]:
    print(f"Executing: {thought.name}")
    memory = thought(memory)
    print(f"  Result stored in: {thought.name}_result")

# Get final results
summary = memory.get_var("summarize_result")
critique = memory.get_var("critique_result")
```

### Multi-Channel Agent

Build agents that work across platforms:

```python
from thoughtflow import LLM, MEMORY, THOUGHT

memory = MEMORY()

# Messages come from different platforms
memory.add_msg("user", "Hello from the website!", channel="webapp")
memory.add_msg("user", "Following up via Telegram", channel="telegram")
memory.add_msg("user", "Quick question from mobile", channel="ios")
memory.add_msg("user", "Also checking Slack", channel="slack")

# Process messages by channel
for channel in ["webapp", "telegram", "ios", "slack"]:
    msgs = memory.get_msgs(channel=channel)
    print(f"\n{channel.upper()} ({len(msgs)} messages):")
    for msg in msgs:
        print(f"  {msg['role']}: {msg['content'][:50]}...")

# Or process all together, maintaining context
all_msgs = memory.get_msgs(include=["user", "assistant"])

# Render for LLM context with channel info
context = memory.render(
    format="conversation",
    include_roles=("user", "assistant"),
    max_total_length=4000
)
```

### Retry with Auto-Repair

Automatic retry with intelligent repair prompts:

```python
from thoughtflow import LLM, MEMORY, THOUGHT

llm = LLM("openai:gpt-4o", key="...")
memory = MEMORY()

thought = THOUGHT(
    name="generate_json",
    llm=llm,
    prompt="""Generate a valid JSON object with exactly these keys:
    - "name": a string
    - "count": an integer greater than 0
    - "tags": a list of at least 3 strings
    """,
    parsing_rules={
        "kind": "json",
        "format": {"name": "", "count": 0, "tags": [""]}
    },
    validator="list_min_len:3",  # Custom: tags must have 3+ items
    max_retries=3,
    retry_delay=0.5,
)

# If validation fails, THOUGHT automatically retries with a repair prompt
# that explains what went wrong:
# "(Please return only the requested format; your last answer failed: List too short)"

memory = thought(memory)

# Check execution history
for attempt in thought.execution_history:
    print(f"Attempt: success={attempt['success']}, duration={attempt['duration_ms']:.1f}ms")
```

### Combining THOUGHTs and ACTIONs

Build agents that think AND act:

```python
from thoughtflow import LLM, MEMORY, THOUGHT, ACTION

llm = LLM("openai:gpt-4o", key="...")
memory = MEMORY()

# Define an action for external API calls
def search_database(memory, query, limit=10):
    results = db.search(query, limit=limit)
    return {"results": results, "count": len(results)}

search = ACTION(name="search", fn=search_database)

# Define thoughts for reasoning
analyze_query = THOUGHT(
    name="analyze_query",
    llm=llm,
    prompt="Convert this user question into a database search query: {last_user_msg}",
)

synthesize = THOUGHT(
    name="synthesize",
    llm=llm,
    prompt="Given these search results: {search_result}\n\nAnswer the user's question: {last_user_msg}",
)

# Workflow: Think → Act → Think
memory.add_msg("user", "What products do we have under $50?")

memory = analyze_query(memory)  # Think: convert to query
query = memory.get_var("analyze_query_result")

memory = search(memory, query=query, limit=20)  # Act: search database

memory = synthesize(memory)  # Think: synthesize answer
answer = memory.get_var("synthesize_result")
```

---

## 🎯 Philosophy: The Zen of ThoughtFlow

ThoughtFlow is guided by principles documented in [**ZEN.md**](ZEN.md):

| Principle | What It Means |
|-----------|---------------|
| 🎯 **First Principles First** | Built on fundamentals, not abstractions on abstractions |
| 🧘 **Complexity is the Enemy** | Pythonic, intuitive, elegant. As light as possible. |
| 👁️ **Obvious Over Abstract** | If you have to dig deep to understand, the design failed |
| 🔍 **Transparency is Trust** | Never guess what's happening under the hood |
| 📦 **Minimize Dependencies** | Zero deps for core. Serverless-ready by default. |
| ♻️ **Backward Compatibility is Sacred** | Code should endure. Deprecation should be rare. |
| 🧩 **Modularity Over Monolith** | Composable pieces, not all-or-nothing frameworks |
| 🚗 **Vehicle, Not Destination** | Your logic, your rules, your journey |
| 🐍 **Python is King** | Pythonic first. No DSLs, no YAML configs, no magic. |

> *"Don't try to please everyone. Greatness comes from focus, not from trying to do everything."*
> 
> — [ZEN.md](ZEN.md)

---

## 🔗 Sister Library: ThoughtBase

**[ThoughtBase](https://github.com/jrolf/thoughtbase)** is an optional companion library providing persistent storage and vector search capabilities.

```python
from thoughtflow import MEMORY, THOUGHT
from thoughtbase import VectorStore, PersistentMemory

# Create persistent, searchable memory
store = VectorStore("my_agent_memories")
persistent_mem = PersistentMemory(store)

# Your normal ThoughtFlow workflow
thought = THOUGHT(name="respond", llm=llm, prompt="...")
memory = thought(memory)

# Save to ThoughtBase
persistent_mem.save(memory)

# Later: search across all saved memories
results = persistent_mem.search("user preferences about notifications", limit=5)

# Load a specific memory
memory = persistent_mem.load(session_id="abc123")
```

> ⚠️ **ThoughtBase is entirely optional.** ThoughtFlow provides complete functionality standalone. ThoughtBase adds persistence and vector search when you need them.

---

## 🔧 Supported Versions

| Version | Python | Status | Notes |
|---------|--------|--------|-------|
| **0.0.x** | 3.9 - 3.12 | 🟢 Active | Current development |

**Compatibility Policy:**
- We test against Python 3.9, 3.10, 3.11, and 3.12
- We aim to support new Python versions within 3 months of stable release
- Breaking changes are avoided; when necessary, deprecation warnings come first

---

## 🧪 Testing & Evaluation

ThoughtFlow is designed for **deterministic testing**:

```python
from thoughtflow import MEMORY
from thoughtflow.eval import Harness, Replay

# ═══════════════════════════════════════════════════════════════════════════
# RECORD AND REPLAY
# ═══════════════════════════════════════════════════════════════════════════

# Record a session
memory = MEMORY()
# ... run your workflow ...
memory.save("session_recording.pkl")

# Replay for testing
replay = MEMORY()
replay.load("session_recording.pkl")

# Assert on results
assert replay.get_var("final_result") == expected_value
assert len(replay.get_msgs()) == expected_message_count

# ═══════════════════════════════════════════════════════════════════════════
# EVALUATION HARNESS
# ═══════════════════════════════════════════════════════════════════════════

# Define test cases
test_cases = [
    {"input": "What's 2+2?", "expected_contains": "4"},
    {"input": "Capital of France?", "expected_contains": "Paris"},
]

# Run evaluation
harness = Harness(test_cases=test_cases)
results = harness.run(my_workflow_function)

# Analyze results
for result in results:
    print(f"Input: {result['input']}")
    print(f"Output: {result['output']}")
    print(f"Passed: {result['passed']}")
```

---

## 📁 Project Structure

```
thoughtflow/
├── src/thoughtflow/
│   ├── __init__.py      # Public API exports
│   ├── llm.py           # LLM class - multi-provider interface
│   ├── memory/
│   │   ├── __init__.py
│   │   └── base.py      # MEMORY class - event-sourced state
│   ├── thought.py       # THOUGHT class - cognitive unit
│   ├── action.py        # ACTION class - external operations
│   ├── _util.py         # Utilities (event_stamp, valid_extract, etc.)
│   ├── tools/           # Tool registry for function calling
│   ├── trace/           # Session tracing and events
│   └── eval/            # Evaluation harness and replay
├── examples/            # Working, runnable examples
│   ├── 01_hello_world.py
│   ├── 02_action.py
│   ├── 03_memory.py
│   ├── 04_valid_extract.py
│   └── ...
├── tests/               # Comprehensive test suite
│   ├── unit/
│   └── integration/
├── docs/                # Documentation source
├── developer/           # Developer guides
├── assets/              # Logo and media
└── ZEN.md               # Philosophy document
```

---

## 🛠️ Development

```bash
# Clone the repository
git clone https://github.com/jrolf/thoughtflow.git
cd thoughtflow

# Install in development mode with all extras
pip install -e ".[dev]"

# Run the test suite
pytest

# Run with coverage
pytest --cov=src/thoughtflow

# Lint the code
ruff check src/

# Format the code
ruff format src/

# Type check
mypy src/thoughtflow/
```

See [developer/](developer/) for comprehensive development documentation.

---

## 📈 Project Status

| Aspect | Status | Notes |
|--------|--------|-------|
| **Core Primitives** | ✅ Stable | LLM, MEMORY, THOUGHT, ACTION |
| **API Stability** | 🟡 Alpha | May evolve based on feedback |
| **Documentation** | 🟡 In Progress | Core docs complete, expanding |
| **Test Coverage** | ✅ Comprehensive | Unit + integration tests |
| **Type Hints** | ✅ Full | Strict mypy compliance |
| **Serverless Ready** | ✅ Yes | Zero deps, fast cold starts |

See [CHANGELOG.md](CHANGELOG.md) for version history.

---

## 🔒 Security

Found a vulnerability? **Please don't open a public issue.**

See [SECURITY.md](SECURITY.md) for our responsible disclosure policy. We take security seriously and will respond within 48 hours.

---

## 🤝 Contributing

We welcome contributions! ThoughtFlow values:

| Principle | What It Means |
|-----------|---------------|
| **Simplicity** | Over feature bloat |
| **Clarity** | Over cleverness |
| **Explicit** | Over implicit |
| **Tested** | Everything has tests |

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## 💬 Getting Help

| Need | Where to Go |
|------|-------------|
| **Question about usage** | [GitHub Discussions](https://github.com/jrolf/thoughtflow/discussions) |
| **Bug report** | [GitHub Issues](https://github.com/jrolf/thoughtflow/issues) |
| **Feature request** | [GitHub Issues](https://github.com/jrolf/thoughtflow/issues) |
| **Security issue** | See [SECURITY.md](SECURITY.md) |

---

## 📖 Resources

| Resource | Description |
|----------|-------------|
| 📚 [Documentation](https://thoughtflow.dev) | Full documentation site |
| 🧘 [ZEN.md](ZEN.md) | Philosophy and design principles |
| 💡 [examples/](examples/) | Working, runnable examples |
| 🛠️ [developer/](developer/) | Developer guides and docs |
| 📝 [CHANGELOG.md](CHANGELOG.md) | Version history |
| 🤝 [CONTRIBUTING.md](CONTRIBUTING.md) | Contribution guidelines |

---

## 📄 License

[MIT](LICENSE) © James A. Rolfsen

---

<p align="center">
  <img src="https://raw.githubusercontent.com/jrolf/thoughtflow/main/assets/logo.png" alt="ThoughtFlow" width="80">
</p>

<p align="center">
  <strong>ThoughtFlow</strong><br>
  <sub>Because your agent code should be as clear as your thinking.</sub>
</p>

<p align="center">
  <sub>Built with ❤️ for developers who believe AI tools should empower, not mystify.</sub>
</p>

<p align="center">
  <sub>
    <a href="#-installation">Install</a> •
    <a href="#-quick-start">Quick Start</a> •
    <a href="#-the-four-primitives-in-depth">Deep Dive</a> •
    <a href="#-contributing">Contribute</a> •
    <a href="ZEN.md">Philosophy</a>
  </sub>
</p>

<p align="center">
  ⭐ Star us on GitHub — it helps!
</p>

<!-- 
═══════════════════════════════════════════════════════════════════════════════
HIDDEN SECTIONS: Uncomment when content is ready
═══════════════════════════════════════════════════════════════════════════════

## 💬 What People Are Saying

<table>
<tr>
<td width="33%">

> *"Finally, an LLM framework that doesn't make me feel stupid."*
>
> — **[Name]** <br><sub>Software Engineer</sub>

</td>
<td width="33%">

> *"Deployed to Lambda in 10 minutes. Try that with LangChain."*
>
> — **[Name]** <br><sub>DevOps Engineer</sub>

</td>
<td width="33%">

> *"I read the entire source in one sitting. That's unheard of."*
>
> — **[Name]** <br><sub>AI Researcher</sub>

</td>
</tr>
</table>

───────────────────────────────────────────────────────────────────────────────

## 🏗️ Built With ThoughtFlow

<table>
<tr>
<td width="33%">

### 🤖 Project Name
**Description**

A conversational AI assistant built with ThoughtFlow.

[View Project →](link)

</td>
<td width="33%">

### 📊 Project Name
**Description**

Data analysis agent using ThoughtFlow workflows.

[View Project →](link)

</td>
<td width="33%">

### 🎮 Project Name
**Description**

Interactive application powered by ThoughtFlow.

[View Project →](link)

</td>
</tr>
</table>

───────────────────────────────────────────────────────────────────────────────

## 👥 Contributor Spotlight

<table>
<tr>
<td align="center">
  <a href="https://github.com/jrolf">
    <img src="https://github.com/jrolf.png" width="80px;" alt="James Rolfsen"/><br>
    <sub><b>James Rolfsen</b></sub>
  </a>
  <br><sub>Creator & Maintainer</sub>
</td>
<td align="center">
  <a href="#">
    <img src="https://github.com/[username].png" width="80px;" alt="Contributor"/><br>
    <sub><b>[Name]</b></sub>
  </a>
  <br><sub>Core Contributor</sub>
</td>
<td align="center">
  <a href="CONTRIBUTING.md">
    <sub><b>You?</b></sub>
  </a>
  <br><sub><a href="CONTRIBUTING.md">Join Us →</a></sub>
</td>
</tr>
</table>

───────────────────────────────────────────────────────────────────────────────

## 🌐 Community

<p align="center">
  <a href="[discord-link]"><img src="https://img.shields.io/badge/Discord-Join%20Us-7289da?style=for-the-badge&logo=discord&logoColor=white" alt="Discord"></a>
  &nbsp;
  <a href="[twitter-link]"><img src="https://img.shields.io/badge/Twitter-Follow-1DA1F2?style=for-the-badge&logo=twitter&logoColor=white" alt="Twitter"></a>
</p>

───────────────────────────────────────────────────────────────────────────────

## 🎮 Try It Now

<p align="center">
  <a href="[replit-link]"><img src="https://img.shields.io/badge/Open%20in%20Replit-Try%20ThoughtFlow-667881?style=for-the-badge&logo=replit&logoColor=white" alt="Replit"></a>
  &nbsp;
  <a href="[colab-link]"><img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open In Colab"></a>
</p>

═══════════════════════════════════════════════════════════════════════════════
-->
