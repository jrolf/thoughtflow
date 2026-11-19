"""
DM class for ThoughtFlow.

A unified Intelligence-layer interface for calling structured "System One"
decision models across providers and wire dialects.

Where ``LLM`` maps messages to generated text and ``EMBED`` maps text to float
vectors, ``DM`` maps structured ``state`` plus one or more typed ``questions``
(``choice``, ``noul``, ``score``, ``box``) to calibrated probability
distributions in a single forward pass without prose generation.

Supported wire dialects (normalized automatically by service prefix):
  - ``systemone``: OpenRouter (``/api/alpha/decisions`` and ``/api/v1/systemone``),
    TypeSafe (Jev), Liquid AI (d1), Perplexity (pplx-decider), Inception
    (mercury-decide), Upstage (solar-decide), Ollama (``/v1/systemone``), and
    vLLM (``/v1/systemone``).
  - ``cloudflare_workers``: Cloudflare Workers AI Clef endpoints (System One
    request body with Cloudflare's outer ``{"result": ..., "success": true}``
    response wrapper).
  - ``openai_decisions``: OpenAI ``POST /v1/decisions`` (``input`` /
    ``input_json``, ordered ``questions`` list with ``predicate``, ``choice``,
    and ``score``, and list-shaped ``answers`` and ``probabilities``).
  - ``llm_fallback``: ``DM.from_llm(llm)`` emulates the exact ``DM.call``
    contract over any generative ``LLM`` or ``ReplayLLM`` so workflows remain
    portable to providers that do not host a dedicated decision endpoint.

Cross-vendor confidence normalization:
  Different decision-model hosts compute their wire ``confidence`` field using
  incompatible formulas over the same probability vector ``p`` of length ``K``
  (e.g. ``max(p)`` on Google, ``(K * max(p) - 1) / (K - 1)`` on TypeSafe,
  Liquid, Perplexity, OpenAI, and Microsoft, and ``1 - H(p) / ln(K)`` on
  Upstage and Cloudflare), and most omit ``confidence`` on binary ``noul``
  answers altogether. ``DM`` preserves the raw field as ``provider_confidence``
  and computes uniform ``confidence`` (linear concentration over uniform) and
  ``margin`` (``p_top1 - p_top2``) directly from ``probabilities`` so caller
  thresholds behave identically across vendors and upstream hosts.
"""

from __future__ import annotations

import copy
import json
import math
import threading
import urllib.error
import urllib.request

from thoughtflow._util import TRANSPORT_PARAM_KEYS, exchange_key, extract_balanced_json
from thoughtflow.llm_params import (
    LLM_RESERVED_KEYS,
    merge_call_params,
    normalize_usage,
    split_call_params,
)

# HTTP status codes that merit retry when a caller opts into retries.
_RETRYABLE_STATUSES = frozenset({408, 409, 425, 429, 500, 502, 503, 504})

# Default endpoint URL and wire dialect per service prefix.
PROVIDER_DECISION_PROFILES = {
    "openrouter": ("https://openrouter.ai/api/alpha/decisions",     "systemone"),
    "typesafe":   ("https://api.typesafe.ai/v1/systemone",          "systemone"),
    "liquid":     ("https://api.liquid.ai/decisions/v1/systemone",  "systemone"),
    "perplexity": ("https://api.perplexity.ai/v1/decisions",        "systemone"),
    "inception":  ("https://api.inceptionlabs.ai/v1/decisions",     "systemone"),
    "upstage":    ("https://api.upstage.ai/v1/systemone",           "systemone"),
    "ollama":     ("http://localhost:11434/v1/systemone",           "systemone"),
    "vllm":       ("http://localhost:8000/v1/systemone",            "systemone"),
    "cloudflare": (None,                                            "cloudflare_workers"),
    "openai":     ("https://api.openai.com/v1/decisions",           "openai_decisions"),
}

_DM_RESERVED_KEYS = LLM_RESERVED_KEYS | frozenset({"dialect", "backing_llm"})


class DecisionError(Exception):
    """
    Raised when a decision-model request fails at the HTTP, transport, or wire layer.

    Mirrors ``ChatError`` so library callers never get silent stdout prints or
    ambiguous empty dicts on failed decision calls.

    Attributes:
        status (int or None): HTTP status code when the failure came from HTTP.
        body (str): Truncated error body text when available.
        retryable (bool): True for rate limits, 5xx errors, and transient
            network timeouts; False for deterministic 4xx client errors.
    """

    def __init__(self, message, status=None, body="", retryable=False):
        """Initialize a DecisionError with optional HTTP status, body preview, and retryable flag."""
        super().__init__(message)
        self.status = status
        self.body = body
        self.retryable = bool(retryable)


