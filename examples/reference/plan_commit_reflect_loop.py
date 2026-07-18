#!/usr/bin/env python3
"""
Reference loop: Plan -> Commit -> Execute -> Reflect.

COPY AND EDIT - DO NOT IMPORT AS A STABLE PACKAGE.
See examples/reference/README.md for contracts, limitations, and extension notes.
"""

import copy
import json
import re
import time
import uuid

from thoughtflow import MEMORY

RESERVED_RECEIPT_KEYS = frozenset(
    ["status", "summary", "error", "hint", "data", "gaps"]
)
BOUNDARY_ACTIONS = frozenset(["REPLAN", "REORIENT", "DONE"])
TERMINAL_REASONS = frozenset(
    [
        "done",
        "reflection_done",
        "max_cycles",
        "wall_clock",
        "task_budget",
        "step_failed",
        "triage_rest",
        "outer_error",
    ]
)
SUCCESS_REASONS = frozenset(["done", "reflection_done", "triage_rest"])
STEP_REF_PATTERN = re.compile(r"^\{step_(\d+)_result\}$")


def _fresh_receipt(base, extra=None):
    """Deep-copy a receipt and reject extension collisions."""
    if extra is not None and not isinstance(extra, dict):
        raise ValueError("receipt extra must be a dict or None")
    extra = extra or {}
    collision = RESERVED_RECEIPT_KEYS.intersection(extra)
    if collision:
        raise ValueError("receipt extra contains reserved keys")
    receipt = copy.deepcopy(base)
    receipt.update(copy.deepcopy(extra))
    return receipt


def receipt_ok(summary="", data=None, extra=None):
    """Return a fresh successful receipt with a string summary."""
    if not isinstance(summary, str):
        raise ValueError("receipt summary must be a string")
    receipt = {"status": "ok", "summary": summary}
    if data is not None:
        receipt["data"] = data
    return _fresh_receipt(receipt, extra)


def receipt_failed(error, hint="", data=None, extra=None):
    """Return a fresh failed receipt with a non-empty error."""
    if not isinstance(error, str) or not error:
        raise ValueError("receipt error must be a non-empty string")
    if not isinstance(hint, str):
        raise ValueError("receipt hint must be a string")
    receipt = {"status": "failed", "error": error, "hint": hint}
    if data is not None:
        receipt["data"] = data
    return _fresh_receipt(receipt, extra)


def receipt_partial(summary="", gaps=None, data=None, extra=None):
    """Return a fresh partial receipt with string summary and list gaps."""
    if not isinstance(summary, str):
        raise ValueError("receipt summary must be a string")
    gaps = [] if gaps is None else gaps
    if not isinstance(gaps, list):
        raise ValueError("receipt gaps must be a list or None")
    receipt = {"status": "partial", "summary": summary, "gaps": gaps}
    if data is not None:
        receipt["data"] = data
    return _fresh_receipt(receipt, extra)


def is_receipt(value):
    """Validate one canonical status-specific receipt shape."""
    if not isinstance(value, dict):
        return False
    status = value.get("status")
    if status == "ok":
        return isinstance(value.get("summary"), str)
    if status == "failed":
        error = value.get("error")
        return (
            isinstance(error, str)
            and bool(error)
            and isinstance(value.get("hint"), str)
        )
    if status == "partial":
        summary_is_string = isinstance(value.get("summary"), str)
        gaps_are_list = isinstance(value.get("gaps"), list)
        return summary_is_string and gaps_are_list
    return False


def split_at_boundary(plan, boundary_actions, include_boundary=True, strict=True):
    """Split native PLAN steps at the first caller-supplied boundary."""
    if not isinstance(plan, list):
        raise TypeError("plan must be a list of steps")
    boundaries = set(boundary_actions)
    for step_index, step in enumerate(plan):
        if not isinstance(step, list) or not step:
            raise TypeError("each plan step must be a non-empty list")
        actions = []
        for task in step:
            action = task.get("action") if isinstance(task, dict) else None
            if not isinstance(action, str) or not action:
                raise TypeError("each task requires a non-empty action")
            actions.append(action)
        boundary = any(action in boundaries for action in actions)
        mixed = boundary and any(action not in boundaries for action in actions)
        if strict and mixed:
            raise ValueError(
                "step {} mixes boundary and action tasks".format(step_index)
            )
        if boundary:
            index = step_index + 1 if include_boundary else step_index
            return plan[:index], plan[index:]
    return list(plan), []


