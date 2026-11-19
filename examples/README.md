# `examples/` — Runnable Walkthroughs, Notebooks, and Deployment Recipes

> **Scope:** Copy-pasteable scripts, interactive notebooks, architectural reference loops, and serverless handlers built on ThoughtFlow.

---

## Directory Layout

```
examples/
├── scripts/        # 14 numbered Python scripts (run offline with MockLLM or live with API keys)
├── notebooks1/     # 5 progressive Jupyter notebooks (foundations -> cloud deployment -> personas)
├── reference/      # Copy-and-edit production outer/inner plan-commit-reflect loop recipe
└── serverless/     # Deployable zero-dependency AWS Lambda stateless chat handler
```

---

## 1. Numbered Scripts (`examples/scripts/`)

Every script in `examples/scripts/` runs directly from a checkout (`PYTHONPATH=src python examples/scripts/<name>.py`) or after `pip install thoughtflow`. Scripts that demonstrate cognitive patterns include deterministic `MockLLM` / `ReplayLLM` defaults so you can run them immediately without API keys:

| Script | Primitives Exercised | What You Learn |
|--------|----------------------|----------------|
| [`01_hello_world.py`](scripts/01_hello_world.py) | `LLM`, `MEMORY`, `THOUGHT` | The universal `memory = thought(memory)` contract |
| [`02_action.py`](scripts/02_action.py) | `ACTION`, `MEMORY` | Wrapping external operations with timing, `{name}_result`, and error containment |
| [`03_memory.py`](scripts/03_memory.py) | `MEMORY` | Channels, variable histories, tombstones, `>10KB` object compression, JSON/pickle round-trips |
| [`04_valid_extract.py`](scripts/04_valid_extract.py) | `valid_extract` | Extracting typed dicts/lists from fenced or prose-wrapped model output |
| [`05_thought_advanced.py`](scripts/05_thought_advanced.py) | `THOUGHT` | Non-LLM operations (`memory_query`, `variable_set`, `conditional`), validators, hooks, `required_vars` / `optional_vars` |
| [`06_multi_provider.py`](scripts/06_multi_provider.py) | `LLM` | Swapping OpenAI, Anthropic, Groq, Gemini, OpenRouter, and local Ollama via `service:model` |
| [`07_workflow.py`](scripts/07_workflow.py) | `WORKFLOW`, `THOUGHT`, `ACTION` | Conditional multi-step pipelines and execution status inspection |
| [`09_decide.py`](scripts/09_decide.py) | `DECIDE`, `DM`, `LLM` | Categorical choices, `DM` System-One binary `choices=bool` (`noul`), uncertainty thresholds, and offline `DM.replay()` |
| [`10_plan.py`](scripts/10_plan.py) | `PLAN` | Sequential/parallel task DAGs (`list[list[dict]]`), parameter schemas, and `{step_N_result}` whole-value references |
| [`11_actions.py`](scripts/11_actions.py) | `SAY`, `READ`, `WRITE`, `SLEEP`, `CALL`, ... | Composing built-in stdlib `ACTION` verbs with `{var}` substitution |
| [`12_chat.py`](scripts/12_chat.py) | `CHAT`, `THOUGHT` | Interactive terminal and programmatic turn-by-turn conversation loops |
| [`13_record_replay.py`](scripts/13_record_replay.py) | `LLM.record`, `LLM.replay`, `Harness` | Recording live sessions into `MEMORY`, replaying offline, and running `thoughtflow.eval.Harness` |
| [`14_rag_llm_view.py`](scripts/14_rag_llm_view.py) | `EMBED`, `MEMORY.add_augment`, `AGENT` | Non-destructive RAG context injection (`merge_augments=True`) while keeping UI history clean |
| [`15_thought_integration_test.py`](scripts/15_thought_integration_test.py) | `THOUGHT` | Testing full `THOUGHT` parse-validate-repair pipelines (`oneOf`, `rescue`, `{name}_outcome`) |

---

## 2. Interactive Notebooks (`examples/notebooks1/`)

1. **`01_foundations.ipynb`** — `LLM`, `MEMORY`, `THOUGHT`, and `ACTION` from scratch.
2. **`02_decisions_plans_actions.ipynb`** — Routing with `DECIDE`, planning with `PLAN`, and executing `ACTION` verbs.
3. **`03_research_agent.ipynb`** — Building a multi-step web research agent with `SEARCH`, `SCRAPE`, and synthesis thoughts.
4. **`04_deploy_to_cloud.ipynb`** — Packaging a stateless ThoughtFlow agent for cloud / serverless execution.
5. **`05_persona_example.ipynb`** — Multi-turn persona agents with persistent `MEMORY`.

---

## 3. Production Reference Recipes & Serverless (`reference/` & `serverless/`)

- **[`examples/reference/`](reference/README.md):** Copy-and-edit **plan-commit-reflect** outer/inner loop (`plan_commit_reflect_loop.py`) demonstrating receipts, `{step_N_result}` resolution, approval gates, `MEMORY.emit()` run lifecycle events, isolated child sub-runs, and `CHRON` scheduling bridges — backed by unit tests in `tests/unit/test_reference_plan_loop.py`.
- **[`examples/serverless/`](serverless/README.md):** Complete AWS Lambda handler (`handler.py`) showing ThoughtFlow's signature 3-line stateless turn pattern (`MEMORY.from_json` -> `agent(memory)` -> `memory.to_json`) with sub-second cold starts and zero external dependencies.