def compute_distribution_metrics(probs):
    """
    Compute vendor-agnostic uncertainty metrics from a discrete probability map.

    Args:
        probs (dict or None): Mapping of option/level key to probability in [0, 1].

    Returns:
        dict: ``top_prob`` (highest probability), ``margin`` (top1 minus top2),
            ``concentration`` (linear excess over uniform ``(K*max_p - 1)/(K - 1)``),
            and ``entropy_conf`` (normalized negentropy ``1 - H(p)/ln(K)``).
    """
    if not probs:
        return {
            "top_prob": None,
            "margin": None,
            "concentration": None,
            "entropy_conf": None,
        }

    values = sorted((max(0.0, float(v)) for v in probs.values()), reverse=True)
    total = sum(values)
    if total <= 0.0:
        return {
            "top_prob": 0.0,
            "margin": 0.0,
            "concentration": 0.0,
            "entropy_conf": 0.0,
        }
    if abs(total - 1.0) > 1e-3:
        values = [v / total for v in values]

    k = len(values)
    top_prob = values[0]
    runner_up = values[1] if k > 1 else max(0.0, 1.0 - top_prob)
    margin = max(0.0, top_prob - runner_up)

    if k > 1:
        concentration = max(0.0, min(1.0, (k * top_prob - 1.0) / (k - 1)))
        entropy = 0.0
        for p in values:
            if p > 1e-12:
                entropy -= p * math.log(p)
        entropy_conf = max(0.0, min(1.0, 1.0 - (entropy / math.log(k))))
    else:
        concentration = max(0.0, min(1.0, top_prob))
        entropy_conf = 1.0

    return {
        "top_prob": round(top_prob, 6),
        "margin": round(margin, 6),
        "concentration": round(concentration, 6),
        "entropy_conf": round(entropy_conf, 6),
    }


def normalize_questions_spec(questions):
    """
    Validate and normalize caller question specs into canonical System-One shape.

    Accepts ergonomic Python shorthands alongside raw System-One / OpenAI forms:
      - ``choice``: ``choices=["a", "b"]`` (encoded as ``{"a": None, "b": None}``)
        or ``choices={"a": "desc", ...}`` or ``criteria={...}``.
      - ``noul`` (aliases ``predicate``, ``bool``, ``boolean``, ``type=bool``, or
        ``choices=bool``): optional ``criteria={"true": "...", "false": "..."}``.
      - ``score``: ``levels=[...]`` or ``criteria=[...]`` (ordered low-to-high).
      - ``box``: ``instructions="..."`` (bounding-box localization on image state).

    Args:
        questions (dict): Map of ``question_id -> question_spec``.

    Returns:
        dict: Canonical question map ready for wire encoding and replay hashing.

    Raises:
        ValueError: When ``questions`` is empty or any question spec is invalid.
    """
    if not isinstance(questions, dict) or not questions:
        raise ValueError("DM requires a non-empty 'questions' dict.")

    canonical = {}
    for qid, spec in questions.items():
        if not isinstance(qid, str) or not qid.strip():
            raise ValueError("Question keys must be non-empty strings, got: {!r}".format(qid))
        if not isinstance(spec, dict):
            raise ValueError(
                "Question '{}' must be a dict specification, got: {}".format(
                    qid, type(spec).__name__
                )
            )

        raw_type = spec.get("type")
        choices_field = spec.get("choices")
        if raw_type is bool or choices_field is bool or choices_field == "bool":
            qtype = "noul"
        elif raw_type is None:
            if "levels" in spec:
                qtype = "score"
            elif "choices" in spec or isinstance(spec.get("criteria"), dict):
                qtype = "choice"
            elif isinstance(spec.get("criteria"), (list, tuple)):
                qtype = "score"
            else:
                qtype = "choice"
        elif raw_type in ("predicate", "bool", "boolean"):
            qtype = "noul"
        else:
            qtype = str(raw_type)

        instructions = spec.get("instructions")
        if instructions is None:
            instructions = spec.get("prompt", "")

        entry = {
            "type": qtype,
            "instructions": instructions,
        }

        if qtype == "choice":
            raw_choices = spec.get("criteria") if "criteria" in spec else choices_field
            if isinstance(raw_choices, dict):
                if not raw_choices:
                    raise ValueError("Choice question '{}' cannot have empty choices.".format(qid))
                entry["criteria"] = {str(k): v for k, v in raw_choices.items()}
            elif isinstance(raw_choices, (list, tuple)):
                if not raw_choices:
                    raise ValueError("Choice question '{}' cannot have empty choices.".format(qid))
                entry["criteria"] = {str(c): None for c in raw_choices}
            else:
                raise ValueError(
                    "Choice question '{}' requires a 'choices' or 'criteria' list or dict.".format(qid)
                )

        elif qtype == "noul":
            crit = spec.get("criteria")
            if crit is not None:
                if not isinstance(crit, dict):
                    raise ValueError("Noul question '{}' criteria must be a dict.".format(qid))
                t_val = crit.get("true", crit.get(True))
                f_val = crit.get("false", crit.get(False))
                entry["criteria"] = {"true": t_val, "false": f_val}

        elif qtype == "score":
            raw_levels = spec.get("criteria") if "criteria" in spec else spec.get("levels")
            if not isinstance(raw_levels, (list, tuple)) or not raw_levels:
                raise ValueError(
                    "Score question '{}' requires a non-empty 'levels' or 'criteria' list.".format(qid)
                )
            entry["criteria"] = list(raw_levels)

        elif qtype == "box":
            if instructions == "" or instructions is None:
                raise ValueError("Box question '{}' requires non-empty 'instructions'.".format(qid))
        else:
            raise ValueError(
                "Unsupported decision question type {!r} on question '{}'.".format(qtype, qid)
            )

        canonical[qid] = entry

    return canonical


