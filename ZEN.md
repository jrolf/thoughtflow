# The Zen of Thoughtflow

The **Zen of Thoughtflow** is a set of guiding principles for building a framework that prioritizes simplicity, clarity, and flexibility. Thoughtflow is not meant to be a rigid system but a tool that helps developers create and explore freely. It's designed to stay light, modular, and focused, with Python at its core. The goal is to reduce complexity, maintain transparency, and ensure that functionality endures over time. Thoughtflow isn't about trying to please everyone—it's about building a tool that serves its purpose well, allowing developers to focus on their own path.

---

### 1. First Principles First
Thoughtflow is built on fundamental, simple concepts. Each piece should start with core truths, avoiding the temptation to build on excessive abstractions.

### 2. Complexity is the Enemy
Keep it simple. Thoughtflow should be Pythonic, intuitive, and elegant. Let ease of use guide every decision, ensuring the library remains as light as possible.

### 3. Obvious Over Abstract
If the user has to dig deep to understand what's going on, the design has failed. Everything should naturally reveal its purpose and operation.

### 4. Transparency is Trust
Thoughtflow must operate transparently. Users should never have to guess what's happening under the hood—understanding empowers, while opacity frustrates.

### 5. Backward Compatibility is Sacred
Code should endure. Deprecation should be rare, and backward compatibility must be respected to protect users' investments in their existing work.

### 6. Flexibility Over Rigidity
Provide intelligent defaults, but allow users infinite possibilities. Thoughtflow should never micromanage the user's experience—give them the freedom to define their journey.

### 7. Minimize Dependencies, Pack Light
Thoughtflow should rely only on minimal, light libraries. Keep the dependency tree shallow, and ensure it's always feasible to deploy the library in serverless architectures.

### 8. Clarity Over Cleverness
Documentation, code, and design must be explicit and clear, not implicit or convoluted. Guide users, both beginners and experts, with straightforward tutorials and examples.

### 9. Modularity is Better than Monolith
Thoughtflow should be a collection of lightweight, composable pieces. Never force the user into an all-or-nothing approach—each component should be able to stand alone. Every builder loves legos.

### 10. Accommodate Both Beginners and Experts
Thoughtflow should grow with its users. Provide frictionless onboarding for beginners while offering flexibility for advanced users to scale and customize as needed.

### 11. Make a Vehicle, Not a Destination
Thoughtflow should focus on the structuring and intelligent sequencing of user-defined thoughts. Classes should be as generalizable as possible, and logic should be easily exported and imported via thought files.

### 12. Good Documentation Accelerates Usage
Documentation and tutorials must be clear, comprehensive, and always up-to-date. They should guide users at every turn, ensuring knowledge is readily available.

### 13. Don't Try to Please Everyone
Thoughtflow is focused and light. It isn't designed to accommodate every possible use case, and that's intentional. Greatness comes from focus, not from trying to do everything.

### 14. Python is King
Thoughtflow is built to be Pythonic. Python is the first-class citizen, and every integration, feature, and extension should honor Python's language and philosophy.

---

## Design Document

ThoughtFlow is designed to be a sophisticated AI agent framework for building 
intelligent, memory-aware systems that can think, act, and maintain persistent 
state. 

---

### Thoughtflow — Plain-English Spec

This document explains **exactly** how to engineer Thoughtflow in simple, idiomatic Python. It is written for a reader with **zero** prior exposure to Thoughtflow.

Thoughtflow is a **Pythonic cognitive engine**. You write ordinary Python—`for`/`while`, `if/elif/else`, `try/except`, and small classes—no graphs, no hidden DSLs. A *flow* is "just a function" that accepts a `MEMORY` object and returns that same `MEMORY` object, modified. Cognition is built from four primitives:

1. **LLM** — A tiny wrapper around a chat-style language model API.
2. **MEMORY** — The single state container that keeps messages, events, logs, reflections, and variables.
3. **THOUGHT** — The unit of cognition: Prompt + Context + LLM + Parsing + Validation (+ Retries + Logging).
4. **ACTION** — Anything the agent *does* (respond, call an HTTP API, write a file, query a vector store, etc.), with consistent logging.

The rest of this spec describes **design philosophy**, **object contracts**, **method/attribute lists**, **data conventions**, and **how everything fits together**—plus example usage that the finished library should support.

---

### Final Notes on Style

* Keep constructors short and forgiving; let users pass just a few arguments.
* Prefer small, pure helpers (parsers/validators) over big class hierarchies.
* Do not hide failures; always leave a visible trace in `logs` and `events`.
* Default behaviors should serve 90% of use cases; exotic needs belong in user code.
