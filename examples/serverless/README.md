# ThoughtFlow on Serverless

A complete, deployable pattern for running ThoughtFlow agents in stateless
compute — AWS Lambda, Google Cloud Functions, Cloudflare Workers (Python),
or any platform that gives you a function and a place to store a string.

## Why this works unusually well

Most agent frameworks fight serverless: heavyweight dependency trees blow
past size limits, in-process state assumes a long-lived server, and cold
starts are measured in seconds.

ThoughtFlow was designed for exactly this environment:

| Property | Consequence |
|---|---|
| **Zero dependencies** | Your deployment is your handler + one pure-Python package. No layers, no containers required. |
| **MEMORY serializes to JSON** | Full conversation state rehydrates from a string. Any storage works: S3, DynamoDB, Redis, a DB column. |
| **`memory = agent(memory)`** | The whole turn is one pure-ish function call — a natural fit for request/response compute. |
| **Stdlib HTTP** | No SDK clients to initialize at cold start. |

## The pattern

```python
def handle_turn(session_json, user_message, llm):
    # 1. REHYDRATE
    memory = MEMORY.from_json(session_json) if session_json else MEMORY()

    # 2. RUN
    memory.add_msg("user", user_message, channel="webapp")
    memory = agent(memory)
    reply = memory.last_asst_msg(content_only=True)

    # 3. PERSIST
    return reply, memory.to_json(indent=None)
```

That is the entire architecture. `handler.py` in this directory contains a
real `lambda_handler` (S3-backed sessions) plus a local file-backed demo.

## Try it locally

No AWS account or API key needed (a mock LLM is used when no key is set):

```bash
python examples/serverless/handler.py
```

## Deploy to AWS Lambda

```bash
# Package: your handler + thoughtflow, nothing else
mkdir package
pip install thoughtflow --target package
cp examples/serverless/handler.py package/
cd package && zip -r ../function.zip . && cd ..

aws lambda create-function \
  --function-name thoughtflow-chat \
  --runtime python3.12 \
  --handler handler.lambda_handler \
  --zip-file fileb://function.zip \
  --role <your-lambda-role-arn> \
  --environment "Variables={SESSION_BUCKET=<your-bucket>,OPENAI_API_KEY=<your-key>}" \
  --timeout 30
```

The resulting zip is well under a megabyte. Compare with frameworks whose
transitive dependencies alone exceed the 250 MB Lambda limit.

## Notes

- **Concurrency:** one session = one storage object. If the same session can
  receive simultaneous turns, apply your storage's standard conditional-write
  mechanism (S3 ETag, DynamoDB conditional expression).
- **Auditability:** the stored JSON is the complete event log — every message,
  variable change, and log line with timestamps. Debugging a production
  conversation means opening one file.
- **Replay:** pair this with `LLM.record()` / `LLM.replay()` to re-run any
  production session deterministically on your laptop. See
  `examples/scripts/13_record_replay.py`.