def build_wire_payload(dialect, model, state, canonical_questions, wire_params):
    """
    Encode ``(model, state, canonical_questions)`` into the provider's JSON body.

    Args:
        dialect (str): ``'systemone'``, ``'cloudflare_workers'``, or ``'openai_decisions'``.
        model (str): Provider model identifier.
        state: String, dict, or list describing the evidence to judge.
        canonical_questions (dict): Output of ``normalize_questions_spec``.
        wire_params (dict): Extra provider wire fields (e.g. ``assets``, ``provider``).

    Returns:
        dict: JSON-serializable wire request payload.
    """
    if dialect in ("systemone", "cloudflare_workers"):
        payload = {
            "model": model,
            "state": state,
            "questions": canonical_questions,
        }
        payload.update(wire_params)
        return payload

    if dialect == "openai_decisions":
        # OpenAI /v1/decisions takes `input` as a string or array of user messages
        # (using an `input_json` content part for structured dicts/lists).
        if isinstance(state, str):
            oa_input = state
        elif (
            isinstance(state, list)
            and state
            and all(isinstance(item, dict) and "role" in item and "content" in item for item in state)
        ):
            oa_input = state
        else:
            oa_input = [
                {
                    "role": "user",
                    "content": [{"type": "input_json", "data": state}],
                }
            ]

        oa_questions = []
        for qid, qspec in canonical_questions.items():
            qtype = qspec["type"]
            instr = qspec.get("instructions", "")

            if qtype == "noul":
                crit = qspec.get("criteria")
                if crit and isinstance(instr, str):
                    parts = [instr] if instr else []
                    if crit.get("true") is not None:
                        parts.append("True when: {}".format(crit["true"]))
                    if crit.get("false") is not None:
                        parts.append("False when: {}".format(crit["false"]))
                    instr = "\n".join(parts)
                oa_questions.append({
                    "type": "predicate",
                    "name": qid,
                    "instructions": instr,
                })

            elif qtype == "choice":
                choices_arr = []
                for val, desc in qspec["criteria"].items():
                    item = {"value": val}
                    if desc is not None and desc != "":
                        item["description"] = desc
                    choices_arr.append(item)
                oa_questions.append({
                    "type": "choice",
                    "name": qid,
                    "instructions": instr,
                    "choices": choices_arr,
                })

            elif qtype == "score":
                levels_arr = []
                for idx, level in enumerate(qspec["criteria"]):
                    if isinstance(level, dict) and "label" in level:
                        levels_arr.append(dict(level))
                    else:
                        levels_arr.append({
                            "label": "level_{}".format(idx),
                            "description": str(level),
                        })
                oa_questions.append({
                    "type": "score",
                    "name": qid,
                    "instructions": instr,
                    "levels": levels_arr,
                })

            elif qtype == "box":
                raise ValueError(
                    "OpenAI '/v1/decisions' dialect does not support 'box' localization questions."
                )

        payload = {
            "model": model,
            "input": oa_input,
            "questions": oa_questions,
        }
        payload.update(wire_params)
        return payload

    raise ValueError("Unknown decision wire dialect: {!r}".format(dialect))