class StepRefError(ValueError):
    """Report an invalid step-result reference."""


def resolve_step_refs(value, step_results, current_step_index=None, depth=0):
    """Resolve exact whole-value ``{step_N_result}`` refs recursively."""
    if depth > 32:
        raise StepRefError("step ref walk exceeded maximum depth")
    if isinstance(value, dict):
        return {
            key: resolve_step_refs(
                item,
                step_results,
                current_step_index,
                depth + 1,
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            resolve_step_refs(item, step_results, current_step_index, depth + 1)
            for item in value
        ]
    if not isinstance(value, str):
        return value
    match = STEP_REF_PATTERN.match(value)
    if not match:
        if "{" in value and "step_" in value and "_result" in value:
            raise StepRefError("unsupported ref {!r}".format(value))
        return value
    step_index = int(match.group(1))
    if current_step_index is not None and step_index >= current_step_index:
        raise StepRefError("forward reference to step_{}".format(step_index))
    if step_index >= len(step_results):
        raise StepRefError("missing result for step_{}".format(step_index))
    return copy.deepcopy(step_results[step_index])


def _validate_id(value, label):
    """Require a non-empty string identity."""
    if not isinstance(value, str) or not value:
        raise ValueError("{} must be a non-empty string".format(label))


def normalize_trigger(raw):
    """Copy a trigger with explicit source, kind, and dict payload."""
    if not isinstance(raw, dict):
        raise ValueError("trigger must be a dict")
    for key in ("source", "kind"):
        if not isinstance(raw.get(key), str) or not raw[key]:
            raise ValueError("trigger requires explicit non-empty {}".format(key))
    if not isinstance(raw.get("payload"), dict):
        raise ValueError("trigger requires explicit dict payload")
    occurrence_id = raw.get("id")
    if "id" not in raw:
        occurrence_id = "occ_{}".format(uuid.uuid4().hex[:12])
    _validate_id(occurrence_id, "trigger id")
    trigger = {
        "id": occurrence_id,
        "source": raw["source"],
        "kind": raw["kind"],
        "payload": copy.deepcopy(raw["payload"]),
    }
    if "dedupe_key" in raw:
        _validate_id(raw["dedupe_key"], "dedupe_key")
        trigger["dedupe_key"] = raw["dedupe_key"]
    return trigger


def _run_state(memory, run_id):
    """Return whether an exact run id has start and terminal events."""
    started = False
    terminal = False
    for event in memory.get_emits():
        if event.get("payload", {}).get("run_id") != run_id:
            continue
        if event["kind"] == "run_started":
            started = True
        elif event["kind"] in ("run_completed", "run_failed"):
            terminal = True
    return started, terminal


def emit_run_started(memory, run_id, trigger, parent_run_id=None):
    """Emit one start with allowlisted trigger fields and optional parent."""
    _validate_id(run_id, "run_id")
    if parent_run_id is not None:
        _validate_id(parent_run_id, "parent_run_id")
    started, terminal = _run_state(memory, run_id)
    if started or terminal:
        raise ValueError("run lifecycle already exists for {!r}".format(run_id))
    summary = {key: trigger[key] for key in ("id", "source", "kind") if key in trigger}
    payload = {"run_id": run_id, "trigger": summary}
    if parent_run_id is not None:
        payload["parent_run_id"] = parent_run_id
    memory.emit("run_started", payload)


def emit_run_terminal(memory, run_id, reason, success):
    """Emit one terminal event using the bounded reason vocabulary."""
    _validate_id(run_id, "run_id")
    if reason not in TERMINAL_REASONS:
        raise ValueError("unsupported terminal reason {!r}".format(reason))
    started, terminal = _run_state(memory, run_id)
    if not started:
        raise ValueError("run_started missing for {!r}".format(run_id))
    if terminal:
        raise ValueError("terminal event already emitted for {!r}".format(run_id))
    kind = "run_completed" if success else "run_failed"
    memory.emit(kind, {"run_id": run_id, "reason": reason, "metrics": {}})


def _validate_exact_params(params, required):
    """Reject non-dict, unknown, missing, and wrong-type params."""
    if not isinstance(params, dict):
        return False, "params must be a dict"
    unknown = set(params) - set(required)
    if unknown:
        return False, "unknown params: {}".format(sorted(unknown))
    for key, expected_type in required.items():
        if key not in params:
            return False, "missing required param {!r}".format(key)
        if not isinstance(params[key], expected_type):
            return False, "param {!r} must be {}".format(
                key,
                expected_type.__name__,
            )
    return True, ""


def validate_read_note(params):
    """Validate READ_NOTE parameters."""
    return _validate_exact_params(params, {"note_id": str})


def validate_send_message(params):
    """Validate SEND_MESSAGE parameters."""
    return _validate_exact_params(params, {"text": str})


def validate_control(params):
    """Validate a parameter-free control action."""
    return _validate_exact_params(params, {})


ACTION_CATALOG = {
    "READ_NOTE": {"validator": validate_read_note, "requires_approval": False},
    "SEND_MESSAGE": {"validator": validate_send_message, "requires_approval": True},
    "REPLAN": {"validator": validate_control, "requires_approval": False},
    "DONE": {"validator": validate_control, "requires_approval": False},
}


def check_approval(action_name, params, agent, catalog):
    """Apply product approval policy to resolved, validated params."""
    if not catalog[action_name].get("requires_approval"):
        return True, ""
    if agent.get("auto_approve"):
        return True, "demo approval"
    return False, "approval denied for {!r}".format(action_name)


def handle_read_note(params, agent):
    """Read one note without side effects."""
    note_id = params["note_id"]
    note = agent.get("notes", {}).get(note_id)
    if note is None:
        return receipt_failed("note not found", hint="check note_id")
    return receipt_ok("read note", data={"note_id": note_id, "body": note})


def handle_send_message(params, agent):
    """Record a demo send after validation and approval."""
    agent.setdefault("sent_messages", []).append(params["text"])
    return receipt_ok("message sent", data={"text": params["text"]})


def handle_control(params, agent):
    """Return a successful receipt for a control boundary."""
    return receipt_ok("control boundary")


HANDLERS = {
    "READ_NOTE": handle_read_note,
    "SEND_MESSAGE": handle_send_message,
    "REPLAN": handle_control,
    "DONE": handle_control,
}


def execute_task(task, step_index, step_results, agent, catalog=None, handlers=None):
    """Resolve, validate, approve, then dispatch one task."""
    catalog = ACTION_CATALOG if catalog is None else catalog
    handlers = HANDLERS if handlers is None else handlers
    action_name = task.get("action")
    try:
        params = resolve_step_refs(
            task.get("params", {}),
            step_results,
            step_index,
        )
    except StepRefError as exc:
        return receipt_failed(str(exc))
    action = catalog.get(action_name)
    if action is None:
        return receipt_failed("unknown action {!r}".format(action_name))
    valid, reason = action["validator"](params)
    if not valid:
        return receipt_failed(reason)
    approved, reason = check_approval(action_name, params, agent, catalog)
    if not approved:
        return receipt_failed(reason, hint="policy gate")
    handler = handlers.get(action_name)
    if handler is None:
        return receipt_failed("no handler for {!r}".format(action_name))
    receipt = handler(params, agent)
    if not is_receipt(receipt):
        return receipt_failed("handler returned a malformed receipt")
    return receipt


def demo_plan(cycle):
    """Return deterministic native PLAN output for offline execution."""
    if cycle == 0:
        return [
            [
                {
                    "action": "READ_NOTE",
                    "params": {"note_id": "intro"},
                    "reason": "Read the introductory note.",
                }
            ],
            [
                {
                    "action": "SEND_MESSAGE",
                    "params": {"text": "Hello from cycle 0"},
                    "reason": "Send the approved greeting.",
                }
            ],
            [
                {
                    "action": "REPLAN",
                    "reason": "Reflect before committing the forecast tail.",
                }
            ],
            [
                {
                    "action": "SEND_MESSAGE",
                    "params": {"text": "forecast only"},
                    "reason": "Show that the forecast tail is not committed.",
                }
            ],
        ]
    return [
        [
            {
                "action": "READ_NOTE",
                "params": {"note_id": "followup"},
                "reason": "Read the follow-up note.",
            }
        ],
        [{"action": "DONE", "reason": "Finish after the committed work."}],
    ]


def reflect(forecast, requested_replan):
    """Return an advisory verdict that never grants action permission."""
    return "CONTINUE" if forecast or requested_replan else "DONE"


def inner_loop(
    agent,
    max_cycles=2,
    max_tasks=20,
    max_wall_seconds=30.0,
    plan_provider=None,
    catalog=None,
    handlers=None,
):
    """Run a bounded plan-commit-reflect loop and return a terminal reason."""
    plan_provider = demo_plan if plan_provider is None else plan_provider
    catalog = ACTION_CATALOG if catalog is None else catalog
    handlers = HANDLERS if handlers is None else handlers
    memory = agent["memory"]
    step_results = []
    tasks_used = 0
    started = time.monotonic()

    for cycle in range(max_cycles):
        if time.monotonic() - started > max_wall_seconds:
            return "wall_clock"
        committed, forecast = split_at_boundary(
            plan_provider(cycle),
            BOUNDARY_ACTIONS,
        )
        requested_replan = False
        for step in committed:
            receipts = []
            for task in step:
                if tasks_used >= max_tasks:
                    return "task_budget"
                if time.monotonic() - started > max_wall_seconds:
                    return "wall_clock"
                tasks_used += 1
                receipt = execute_task(
                    task,
                    len(step_results),
                    step_results,
                    agent,
                    catalog,
                    handlers,
                )
                receipts.append(receipt)
                if receipt["status"] == "failed":
                    memory.add_log("step failed: {}".format(receipt["error"]))
                    return "step_failed"
            step_results.append(receipts[0] if len(receipts) == 1 else receipts)
            actions = [task["action"] for task in step]
            if "DONE" in actions:
                return "done"
            requested_replan = requested_replan or "REPLAN" in actions
        verdict = reflect(forecast, requested_replan)
        memory.add_log("reflection: {}".format(verdict))
        if verdict == "DONE":
            return "reflection_done"

    if not agent.get("sent_messages"):
        memory.add_log(
            "fallback required: max cycles without send; no automatic delivery"
        )
    return "max_cycles"


def outer_loop(raw_trigger, agent, run_id=None):
    """Normalize, triage, execute, and emit one run lifecycle."""
    memory = agent["memory"]
    trigger = normalize_trigger(raw_trigger)
    run_id = trigger["id"] if run_id is None else run_id
    _validate_id(run_id, "run_id")
    emit_run_started(memory, run_id, trigger)
    reason = "triage_rest"
    try:
        if trigger["kind"] == "user_message":
            reason = inner_loop(agent, max_cycles=agent.get("effort_cap", 2))
    except Exception:
        emit_run_terminal(memory, run_id, "outer_error", False)
        raise
    emit_run_terminal(memory, run_id, reason, reason in SUCCESS_REASONS)
    return reason


SUB_RUN_PLANS = {
    "READ_NOTE": [
        [
            {
                "action": "READ_NOTE",
                "params": {"note_id": "intro"},
                "reason": "Read the child run's introductory note.",
            }
        ]
    ],
    "SEND_MESSAGE": [
        [
            {
                "action": "SEND_MESSAGE",
                "params": {"text": "sub-run"},
                "reason": "Attempt the child run's gated side effect.",
            }
        ]
    ],
    "REPLAN": [
        [{"action": "REPLAN", "reason": "Request another bounded child cycle."}]
    ],
    "DONE": [[{"action": "DONE", "reason": "Finish the child run."}]],
}


def run_sub_loop(parent_memory, allowed_actions, max_cycles=1, output_keys=None):
    """Run a bounded child copy and return an honest receipt plus safe outputs."""
    if not isinstance(allowed_actions, list) or not allowed_actions:
        raise ValueError("allowed_actions must be a non-empty list")
    unknown = set(allowed_actions) - set(ACTION_CATALOG)
    if unknown:
        raise ValueError("unknown allowed actions: {}".format(sorted(unknown)))
    catalog = {name: ACTION_CATALOG[name] for name in allowed_actions}
    handlers = {name: HANDLERS[name] for name in allowed_actions}
    child = {
        "memory": parent_memory.copy(),
        "notes": {"intro": "sub-run note"},
        "auto_approve": False,
    }
    plan = copy.deepcopy(SUB_RUN_PLANS[allowed_actions[0]])
    reason = inner_loop(
        child,
        max_cycles=max_cycles,
        plan_provider=lambda cycle: plan,
        catalog=catalog,
        handlers=handlers,
    )
    outputs = {}
    for key in output_keys or []:
        if key in child:
            try:
                json.dumps(child[key])
            except (TypeError, ValueError):
                data = {
                    "reason": reason,
                    "outputs": sorted(outputs),
                    "rejected_output": key,
                }
                receipt = receipt_failed(
                    "sub-run output is not JSON-safe",
                    hint="Allowlist only plain JSON data.",
                    data=data,
                )
                return receipt, {}
            outputs[key] = copy.deepcopy(child[key])
    data = {"reason": reason, "outputs": sorted(outputs)}
    if reason in SUCCESS_REASONS:
        receipt = receipt_ok("sub-run finished", data=data)
    elif reason in ("max_cycles", "task_budget", "wall_clock"):
        receipt = receipt_partial(
            "sub-run stopped before completion",
            gaps=[reason],
            data=data,
        )
    else:
        receipt = receipt_failed("sub-run {}".format(reason), data=data)
    return receipt, outputs


def make_chron_outer_loop_adapter(outer_loop_fn, agent):
    """
    Adapt CHRON action(memory) without claiming occurrence or dedupe context.

    Current CHRON supplies no scheduled occurrence/manual/catch-up context, so
    this closure generates a fresh execution id for each call.
    """

    def chron_action(memory):
        execution_id = "chron_{}".format(uuid.uuid4().hex[:12])
        trigger = {
            "id": execution_id,
            "source": "chron",
            "kind": "scheduled_tick",
            "payload": {"execution_id": execution_id},
        }
        non_memory_state = {
            key: value for key, value in agent.items() if key != "memory"
        }
        child_agent = copy.deepcopy(non_memory_state)
        child_agent["memory"] = memory
        outer_loop_fn(trigger, child_agent, run_id=execution_id)

    return chron_action


def build_demo_agent():
    """Build deterministic plain agent data for offline execution."""
    return {
        "memory": MEMORY(),
        "notes": {"intro": "ThoughtFlow reference loop", "followup": "cycle two"},
        "auto_approve": True,
        "effort_cap": 2,
        "sent_messages": [],
    }


def main():
    """Run the plan-commit-reflect loop entirely offline."""
    agent = build_demo_agent()
    trigger = {"source": "demo", "kind": "user_message", "payload": {"text": "hello"}}
    reason = outer_loop(trigger, agent)
    kinds = [event["kind"] for event in agent["memory"].get_emits()]
    print("Terminal reason:", reason)
    print("Sent messages:", agent["sent_messages"])
    print("Lifecycle emits:", kinds)


if __name__ == "__main__":
    main()
