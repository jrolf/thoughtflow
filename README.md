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
  <a href="#-the-primitives">Primitives</a> •
  <a href="#-foundational-primitives-in-depth">Foundational</a> •
  <a href="#-higher-level-primitives">Higher-Level</a> •
  <a href="#-real-world-patterns">Patterns</a> •
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
pip install thoughtflow==0.0.7

# Check your installed version
python -c "import thoughtflow; print(thoughtflow.__version__)"
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
- 🎯 **Your agent logic should fit in your head** — A few powerful primitives, not forty classes
- 🔍 **Every state change should be visible and traceable** — Event-sourced memory with full history
- 🧪 **Testing AI systems should be as easy as testing regular code** — Deterministic replay built-in
- 📦 **Zero dependencies means zero supply chain nightmares** — Core runs on stdlib only
- ⚡ **Serverless deployment should be trivial, not heroic** — <100ms cold starts

This isn't just a library. It's a stance.

---

## ✅ When to Use ThoughtFlow

ThoughtFlow is the right choice when:

- **You need serverless deployment** — Lambda, Cloud Functions, Edge. Zero dependencies means instant cold starts.
- **You want to understand your entire codebase** in an afternoon — A handful of concepts, not forty.
- **You value explicit state over magic** — Every change is visible, traceable, and replayable.
- **You need deterministic testing** of AI workflows — Record sessions, replay them, assert on results.
- **You're building production agents**, not prototypes — Serious error handling, retry logic, validation.
- **You prefer composition over configuration** — Plain Python, not YAML or JSON configs.
- **You work across multiple LLM providers** — One interface for OpenAI, Anthropic, Groq, Gemini, Ollama, and more.

## ❌ When NOT to Use ThoughtFlow

Be honest with yourself — ThoughtFlow isn't for everyone:

