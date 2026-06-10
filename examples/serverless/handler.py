#!/usr/bin/env python3
"""
ThoughtFlow Serverless Example: Stateless Chat Handler

The pattern that makes ThoughtFlow serverless-native:

    1. REHYDRATE — load the session MEMORY from storage (JSON string)
    2. RUN       — memory = agent(memory)
    3. PERSIST   — serialize the MEMORY back to storage

Because MEMORY serializes completely to JSON and the library has zero
dependencies, the entire deployment is your handler plus one pure-Python
package — no containers, no dependency layers, cold starts in milliseconds.

This file is a real AWS Lambda handler (`lambda_handler`), but the core
function (`handle_turn`) is storage- and platform-agnostic: swap the
S3 calls for DynamoDB, GCS, Redis, or a database column — anything that
stores a string. A local-file storage backend is included so you can run
the whole flow on your laptop:

Run locally (no AWS, mock LLM without an API key):
    python examples/serverless/handler.py
"""

import json
import os

from thoughtflow import LLM, MEMORY, THOUGHT


# =============================================================================
# The agent: any memory -> memory callable built from primitives
# =============================================================================

def build_agent(llm):
    """Build the per-turn flow. Construction is cheap; do it per invocation."""
    return THOUGHT(
        name="respond",
        llm=llm,
        prompt=(
            "You are a helpful, concise assistant. "
            "Continue the conversation. The user just said: {last_user_msg}"
        ),
        channel="webapp",
    )


# =============================================================================
# The serverless turn: rehydrate -> run -> persist
# =============================================================================

def handle_turn(session_json, user_message, llm):
    """
    Execute one chat turn statelessly.

    Args:
        session_json: The stored MEMORY as a JSON string ('' for new session).
        user_message: The user's new message.
        llm: An LLM instance.

    Returns:
        (reply, new_session_json): the assistant's reply and the updated
        session, ready to be written back to storage.
    """
    # 1. REHYDRATE — full conversation state from a JSON string
    if session_json:
        memory = MEMORY.from_json(session_json)
    else:
        memory = MEMORY()

    # 2. RUN — the universal contract
    memory.add_msg("user", user_message, channel="webapp")
    memory = build_agent(llm)(memory)
    reply = memory.last_asst_msg(content_only=True) or ""

    # 3. PERSIST — the complete, auditable event log
    return reply, memory.to_json(indent=None)


# =============================================================================
# AWS Lambda entry point (S3-backed sessions)
# =============================================================================

def lambda_handler(event, context):
    """
    AWS Lambda handler for a chat API.

    Expects an API Gateway proxy event with a JSON body:
        {"session_id": "abc123", "message": "Hello!"}

    Sessions are stored as JSON objects in S3 (one per session_id).
    boto3 is available in the Lambda runtime by default — ThoughtFlow
    itself needs nothing.
    """
    import boto3  # provided by the Lambda runtime

    bucket = os.environ["SESSION_BUCKET"]
    s3 = boto3.client("s3")

    body = json.loads(event.get("body") or "{}")
    session_id = body["session_id"]
    user_message = body["message"]
    key = "sessions/{}.json".format(session_id)

    # Load existing session (empty string for a new conversation)
    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
        session_json = obj["Body"].read().decode("utf-8")
    except s3.exceptions.NoSuchKey:
        session_json = ""

    llm = LLM("openai:gpt-4o-mini", key=os.environ["OPENAI_API_KEY"])
    reply, new_session_json = handle_turn(session_json, user_message, llm)

    s3.put_object(Bucket=bucket, Key=key, Body=new_session_json.encode("utf-8"))

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"reply": reply, "session_id": session_id}),
    }


# =============================================================================
# Local demonstration (file-backed sessions, no AWS required)
# =============================================================================

class MockLLM(LLM):
    """Offline stand-in so the demo runs without an API key."""

    REPLIES = [
        "Hello! How can I help you today?",
        "Great question — milliseconds matter, so I'll keep it short.",
        "You're welcome. Everything we discussed is in the session log.",
    ]

    def __init__(self):
        super().__init__("openai:gpt-4o-mini", key="mock")
        self._turn = 0

    def call(self, msg_list, params={}, output_schema=None, stream=False):
        reply = self.REPLIES[min(self._turn, len(self.REPLIES) - 1)]
        self._turn += 1
        return [reply]


def main():
    """Simulate three stateless invocations against file storage."""
    store_path = "/tmp/thoughtflow_session_demo.json"
    if os.path.exists(store_path):
        os.remove(store_path)

    if os.getenv("OPENAI_API_KEY"):
        llm = LLM("openai:gpt-4o-mini", key=os.environ["OPENAI_API_KEY"])
    else:
        print("(no OPENAI_API_KEY — using a mock LLM)\n")
        llm = MockLLM()

    turns = [
        "Hi there!",
        "Why does ThoughtFlow work well in serverless functions?",
        "Thanks!",
    ]

    for user_message in turns:
        # Each loop iteration simulates a separate, stateless invocation:
        # nothing survives in process memory between turns.
        session_json = ""
        if os.path.exists(store_path):
            with open(store_path, "r", encoding="utf-8") as f:
                session_json = f.read()

        reply, new_session_json = handle_turn(session_json, user_message, llm)

        with open(store_path, "w", encoding="utf-8") as f:
            f.write(new_session_json)

        print("user: {}".format(user_message))
        print("assistant: {}\n".format(reply))

    # The stored session is a complete, auditable event log
    final = MEMORY.from_json(new_session_json)
    msgs = final.get_msgs()
    print("Session log contains {} messages across {} turns.".format(
        len(msgs), len(turns)))
    print("Full state lives in one JSON file: {}".format(store_path))


if __name__ == "__main__":
    main()
