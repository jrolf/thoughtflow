# Decision Models (`DM` & `DECIDE`)

ThoughtFlow treats **System-One decision models** (`DM`) as a first-class Intelligence primitive beside `LLM` and `EMBED`, and integrates them seamlessly into `DECIDE`.

Where a generative `LLM` emits prose tokens and relies on prompt engineering + parsing to extract a label, a `DM` evaluates structured `state` against one or more typed `questions` (`choice`, `noul`, `score`, `box`) in a **single forward pass** and returns calibrated probability distributions.

---

## Why `DM` Exists Alongside `LLM`

1. **Speed & cost:** A decision model answers multiple independent routing, safety, rubric, and boolean questions over shared context in one pass without generating reasoning or prose tokens.
2. **Calibrated uncertainty:** Instead of trusting uncalibrated self-reported numbers ("confidence: 95%"), `DM` returns actual probability distributions — allowing `DECIDE` to enforce `min_confidence` and `min_margin` gates and escalate genuinely ambiguous cases to an `LLM` or human reviewer.
3. **Wire-dialect normalization:** Different providers expose incompatible schemas and confidence formulas (OpenRouter `/api/alpha/decisions`, TypeSafe `/v1/systemone`, OpenAI `/v1/decisions`, Liquid `d1`, Cloudflare Workers AI `clef`, Ollama/vLLM `/v1/systemone`). `DM` normalizes all of them into one Python dict shape.

---

## One-Line Swap in `DECIDE`

`DECIDE` accepts either an `LLM` or a `DM` (`model=` is an alias for `llm=`). Downstream code reading `memory.get_var("{name}_result")` does not change:

```python
from thoughtflow import DM, DECIDE, MEMORY

dm = DM("openrouter:typesafe/jev-1.14", key="sk-or-...")

router = DECIDE(
    name="route",
    model=dm,   # works identically with llm=LLM("openai:gpt-4o", key="...")
    choices={
        "billing": "Invoices, duplicate charges, and refunds",
        "tech": "Crashes, login failures, and API bugs",
        "sales": "Pricing, plans, and seat quotes",
    },
    prompt="Route this support message: {last_user_msg}",
    min_margin=0.50,
    default="escalate",
)

memory = MEMORY()
memory.add_msg("user", "I was billed twice for my subscription this month.")
memory = router(memory)

print(memory.get_var("route_result"))    # "billing"
print(memory.get_var("route_outcome"))   # probabilities, confidence, margin, source
```

### Automatic Prompt-Injection Isolation (`state="auto"`)

When `DECIDE` runs against a `DM` with default `state="auto"`, it parses `{var}` placeholders in `prompt`, lifts the raw values into a structured `state` dictionary (`{"last_user_msg": "..."}`), and rewrites the question `instructions` to reference backticked field names (`Route this support message: \`last_user_msg\``). Untrusted user text stays cleanly separated from instructions.

---

## Four Decision Modes

All four modes work on both `DM` and `LLM` (multi-question `questions=` on an `LLM` adapts automatically via `DM.from_llm`):

| Mode | `DECIDE` Setup | Stored `{name}_result` |
|------|----------------|------------------------|
| **Categorical (`choice`)** | `choices=["a", "b"]` or `choices={"a": "desc"}` | Selected key (`str`) |
| **Binary (`noul`)** | `choices=bool` (optional `threshold=0.5`) | `True` or `False` (`bool`), with $P(\text{true})$ in `{name}_outcome["probability"]` |
| **Ordered rubric (`score`)** | `levels=["Low: ...", "Medium: ...", "High: ..."]` | Continuous rubric position (`float` in `[0.0, K - 1.0]`) |
| **Multi-question (`multi`)** | `questions={"owner": {...}, "is_sev1": {...}}` | Dict mapping each question ID to its typed value |

---

## Cross-Vendor Confidence & Margin Normalization

Upstream providers compute wire `confidence` using incompatible formulas over the same probability vector $p$ of length $K$:
- Google reports $\max(p)$.
- TypeSafe, Liquid, Perplexity, and OpenAI report linear concentration $\frac{K \cdot \max(p) - 1}{K - 1}$.
- Upstage and Cloudflare report normalized negentropy $1 - \frac{H(p)}{\ln K}$.
- Most providers omit `confidence` altogether on binary `noul` answers.

`DM` preserves the raw wire number as `provider_confidence` and computes uniform `confidence` (linear concentration in $[0, 1]$) and `margin` ($p_{(1)} - p_{(2)}$) directly from `probabilities` so `min_confidence` and `min_margin` thresholds behave identically regardless of vendor.

---

## Portable Fallback (`DM.from_llm`) & Deterministic Replay

- **No decision endpoint? Use `DM.from_llm(llm)`:** Wraps any generative `LLM` (or `ReplayLLM`) behind the exact `DM.call(state, questions)` interface (`probabilities=None` so callers never mistake generative text for calibrated probabilities).
- **Automatic failover:** Pass `retry={"fallback_llm": backup_llm}` to `DECIDE(model=dm, ...)` to rescue transient outages or refusals with a single backup pass.
- **Hermetic replay:** `dm.record(memory)` captures `kind='decide'` exchanges in `MEMORY`, and `DM.replay(memory)` returns a thread-safe `ReplayDM` for instant offline CI tests.

For complete API details, see [`primitives/DM.md`](https://github.com/jrolf/thoughtflow/blob/main/primitives/DM.md) and [`primitives/DECIDE.md`](https://github.com/jrolf/thoughtflow/blob/main/primitives/DECIDE.md).