def parse_wire_response(dialect, raw_response, canonical_questions, service, model):
    """
    Normalize a provider's wire JSON into ThoughtFlow's uniform decision envelope.

    Args:
        dialect (str): Wire dialect used for the request.
        raw_response (dict): Parsed JSON response from the provider.
        canonical_questions (dict): Canonical question map from the request.
        service (str): ThoughtFlow service prefix.
        model (str): Requested model slug.

    Returns:
        dict: Normalized response containing ``id``, ``model``, ``provider``,
            ``answers`` (ordered map of per-question dicts), and ``usage``.

    Raises:
        DecisionError: When the response payload represents an upstream API error
            or contains malformed numeric/choice fields.
    """
    if not isinstance(raw_response, dict):
        raise DecisionError("Decision endpoint returned non-object JSON: {!r}".format(raw_response))

    body = raw_response
    if dialect == "cloudflare_workers":
        if body.get("success") is False:
            errors = body.get("errors") or body
            raise DecisionError(
                "Cloudflare Workers AI error: {}".format(errors),
                body=json.dumps(errors)[:500],
            )
        if isinstance(body.get("result"), dict):
            body = body["result"]

    if body.get("error") is not None and "answers" not in body:
        err = body["error"]
        msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
        raise DecisionError(msg, body=json.dumps(err)[:500])

    raw_answers = body.get("answers", {})
    if isinstance(raw_answers, list):
        raw_answers = {
            item.get("name"): item
            for item in raw_answers
            if isinstance(item, dict) and item.get("name") is not None
        }
    elif not isinstance(raw_answers, dict):
        raw_answers = {}

    ordered_answers = {}
    for qid in canonical_questions:
        ans = raw_answers.get(qid)
        if not isinstance(ans, dict):
            ordered_answers[qid] = {
                "type": "refusal",
                "value": None,
                "probability": None,
                "probabilities": None,
                "provider_confidence": None,
                "confidence": None,
                "margin": None,
            }
            continue

        atype = ans.get("type")
        if atype == "predicate":
            atype = "noul"

        if atype == "refusal":
            ordered_answers[qid] = {
                "type": "refusal",
                "value": None,
                "probability": None,
                "probabilities": None,
                "provider_confidence": None,
                "confidence": None,
                "margin": None,
            }
            continue

        try:
            if atype == "choice":
                chosen = ans.get("choice")
                if chosen is None:
                    raise DecisionError("Choice answer for '{}' missing 'choice' field.".format(qid))
                raw_probs = ans.get("probabilities")
                if isinstance(raw_probs, list):
                    probs = {
                        str(item["value"]): float(item["probability"])
                        for item in raw_probs
                        if isinstance(item, dict) and "value" in item and "probability" in item
                    }
                elif isinstance(raw_probs, dict):
                    probs = {str(k): float(v) for k, v in raw_probs.items()}
                else:
                    probs = None

                metrics = compute_distribution_metrics(probs)
                prov_conf = ans.get("confidence")
                prov_conf_f = float(prov_conf) if prov_conf is not None else None
                win_prob = (
                    round(float(probs[str(chosen)]), 6)
                    if (probs and str(chosen) in probs)
                    else metrics["top_prob"]
                )
                ordered_answers[qid] = {
                    "type": "choice",
                    "value": chosen,
                    "probability": win_prob,
                    "probabilities": probs,
                    "provider_confidence": prov_conf_f,
                    "confidence": metrics["concentration"] if probs else prov_conf_f,
                    "margin": metrics["margin"],
                }

            elif atype == "noul":
                raw_p = ans.get("noul", ans.get("probability"))
                if raw_p is None:
                    raise DecisionError("Noul answer for '{}' missing probability field.".format(qid))
                p_true = max(0.0, min(1.0, float(raw_p)))
                probs = {"true": round(p_true, 6), "false": round(1.0 - p_true, 6)}
                metrics = compute_distribution_metrics(probs)
                prov_conf = ans.get("confidence")
                ordered_answers[qid] = {
                    "type": "noul",
                    "value": p_true >= 0.5,
                    "probability": round(p_true, 6),
                    "probabilities": probs,
                    "provider_confidence": float(prov_conf) if prov_conf is not None else None,
                    "confidence": metrics["concentration"],
                    "margin": metrics["margin"],
                }

            elif atype == "score":
                raw_score = ans.get("score")
                if raw_score is None:
                    raise DecisionError("Score answer for '{}' missing 'score' field.".format(qid))
                score_val = float(raw_score)
                raw_probs = ans.get("probabilities")
                if isinstance(raw_probs, list):
                    probs = {}
                    for idx, item in enumerate(raw_probs):
                        if isinstance(item, dict):
                            key_name = str(item.get("index", item.get("label", idx)))
                            probs[key_name] = float(item.get("probability", 0.0))
                        else:
                            probs[str(idx)] = float(item)
                elif isinstance(raw_probs, dict):
                    probs = {str(k): float(v) for k, v in raw_probs.items()}
                else:
                    probs = None

                metrics = compute_distribution_metrics(probs)
                prov_conf = ans.get("confidence")
                prov_conf_f = float(prov_conf) if prov_conf is not None else None
                ordered_answers[qid] = {
                    "type": "score",
                    "value": round(score_val, 6),
                    "probability": metrics["top_prob"],
                    "probabilities": probs,
                    "legend": ans.get("legend"),
                    "provider_confidence": prov_conf_f,
                    "confidence": metrics["concentration"] if probs else prov_conf_f,
                    "margin": metrics["margin"],
                }

            elif atype == "box":
                box_val = ans.get("box")
                if not isinstance(box_val, dict):
                    raise DecisionError("Box answer for '{}' missing 'box' object.".format(qid))
                prov_conf = ans.get("confidence")
                prov_conf_f = float(prov_conf) if prov_conf is not None else None
                ordered_answers[qid] = {
                    "type": "box",
                    "value": box_val,
                    "probability": None,
                    "probabilities": None,
                    "provider_confidence": prov_conf_f,
                    "confidence": prov_conf_f,
                    "margin": None,
                }

            else:
                ordered_answers[qid] = {
                    "type": "refusal",
                    "value": None,
                    "probability": None,
                    "probabilities": None,
                    "provider_confidence": None,
                    "confidence": None,
                    "margin": None,
                }
        except DecisionError:
            raise
        except (TypeError, ValueError) as exc:
            raise DecisionError(
                "Malformed answer fields on question '{}': {}".format(qid, exc)
            ) from exc

    resolved_model = body.get("model", model)
    usage = normalize_usage(body, service, resolved_model)

    return {
        "id": body.get("id"),
        "model": resolved_model,
        "provider": body.get("provider", service),
        "answers": ordered_answers,
        "usage": usage,
    }