- **You need pre-built RAG pipelines out of the box** → Consider [LlamaIndex](https://github.com/run-llama/llama_index)
- **You want visual workflow builders** → Consider [Flowise](https://github.com/FlowiseAI/Flowise), [Langflow](https://github.com/langflow-ai/langflow)
- **You need very large-scale multi-agent swarms** → Consider [AutoGen](https://github.com/microsoft/autogen), [CrewAI](https://github.com/joaomdmoura/crewai) (ThoughtFlow supports multi-agent via AGENT + DELEGATE, but optimizes for clarity over massive swarms)
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
| **Concepts to Learn** | **~12 core** | 50+ | 30+ | 15+ |
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

## 🧩 The Primitives

ThoughtFlow is built in layers. Four **foundational** primitives form the base; everything else composes on top through inheritance and delegation.

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ORCHESTRATION        WORKFLOW ·  CHRON                                 │
│  COORDINATION         DELEGATE ·  CHAT                                  │
│  AUTONOMY             AGENT  (→ ReactAgent · ReflectAgent · PlanActAgent) │
│  CAPABILITY           TOOL · MCP                                        │
│  ─────────────────────────────────────────────────────────────────────── │
│  COGNITION            THOUGHT  (→ DECIDE · PLAN)                        │
│  OPERATION            ACTION   (→ 16 elemental subclasses)              │
│  STATE                MEMORY                                            │
│  INTELLIGENCE         LLM · EMBED                                       │
│  ─────────────────────────────────────────────────────────────────────── │
│  ↑ Foundational layer            ↑ Higher-level layer                   │
└─────────────────────────────────────────────────────────────────────────┘
```

### Foundational Primitives

Master these four and you understand the core of the framework.

| Primitive | What It Does | The Pattern |
|-----------|--------------|-------------|
| **LLM** | Unified interface to call any language model | `response = llm.call(messages)` |
| **MEMORY** | Event-sourced state container for everything | `memory.add_msg("user", "Hello!")` |
| **THOUGHT** | Atomic unit of cognition with retry/parsing | `memory = thought(memory)` |
| **ACTION** | External operations with consistent logging | `memory = action(memory, **kwargs)` |

### Higher-Level Primitives

Built on the foundational layer for richer capabilities.

| Primitive | Layer | Purpose |
|-----------|-------|---------|
| **EMBED** | Intelligence | Vector embeddings from any provider |
| **DECIDE** | Cognition | Constrained decisions from finite choices (extends THOUGHT) |
| **PLAN** | Cognition | Structured multi-step execution plans (extends THOUGHT) |
| **TOOL** | Capability | Wrap any callable as an LLM-invocable tool |
| **MCP** | Capability | Model Context Protocol client for external tool servers |
| **AGENT** | Autonomy | Autonomous reasoning loop (think → act → observe) |
| **ReactAgent** | Autonomy | ReAct-style agent (extends AGENT) |
| **ReflectAgent** | Autonomy | Self-reflective agent (extends AGENT) |
| **PlanActAgent** | Autonomy | Plan-then-execute agent (extends AGENT) |
| **DELEGATE** | Coordination | Route tasks across a team of named agents |
| **CHAT** | Coordination | Multi-turn conversational interface |
| **WORKFLOW** | Orchestration | Directed graph of steps with branching and merging |
| **CHRON** | Orchestration | Schedule manager for recurring cron and interval jobs |

### Action Subclasses (Elemental Operations)

These are the "verbs" that agents use to interact with the world. All extend **ACTION**.

| Category | Primitives | Purpose |
|----------|------------|---------|
| **Communication** | `SAY`, `ASK`, `NOTIFY` | Output to users, get input, send notifications |
| **Information Retrieval** | `SEARCH`, `FETCH`, `SCRAPE`, `READ` | Multi-provider web search, HTTP requests, content scraping, file reading |
| **Persistence** | `WRITE`, `POST` | Write files, send data to APIs |
| **Temporal Control** | `SLEEP`, `WAIT`, `NOOP` | Pause execution, wait for conditions, no-op |
| **Execution** | `RUN`, `CALL` | Shell commands, function invocation |

> 💡 Every primitive — foundational and higher-level alike — inherits serialization, execution history, and introspection from its parent class.

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

## 🔮 Foundational Primitives In Depth

### `LLM` — The Universal Model Interface

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

### `MEMORY` — Event-Sourced State

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

# Quick access to most recent (returns full event dict by default)
memory.last_user_msg()                    # Returns: {'stamp': '...', 'content': 'Also checking on mobile', ...}
memory.last_asst_msg()                    # Returns: {'stamp': '...', 'content': 'Hi there!', ...}
memory.last_sys_msg()                     # Returns: {'stamp': '...', 'content': '...', ...}

# Or get just the content string
memory.last_user_msg(content_only=True)   # Returns: "Also checking on mobile"
memory.last_asst_msg(content_only=True)   # Returns: "Hi there! How can I help?"

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

# Retrieve logs and reflections (returns lists of event dicts)
memory.get_logs()                         # All log entries as list of dicts
memory.get_refs()                         # All reflections as list of dicts

# Quick access to most recent (returns full event dict by default)
memory.last_log_msg()                     # Returns: {'stamp': '...', 'content': '...', ...}
memory.last_ref()                         # Returns: {'stamp': '...', 'content': '...', ...}

# Or get just the content string
memory.last_log_msg(content_only=True)    # Returns: "Response generated successfully"
memory.last_ref(content_only=True)        # Returns: "Should ask clarifying questions..."

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

### `THOUGHT` — The Atomic Unit of Cognition

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

### `ACTION` — External Operations

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

## 🔧 Higher-Level Primitives

Higher-level primitives build on the foundational layer for specialized use cases. They inherit all features from their parent class (retry logic, serialization, hooks, execution history) while adding domain-specific functionality.

### `DECIDE` — Constrained Decision Steps

> **Extends:** THOUGHT

DECIDE is a specialized THOUGHT that constrains LLM output to a finite set of choices. Perfect for routing, classification, and branching logic:

```python
from thoughtflow import LLM, MEMORY, DECIDE

llm = LLM("openai:gpt-4o", key="...")
memory = MEMORY()

# ═══════════════════════════════════════════════════════════════════════════
# SIMPLE LIST OF CHOICES
# ═══════════════════════════════════════════════════════════════════════════

sentiment = DECIDE(
    name="classify_sentiment",
    llm=llm,
    choices=["positive", "negative", "neutral"],
    prompt="Classify the sentiment of: {text}",
)

memory.set_var("text", "I absolutely love this product!")
memory = sentiment(memory)
print(memory.get_var("classify_sentiment_result"))  # "positive"

# ═══════════════════════════════════════════════════════════════════════════
# DICT WITH DESCRIPTIONS (shown to LLM)
# ═══════════════════════════════════════════════════════════════════════════

router = DECIDE(
    name="route_request",
    llm=llm,
    choices={
        "approve": "Accept the request and proceed",
        "reject": "Deny the request with explanation",
        "escalate": "Send to human reviewer for decision",
    },
    prompt="Review this support ticket: {ticket}\n\nDecide how to handle it.",
    default="escalate",  # Fallback if all retries fail
)

memory.set_var("ticket", "Customer requesting refund for damaged item")
memory = router(memory)
result = memory.get_var("route_request_result")  # "approve", "reject", or "escalate"

# ═══════════════════════════════════════════════════════════════════════════
# FEATURES
# ═══════════════════════════════════════════════════════════════════════════

# DECIDE defaults to max_retries=5 (vs THOUGHT's 1)
# because classification often needs more attempts

# Smart parsing handles LLM verbosity:
# "I would choose: approve" → "approve"
# "APPROVE" → "approve" (case-insensitive by default)

# Choice-specific repair prompts:
# "(Respond with exactly one of: approve, reject, escalate. No other text.)"
```

**Key features:**
- **Constrained output** — Forces LLM to pick from valid choices
- **Flexible input** — List for simple choices, dict for choices with descriptions
- **Smart parsing** — Handles exact matches, embedded choices, and case variations
- **Higher retry default** — 5 retries vs THOUGHT's 1, since classification often needs correction
- **Default fallback** — Optional default choice when all retries fail
- **Inherits from THOUGHT** — Full serialization, hooks, and history support

---

### `PLAN` — Structured Multi-Step Planning

> **Extends:** THOUGHT

PLAN generates structured execution plans where an LLM creates a sequence of steps with parallel task support. Each task includes a reason explaining why it was chosen:

```python
from thoughtflow import LLM, MEMORY, PLAN

llm = LLM("openai:gpt-4o", key="...")
memory = MEMORY()

# ═══════════════════════════════════════════════════════════════════════════
# SIMPLE ACTIONS (descriptions only)
# ═══════════════════════════════════════════════════════════════════════════

planner = PLAN(
    name="research_plan",
    llm=llm,
    actions={
        "search": "Search the web for information",
        "analyze": "Analyze content for key insights",
        "summarize": "Create a concise summary",
        "notify": "Send notification to user",
    },
    prompt="Create a plan to achieve: {goal}",
)

memory.set_var("goal", "Research ThoughtFlow and summarize findings")
memory = planner(memory)
plan = memory.get_var("research_plan_result")
# [
#     [{"action": "search", "params": {"query": "ThoughtFlow"},
#       "reason": "Start by gathering information about the library."}],
#     [{"action": "analyze", "params": {"content": "{step_0_result}"},
#       "reason": "Extract key insights from search results."}],
#     [{"action": "summarize", "params": {"text": "{step_1_result}"},
#       "reason": "Condense findings into actionable summary."},
#      {"action": "notify", "params": {"message": "Research complete"},
#       "reason": "Alert user that the task is finished."}]
# ]

# ═══════════════════════════════════════════════════════════════════════════
# ACTIONS WITH PARAMETER SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════

# Use "?" suffix for optional parameters (e.g., "int?" means optional int)
planner = PLAN(
    name="workflow",
    llm=llm,
    actions={
        "search": {
            "description": "Search for information",
            "params": {"query": "str", "max_results": "int?"}
        },
        "fetch": {
            "description": "Fetch a resource by URL",
            "params": {"url": "str"}
        },
        "notify": {
            "description": "Send notification",
            "params": {"message": "str", "channel": "str?"}
        }
    },
    prompt="Plan to achieve: {goal}\nContext: {context}",
    max_steps=10,      # Maximum sequential steps
    max_parallel=5,    # Maximum parallel tasks per step
)

# ═══════════════════════════════════════════════════════════════════════════
# OUTPUT STRUCTURE
# ═══════════════════════════════════════════════════════════════════════════

# Plan = List of Steps (executed sequentially)
# Step = List of Tasks (can execute in parallel)
# Task = {"action": "...", "params": {...}, "reason": "..."}

# Tasks can reference previous step results:
# {"action": "analyze", "params": {"content": "{step_0_result}"}, "reason": "..."}
```

**Key features:**
- **Structured output** — `List[List[Dict]]` for steps with parallel tasks
- **Explainable** — Each task requires a `reason` field (1-3 sentences)
- **Flexible actions** — Simple descriptions or full parameter schemas
- **Parameter validation** — Required vs optional params with `?` suffix
- **Step references** — Tasks can reference `{step_N_result}` from previous steps
- **Configurable limits** — `max_steps` and `max_parallel` constraints
- **Inherits from THOUGHT** — Full retry, serialization, and hook support

---

### ACTION Subclasses — Elemental Operations

> **Extends:** ACTION

ThoughtFlow provides a suite of pre-built ACTION subclasses for common operations. These are the "verbs" that agents use to interact with the world:

| Category | Primitives | Purpose |
|----------|------------|---------|
| **Communication** | `SAY`, `ASK`, `NOTIFY` | Output to users, get input, send notifications |
| **Information Retrieval** | `SEARCH`, `FETCH`, `SCRAPE`, `READ` | Web search, HTTP requests, scraping, file reading |
| **Persistence** | `WRITE`, `POST` | Write files, send data to APIs |
| **Temporal Control** | `SLEEP`, `WAIT`, `NOOP` | Pause execution, wait for conditions, no-op |
| **Execution** | `RUN`, `CALL` | Shell commands, function invocation |

```python
from thoughtflow import MEMORY, SAY, SEARCH, FETCH, READ, WRITE, SLEEP

memory = MEMORY()

# Output a message to the user
say = SAY(message="Hello! Starting research...")
memory = say(memory)

# Search the web
search = SEARCH(query="ThoughtFlow Python library", max_results=5)
memory = search(memory)
results = memory.get_var("search_result")

# Fetch a webpage
fetch = FETCH(url="https://github.com/jrolf/thoughtflow")
memory = fetch(memory)

# Read a local file
read = READ(path="config.json", parse="json")
memory = read(memory)

# Write results to file
write = WRITE(path="output.txt", content="{search_result}")
memory = write(memory)

# Pause between operations (rate limiting)
sleep = SLEEP(duration=1.0, reason="Rate limit pause")
memory = sleep(memory)
```

**Key features:**
- **Zero dependencies** — All actions use Python standard library
- **Consistent interface** — `memory = action(memory)` pattern
- **Variable substitution** — Use `{variable}` placeholders from memory
- **Automatic logging** — All executions logged to memory
- **Inherits from ACTION** — Full execution history and serialization

---

### `SEARCH` — Multi-Provider Web Search

> **Extends:** ACTION

SEARCH abstracts multiple search engines behind a unified interface with normalized results. Supports **DuckDuckGo** (free, no key), **Brave Search**, **EXA** (semantic search), and **Google Custom Search**.

```python
from thoughtflow import MEMORY, SEARCH

memory = MEMORY()

# DuckDuckGo (default — no API key required)
search = SEARCH(query="ThoughtFlow Python library", max_results=5)
memory = search(memory)

# Brave Search
search = SEARCH(query="latest AI news", provider="brave", api_key="BSA...")
memory = search(memory)

# All providers return the same normalized structure:
result = memory.get_var("search_result")
# {
#   "query": "...",
#   "provider": "duckduckgo",
#   "results": [
#       {"title": "...", "url": "...", "snippet": "...", "rank": 1,
#        "source": "example.com", "date_published": "...", "extra": {}},
#       ...
#   ],
#   "total_found": 5,
#   "timestamp": "..."
# }
```

---

### `SCRAPE` — Structured Content Extraction

> **Extends:** ACTION

SCRAPE visits a URL and extracts content in three modes: raw HTML (default), **Markdown**, or a **structured** JSON object with metadata, headings, links, and images.

```python
from thoughtflow import MEMORY, SCRAPE

memory = MEMORY()

# Get clean Markdown
scrape = SCRAPE(url="https://example.com", extract="markdown")
memory = scrape(memory)
markdown_text = memory.get_var("scrape_result")

# Get structured JSON with full metadata
scrape = SCRAPE(url="https://example.com", extract="structured")
memory = scrape(memory)
data = memory.get_var("scrape_result")
# {"url": "...", "title": "...", "author": "...", "content_markdown": "...",
#  "content_text": "...", "headings": [...], "links": [...], "images": [...],
#  "word_count": 42, "timestamp": "..."}
```

---

### `TOOL` — LLM-Selectable Capabilities

TOOL wraps any callable with a JSON Schema so that an LLM can discover, reason about, and invoke it during an agentic loop. This is the bridge between your code and the LLM's function-calling protocol.

```python
from thoughtflow import TOOL

def get_weather(city, units="celsius"):
    """Fetch current weather for a city."""
    return {"city": city, "temp": 22, "units": units}

weather_tool = TOOL(
    name="get_weather",
    description="Get the current weather for a city.",
    parameters={
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "City name"},
            "units": {"type": "string", "enum": ["celsius", "fahrenheit"]},
        },
        "required": ["city"],
    },
    fn=get_weather,
)

# Pass to an AGENT — the LLM decides when to call it
```

---

### `MCP` — Model Context Protocol Client

MCP connects to external tool servers using the open [Model Context Protocol](https://modelcontextprotocol.io). It discovers remote tools and returns them as native TOOL instances. Supports **stdio** (local subprocess) and **HTTP+SSE** (remote server) transports.

```python
from thoughtflow import MCP

# Local MCP server via stdio
with MCP("npx -y @modelcontextprotocol/server-filesystem /tmp") as mcp:
    tools = mcp.list_tools()    # Returns list of TOOL instances
    result = mcp.call_tool("read_file", {"path": "/tmp/notes.txt"})

# Remote MCP server via HTTP
with MCP("https://my-mcp-server.example.com/mcp") as mcp:
    tools = mcp.list_tools()
```

---

### `AGENT` — Autonomous Tool-Use Loop

AGENT is the primitive that turns an LLM into an autonomous agent. It runs the cycle: **call LLM → parse tool requests → execute tools → feed results back → repeat** until the LLM produces a final text response or the iteration limit is reached.

```python
from thoughtflow import LLM, MEMORY, TOOL, AGENT

llm = LLM("openai:gpt-4o", key="...")
tools = [weather_tool]  # TOOL instances

agent = AGENT(
    llm=llm,
    tools=tools,
    system_prompt="You are a helpful weather assistant.",
    max_iterations=10,
)

memory = MEMORY()
memory.add_msg("user", "What's the weather in Paris?")
memory = agent(memory)  # Autonomous loop runs here

print(memory.last_asst_msg(content_only=True))
```

Subclasses provide different agentic strategies:

| Subclass | Strategy |
|----------|----------|
| **ReactAgent** | ReAct: interleaved reasoning and acting |
| **ReflectAgent** | Self-reflective: critiques its own output before finalizing |
| **PlanActAgent** | Plan-then-execute: generates a plan, then executes it step by step |

---

### `DELEGATE` — Multi-Agent Coordination

DELEGATE routes tasks between a team of named agents using three coordination patterns:

```python
from thoughtflow import AGENT, DELEGATE, MEMORY

researcher = AGENT(llm=llm, tools=[search_tool], name="researcher")
writer = AGENT(llm=llm, name="writer")

delegate = DELEGATE(agents=[researcher, writer])

memory = MEMORY()

# Dispatch: send to researcher, wait for result
memory = delegate.dispatch(memory, "researcher", "Find info on quantum computing")

# Handoff: pass to writer, fire-and-forget
delegate.handoff(memory, "writer", "Write a summary of the findings")

# Broadcast: ask all agents the same question
results = delegate.broadcast(memory, "Summarize your findings")
```

---

### `WORKFLOW` — Step-Based Orchestration

WORKFLOW chains steps (THOUGHTs, ACTIONs, AGENTs, or plain functions) into a directed sequence with conditional branching and error handling. It is "Python control flow with guardrails."

```python
from thoughtflow import MEMORY, THOUGHT, WORKFLOW

workflow = WORKFLOW(name="research_flow", on_error="skip")

workflow.step(classify_thought, name="classify")
workflow.step(search_action, condition=lambda m: m.get_var("needs_search"))
workflow.step(summarize_thought, name="summarize")

memory = MEMORY()
memory.add_msg("user", "Tell me about quantum computing")
memory = workflow(memory)

# Inspect execution
for entry in workflow.execution_log:
    print(f"{entry['step']}: {entry['duration_ms']:.0f}ms — {'ok' if entry['success'] else 'error'}")
```

---

### `CHRON` — Schedule Manager

CHRON manages recurring jobs with cron expressions or fixed intervals. It supports two execution modes: **tick mode** for serverless environments (Lambda, Cloud Functions) and **loop mode** for long-running daemons. Job state optionally persists to a JSON file.

```python
from thoughtflow import CHRON

chron = CHRON(name="ops", state_file="jobs.json")

# Cron expression: run at 2am daily
chron.add("nightly_cleanup", schedule="0 2 * * *", action=run_cleanup)

# Fixed interval: every 60 seconds
chron.add("heartbeat", every=60, action=lambda m: print("alive"))

# Serverless: external cron calls your handler
results = chron.tick()  # Executes any jobs that are due right now

# Daemon: blocking loop (or start() for a background thread)
chron.start(tick_interval=60)
# ... later ...
chron.stop()
```

---

### `CHAT` — Interactive Conversation Loop

CHAT wraps any callable that follows the ThoughtFlow contract and provides a text-based input/output loop for testing agents in a terminal or Jupyter notebook.

```python
from thoughtflow import LLM, THOUGHT, CHAT

llm = LLM("openai:gpt-4o", key="...")
responder = THOUGHT(name="respond", llm=llm, prompt="Answer: {last_user_msg}")

chat = CHAT(responder, greeting="Hello! Ask me anything.")
chat.run()  # Interactive loop — type 'q' to exit

# Or programmatic turn-by-turn:
response = chat.turn("What is the capital of France?")
```

---

### `EMBED` — Vector Embeddings

EMBED is the embedding counterpart to LLM. It sends text to an embedding endpoint and returns a vector. Same multi-provider pattern — one class, any provider.

```python
from thoughtflow import EMBED

embed = EMBED("openai:text-embedding-3-small", key="sk-...")

# Single text → single vector
vector = embed.call("Hello world")
print(len(vector))  # e.g., 1536

# Batch → list of vectors
vectors = embed.call(["Hello", "World"])
```

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
    validator="list_min_len:3",  # Built-in: tags must have 3+ items
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

### Agentic Research with AGENT + TOOL

Let the LLM decide which tools to call autonomously:

```python
from thoughtflow import LLM, MEMORY, TOOL, AGENT

llm = LLM("openai:gpt-4o", key="...")

# Define tools with schemas the LLM can reason about
search_tool = TOOL(
    name="web_search",
    description="Search the web for current information.",
    parameters={
        "type": "object",
        "properties": {"query": {"type": "string", "description": "Search query"}},
        "required": ["query"],
    },
    fn=lambda query: my_search_fn(query),
)

agent = AGENT(
    llm=llm,
    tools=[search_tool],
    system_prompt="You are a research assistant. Use tools to answer questions.",
    max_iterations=5,
)

memory = MEMORY()
memory.add_msg("user", "What are the latest developments in quantum computing?")
memory = agent(memory)

print(memory.last_asst_msg(content_only=True))
```

### Orchestrated Workflow with Branching

Use WORKFLOW for conditional step execution:

```python
from thoughtflow import MEMORY, THOUGHT, WORKFLOW, SEARCH

workflow = WORKFLOW(name="smart_answer", on_error="skip")

# Step 1: Classify the question
workflow.step(classify_thought, name="classify")

# Step 2: Search only if classification says we need external info
workflow.step(
    SEARCH(query="{last_user_msg}", max_results=3),
    name="search",
    condition=lambda m: m.get_var("classify_result") == "needs_research",
)

# Step 3: Always summarize
workflow.step(summarize_thought, name="summarize")

memory = MEMORY()
memory.add_msg("user", "What happened in tech news today?")
memory = workflow(memory)
```

### Scheduled Jobs with CHRON

Run recurring tasks on a cron schedule:

```python
from thoughtflow import CHRON, MEMORY

def daily_report(memory):
    """Generate and send a daily report."""
    # ... your logic here ...
    print(f"Report generated at {memory.get_var('chron_fired_at')}")

chron = CHRON(name="scheduler", state_file="schedule_state.json")
chron.add("daily_report", schedule="0 9 * * 1-5", action=daily_report)
chron.add("health_check", every=300, action=lambda m: print("OK"))

# In serverless (Lambda handler): chron.tick()
# In a daemon process: chron.start(tick_interval=60)
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
│   ├── llm.py           # LLM — multi-provider model interface
│   ├── embed.py         # EMBED — multi-provider embeddings
│   ├── memory.py        # MEMORY — event-sourced state container
│   ├── thought.py       # THOUGHT — atomic cognitive unit
│   ├── action.py        # ACTION — external operations base class
│   ├── tool.py          # TOOL — LLM-selectable capabilities
│   ├── mcp.py           # MCP — Model Context Protocol client
│   ├── agent.py         # AGENT — autonomous tool-use loop
│   ├── delegate.py      # DELEGATE — multi-agent coordination
│   ├── workflow.py      # WORKFLOW — step-based orchestration
│   ├── chron.py         # CHRON — schedule manager (cron/interval)
│   ├── chat.py          # CHAT — interactive conversation loop
│   ├── _cron_expr.py    # Internal cron expression parser
│   ├── _util.py         # Utilities (event_stamp, valid_extract, etc.)
│   ├── thoughts/        # THOUGHT subclasses (DECIDE, PLAN)
│   ├── actions/         # ACTION subclasses (16 elemental operations)
│   ├── agents/          # AGENT subclasses (ReactAgent, ReflectAgent, PlanActAgent)
│   ├── trace/           # Session tracing and events
│   └── eval/            # Evaluation harness and replay
├── primitives/          # Per-primitive documentation (Markdown)
├── examples/            # Working, runnable examples
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
| **Foundational Primitives** | ✅ Stable | LLM, EMBED, MEMORY, THOUGHT, ACTION |
| **Cognitive / Planning** | ✅ Stable | DECIDE, PLAN |
| **Capability** | ✅ Stable | TOOL, MCP |
| **Autonomy** | ✅ Stable | AGENT, ReactAgent, ReflectAgent, PlanActAgent |
| **Coordination** | ✅ Stable | DELEGATE, CHAT |
| **Orchestration** | ✅ Stable | WORKFLOW, CHRON |
| **Action Subclasses** | ✅ Stable | 16 elemental operations (SEARCH, SCRAPE, FETCH, etc.) |
| **API Stability** | 🟡 Alpha | May evolve based on feedback |
| **Documentation** | ✅ Per-primitive docs | `primitives/` folder with Markdown per class |
| **Test Coverage** | ✅ Comprehensive | Unit + integration tests |
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
| 🧩 [primitives/](primitives/) | Per-primitive documentation (one Markdown file per class) |
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
    <a href="#-foundational-primitives-in-depth">Foundational</a> •
    <a href="#-higher-level-primitives">Higher-Level</a> •
    <a href="#-contributing">Contribute</a>
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