class DM:
    """
    Unified interface for structured Decision Models across providers.

    ``DM`` is the System-One counterpart to ``LLM`` and ``EMBED`` in ThoughtFlow's
    Intelligence layer. Pass a ``DM`` directly to ``DECIDE(llm=dm, ...)`` (or
    ``DECIDE(model=dm, ...)``) for single-pass calibrated routing, binary
    gating, rubric scoring, or multi-question triage, or invoke ``dm.call(...)``
    (or ``dm(...)``) directly from Python.

    Attributes:
        service (str): Provider prefix (e.g. ``'openrouter'``, ``'typesafe'``,
            ``'openai'``, ``'liquid'``, ``'cloudflare'``, ``'ollama'``).
        model (str): Provider model slug (e.g. ``'typesafe/jev-1.14'``).
        api_key (str): API key for bearer authentication.
        default_params (dict): Default wire/transport params merged on each call.
        last_params (dict): Merged parameters from the most recent call.
        last_usage (dict or None): Normalized usage dict from the most recent call.
        last_error (str or None): Error message from the most recent failed call.

    Example:
        >>> from thoughtflow import DM, DECIDE, MEMORY
        >>> dm = DM("openrouter:typesafe/jev-1.14", key="sk-or-...")
        >>> route = DECIDE(
        ...     name="route",
        ...     model=dm,
        ...     choices={"billing": "Invoices and charges", "tech": "Product bugs"},
        ...     prompt="Route this ticket: {last_user_msg}",
        ... )
        >>> mem = MEMORY()
        >>> mem.add_msg("user", "I was charged twice for my plan.")
        >>> mem = route(mem)
        >>> mem.get_var("route_result")
        'billing'
    """

    is_decision_model = True

    def __init__(self, model_id="", key="API_KEY", secret="API_SECRET", **kwargs):
        """
        Initialize a DM instance with a ``service:model`` identifier and credentials.

        Args:
            model_id (str): Provider and model in ``'service:model'`` format.
                Examples: ``'openrouter:typesafe/jev-1.14'``, ``'openai:gpt-6-luna'``,
                ``'typesafe:jev-1.14'``, ``'liquid:d1.2'``, ``'ollama:d3:4b'``.
                Bare slugs without ``':'`` default to the ``'openrouter'`` service
                (and empty ``model_id`` defaults to ``'openrouter:typesafe/jev-1.14'``).
            key (str): API key for authentication (optional for local ``ollama``/``vllm``).
            secret (str): Optional API secret for symmetry with ``LLM`` / ``EMBED``.
            **kwargs: Optional configuration:
                - ``request_timeout`` (float): Socket timeout in seconds (default 60).
                - ``on_usage`` (callable): Hook ``fn(usage_dict)`` invoked after each call.
                - ``record`` (MEMORY): Start recording ``'decide'`` exchanges immediately.
                - ``dialect`` (str): Override wire dialect for custom gateways.
                - Transport keys (``base_url``, ``extra_headers``, ``referer``, ``title``,
                  ``ollama_url``, ``account_id``) and provider wire fields.
        """
        if not model_id:
            model_id = "openrouter:typesafe/jev-1.14"
        elif ":" not in model_id:
            model_id = "openrouter:" + model_id

        service, model = model_id.split(":", 1)
        self.service = service
        self.model = model
        self.api_key = key
        self.api_secret = secret

        self._record_memory = kwargs.pop("record", None)
        self.request_timeout = kwargs.pop("request_timeout", 60)
        self.on_usage = kwargs.pop("on_usage", None)
        self.dialect = kwargs.pop("dialect", None)
        self._backing_llm = kwargs.pop("backing_llm", None)

        self.default_params = {}
        for k, v in kwargs.items():
            if k in _DM_RESERVED_KEYS:
                continue
            if v is not None:
                self.default_params[k] = v

        self.last_params = {}
        self.last_usage = None
        self.last_error = None
        self._lock = threading.Lock()

    def __call__(self, state, questions, params=None):
        """Allow invoking ``dm(state, questions, params)`` directly like ``LLM`` and ``EMBED``."""
        return self.call(state, questions, params=params)

    @classmethod
    def from_llm(cls, llm, **kwargs):
        """
        Adapt any generative ``LLM`` (or ``ReplayLLM``) to the ``DM`` interface.

        Useful when developing offline with scripted models or deploying the same
        decision workflow against a provider that offers chat models only.
        Returned answers carry ``probabilities=None`` and ``provider_confidence=None``
        so callers never mistake generative labels for calibrated System-One probabilities.

        Args:
            llm: A ThoughtFlow ``LLM`` (or duck-typed object with ``.call(msgs)``).
            **kwargs: Optional ``DM`` kwargs (e.g. ``record=memory``, ``on_usage=...``).

        Returns:
            DM: Adapter instance with ``dialect='llm_fallback'``.
        """
        svc = getattr(llm, "service", "llm") or "llm"
        mdl = getattr(llm, "model", "chat") or "chat"
        return cls(
            model_id="{}:{}".format(svc, mdl),
            key="",
            dialect="llm_fallback",
            backing_llm=llm,
            **kwargs,
        )

    def record(self, memory):
        """
        Record every decision exchange into ``memory`` under ``kind='decide'``.

        Args:
            memory: A ``MEMORY`` instance, or ``None`` to stop recording.

        Returns:
            DM: ``self`` for chaining.
        """
        self._record_memory = memory
        return self

    @classmethod
    def replay(cls, memory, on_miss="raise", model_id=None, **kwargs):
        """
        Build a deterministic ``ReplayDM`` from recorded ``'decide'`` exchanges.

        Args:
            memory: ``MEMORY`` containing recorded ``'decide'`` exchanges.
            on_miss: ``'raise'`` (default) to raise ``ReplayMissError`` on an
                unrecorded request, or a live ``DM`` instance to fall back to.
            model_id: ``'service:model'`` to replay as when ``memory`` holds
                recordings from multiple decision models.
            **kwargs: Optional ``DM`` defaults (e.g. wire ``default_params`` or
                ``on_usage=...``) forwarded to ``ReplayDM``.

        Returns:
            ReplayDM
        """
        return ReplayDM(memory, on_miss=on_miss, model_id=model_id, **kwargs)

    def _request_signature(self, state, canonical_questions, wire_params):
        """Build the transport-independent ``(key, request)`` pair for record/replay."""
        clean_params = {
            k: v for k, v in wire_params.items() if k not in TRANSPORT_PARAM_KEYS
        }
        request = {
            "state": state,
            "questions": canonical_questions,
            "params": clean_params,
        }
        key = exchange_key(self.service, self.model, request)
        return key, request

    def _resolve_endpoint_and_dialect(self, transport, wire_params, canonical_questions):
        """Resolve ``(url, headers, dialect)`` for the configured service and transport."""
        profile = PROVIDER_DECISION_PROFILES.get(self.service)
        if profile is None:
            if not (transport.get("base_url") and self.dialect):
                raise ValueError(
                    "Unsupported decision service '{}'. Supported services: {}. "
                    "For custom gateways, supply both base_url= and dialect=.".format(
                        self.service,
                        ", ".join(sorted(PROVIDER_DECISION_PROFILES)),
                    )
                )
            default_url, default_dialect = None, self.dialect
        else:
            default_url, default_dialect = profile

        dialect = self.dialect or default_dialect

        if transport.get("base_url"):
            url = transport["base_url"]
        elif self.service == "ollama" and transport.get("ollama_url"):
            url = transport["ollama_url"].rstrip("/") + "/v1/systemone"
        elif self.service == "cloudflare":
            account_id = transport.get("account_id")
            if not account_id:
                raise ValueError(
                    "Cloudflare Workers AI DM requires account_id= or an explicit base_url=."
                )
            url = "https://api.cloudflare.com/client/v4/accounts/{}/ai/run/{}".format(
                account_id, self.model
            )
        else:
            url = default_url

        headers = {"Content-Type": "application/json"}
        keyless_local = self.service in ("ollama", "vllm") and self.api_key in ("", "API_KEY", None)
        if self.api_key and not keyless_local:
            headers["Authorization"] = "Bearer " + self.api_key

        if self.service == "openrouter":
            if transport.get("referer"):
                headers["HTTP-Referer"] = transport["referer"]
            if transport.get("title"):
                headers["X-Title"] = transport["title"]

        if self.service == "typesafe":
            uses_images = "assets" in wire_params or any(
                q.get("type") == "box" for q in canonical_questions.values()
            )
            if uses_images:
                headers["TypeSafe-Danger-Zone-Images"] = "true"

        if transport.get("extra_headers"):
            headers.update(transport["extra_headers"])

        return url, headers, dialect

    def call(self, state, questions, params=None):
        """
        Evaluate one or more typed questions over ``state``.

        Args:
            state: Context to evaluate (string, dict, or list of content/media parts).
            questions (dict): Map of ``question_id -> spec`` (``choice``, ``noul``,
                ``score``, or ``box``).
            params (dict, optional): Per-call transport or wire parameter overrides.

        Returns:
            dict: Normalized decision response with ``answers``, ``usage``,
                ``model``, ``provider``, and ``id``.

        Raises:
            ValueError: On invalid question specs or unsupported service configuration.
            DecisionError: On HTTP, network, or malformed wire responses.
        """
        merged = merge_call_params(self.default_params, params)
        wire_params, transport = split_call_params(merged)
        self.last_params = dict(merged)
        self.last_error = None

        canonical_q = normalize_questions_spec(questions)
        sig_key, sig_req = self._request_signature(state, canonical_q, wire_params)

        try:
            if self.dialect == "llm_fallback" or self._backing_llm is not None:
                result = self._call_llm_fallback(state, canonical_q, merged)
            else:
                url, headers, resolved_dialect = self._resolve_endpoint_and_dialect(
                    transport, wire_params, canonical_q
                )
                payload = build_wire_payload(
                    resolved_dialect, self.model, state, canonical_q, wire_params
                )
                raw = self._send_request(url, payload, headers)
                result = parse_wire_response(
                    resolved_dialect, raw, canonical_q, self.service, self.model
                )
        except DecisionError as exc:
            self.last_error = str(exc)
            raise

        usage = result.get("usage")
        self.last_usage = usage
        if self.on_usage and callable(self.on_usage) and usage:
            self.on_usage(dict(usage))

        if self._record_memory is not None:
            with self._lock:
                self._record_memory.add_exchange(
                    kind="decide",
                    key=sig_key,
                    service=self.service,
                    model=self.model,
                    request=copy.deepcopy(sig_req),
                    response=[copy.deepcopy(result)],
                )

        return result

    def _send_request(self, url, payload, headers):
        """POST JSON via stdlib ``urllib`` and raise ``DecisionError`` on failure."""
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        timeout = self.request_timeout
        open_kwargs = {"timeout": timeout} if timeout is not None else {}

        try:
            with urllib.request.urlopen(req, **open_kwargs) as resp:
                raw_text = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body_text = ""
            try:
                body_text = exc.read().decode("utf-8", errors="replace")
            except Exception:
                body_text = str(exc)
            msg = "Decision request failed with HTTP {}: {}".format(
                exc.code, body_text[:400]
            )
            self.last_error = msg
            raise DecisionError(
                msg,
                status=exc.code,
                body=body_text[:500],
                retryable=(exc.code in _RETRYABLE_STATUSES),
            ) from exc
        except Exception as exc:
            msg = "Decision transport error: {}".format(exc)
            self.last_error = msg
            raise DecisionError(msg, status=None, body="", retryable=True) from exc

        try:
            return json.loads(raw_text)
        except json.JSONDecodeError as exc:
            msg = "Decision endpoint returned invalid JSON: {}".format(raw_text[:200])
            self.last_error = msg
            raise DecisionError(msg, status=200, body=raw_text[:500], retryable=False) from exc

    def _call_llm_fallback(self, state, canonical_q, call_params):
        """Execute ``canonical_q`` over a backing generative ``LLM`` via JSON prompt."""
        if self._backing_llm is None:
            raise DecisionError("DM configured with dialect='llm_fallback' has no backing_llm.")

        schema_hint = {}
        for qid, q in canonical_q.items():
            qtype = q["type"]
            if qtype == "choice":
                schema_hint[qid] = {
                    "type": "choice",
                    "allowed_choices": q["criteria"],
                    "instructions": q.get("instructions", ""),
                }
            elif qtype == "noul":
                schema_hint[qid] = {
                    "type": "noul",
                    "range": "float probability 0.0 to 1.0 that condition is true",
                    "instructions": q.get("instructions", ""),
                    "criteria": q.get("criteria"),
                }
            elif qtype == "score":
                schema_hint[qid] = {
                    "type": "score",
                    "range": "float index from 0.0 to {}.0".format(len(q["criteria"]) - 1),
                    "levels": q["criteria"],
                    "instructions": q.get("instructions", ""),
                }
            else:
                raise ValueError(
                    "DM.from_llm fallback does not support question type {!r}.".format(qtype)
                )

        prompt = (
            "Evaluate STATE against every question in QUESTIONS and respond with ONLY a "
            "JSON object mapping each question key to its typed answer:\n"
            '- For "choice": {"type": "choice", "choice": "<exact allowed key>"}\n'
            '- For "noul": {"type": "noul", "noul": <float between 0.0 and 1.0>}\n'
            '- For "score": {"type": "score", "score": <float level index>}\n\n'
            "STATE:\n"
            + json.dumps(state, ensure_ascii=False, default=str)
            + "\n\nQUESTIONS:\n"
            + json.dumps(schema_hint, ensure_ascii=False, default=str)
        )

        msgs = [{"role": "user", "content": prompt}]
        llm_params = {
            k: v for k, v in call_params.items() if k not in TRANSPORT_PARAM_KEYS
        }
        replies = (
            self._backing_llm.call(msgs, llm_params)
            if hasattr(self._backing_llm, "call")
            else self._backing_llm(msgs)
        )
        raw_text = replies[0] if isinstance(replies, list) and replies else str(replies or "")
        if not raw_text.strip():
            llm_err = getattr(self._backing_llm, "last_error", None)
            if llm_err:
                raise DecisionError(
                    "Backing LLM call failed: {}".format(llm_err),
                    retryable=True,
                )
            raise DecisionError("Backing LLM returned an empty response.", retryable=True)

        json_str = extract_balanced_json(raw_text.strip())
        if not json_str:
            raise DecisionError(
                "Backing LLM fallback did not return valid JSON: {!r}".format(raw_text[:200]),
                retryable=True,
            )

        try:
            parsed_answers = json.loads(json_str)
        except json.JSONDecodeError as exc:
            raise DecisionError(
                "Backing LLM fallback returned malformed JSON: {}".format(exc),
                retryable=True,
            ) from exc

        if not isinstance(parsed_answers, dict):
            raise DecisionError(
                "Backing LLM fallback must return a JSON object keyed by question ID, got {}.".format(
                    type(parsed_answers).__name__
                ),
                retryable=True,
            )

        normalized_answers = {}
        for qid, q in canonical_q.items():
            ans = parsed_answers.get(qid)
            if not isinstance(ans, dict):
                raise DecisionError(
                    "Backing LLM fallback omitted answer object for question '{}'.".format(qid),
                    retryable=True,
                )
            entry = dict(ans)
            if "type" not in entry and entry.get("type") != "refusal":
                entry["type"] = q["type"]

            if entry.get("type") == "choice":
                picked = entry.get("choice")
                if picked not in q["criteria"]:
                    raise DecisionError(
                        "Backing LLM returned disallowed choice {!r} for '{}'.".format(picked, qid),
                        retryable=True,
                    )
            normalized_answers[qid] = entry

        backing_usage = getattr(self._backing_llm, "last_usage", None)
        synthetic_body = {
            "model": self.model,
            "provider": self.service,
            "answers": normalized_answers,
            "usage": backing_usage or {},
        }
        try:
            return parse_wire_response(
                "systemone", synthetic_body, canonical_q, self.service, self.model
            )
        except DecisionError as exc:
            exc.retryable = True
            raise

    def __str__(self):
        """Return concise string representation."""
        return "DM({}:{})".format(self.service, self.model)

    def __repr__(self):
        """Return detailed string representation."""
        return "DM(service='{}', model='{}')".format(self.service, self.model)


class ReplayDM(DM):
    """
    A ``DM`` that serves recorded decision responses offline from ``MEMORY``.

    Mirrors ``ReplayLLM`` and ``ReplayEMBED``: matches requests by content hash
    (excluding transport-only parameters), advances a thread-safe per-key cursor
    when identical requests were recorded multiple times, and deep-copies outputs
    so caller mutation cannot corrupt stored recordings.
    """

    def __init__(self, memory, on_miss="raise", model_id=None, **kwargs):
        """
        Args:
            memory: ``MEMORY`` containing recorded ``'decide'`` exchanges.
            on_miss: ``'raise'`` (default) to raise ``ReplayMissError``, or a
                live ``DM`` instance to fall back to on unrecorded requests.
            model_id: ``'service:model'`` to replay as when ``memory`` holds
                recordings from multiple decision models.
            **kwargs: Optional ``DM`` kwargs (e.g. ``on_usage=...``).
        """
        from thoughtflow.llm import ReplayMissError

        self._miss_error = ReplayMissError
        exchanges = memory.get_exchanges(kind="decide")

        identities = {(e.get("service"), e.get("model")) for e in exchanges}
        if model_id is not None:
            if ":" in model_id:
                service, model = model_id.split(":", 1)
            else:
                service, model = "openrouter", model_id
        elif len(identities) == 1:
            service, model = next(iter(identities))
        elif len(identities) == 0:
            service, model = "replay", "empty"
        else:
            raise ValueError(
                "Memory contains decision recordings from multiple models ({}). "
                "Pass model_id='service:model' to choose one.".format(
                    ", ".join(sorted("{}:{}".format(s, m) for s, m in identities))
                )
            )

        super().__init__(model_id="{}:{}".format(service, model), key="replay", **kwargs)
        self.on_miss = on_miss

        self._responses = {}
        self._cursor = {}
        for ex in exchanges:
            if (ex.get("service"), ex.get("model")) != (service, model):
                continue
            resp_list = ex.get("response") or []
            if resp_list:
                self._responses.setdefault(ex["key"], []).append(resp_list[0])
                self._cursor[ex["key"]] = 0

    def call(self, state, questions, params=None):
        """Serve the recorded decision response matching ``(state, questions, params)``."""
        merged = merge_call_params(self.default_params, params)
        wire_params, _transport = split_call_params(merged)
        self.last_params = dict(merged)

        canonical_q = normalize_questions_spec(questions)
        key, _req = self._request_signature(state, canonical_q, wire_params)

        with self._lock:
            recorded = self._responses.get(key)
            if recorded is not None:
                idx = min(self._cursor[key], len(recorded) - 1)
                self._cursor[key] += 1
                payload = copy.deepcopy(recorded[idx])
            else:
                payload = None

        if payload is None:
            if self.on_miss == "raise" or self.on_miss is None:
                raise self._miss_error(
                    "No recorded decision for this request (key={}). "
                    "Re-record the session, or construct ReplayDM with "
                    "on_miss=<live DM> to fall back.".format(key)
                )
            return self.on_miss.call(state, questions, params=params)

        self.last_error = None
        self.last_usage = payload.get("usage")
        if self.on_usage and callable(self.on_usage) and self.last_usage:
            self.on_usage(dict(self.last_usage))
        return payload
