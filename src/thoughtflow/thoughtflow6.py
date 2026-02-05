
DeveloperContext = """

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

ThoughtFlow is designed to be a sophisticated AI agent framework for building 
intelligent, memory-aware systems that can think, act, and maintain persistent 
state. 

---


# Thoughtflow — Design Document (Plain-English Spec for a Single-File Base Implementation)

This document explains **exactly** how to engineer Thoughtflow in simple, idiomatic Python. It is meant to live at the top of a *single Python script* that defines the foundational classes and helper functions. It is written for a reader with **zero** prior exposure to Thoughtflow.

Thoughtflow is a **Pythonic cognitive engine**. You write ordinary Python—`for`/`while`, `if/elif/else`, `try/except`, and small classes—no graphs, no hidden DSLs. A *flow* is "just a function" that accepts a `MEMORY` object and returns that same `MEMORY` object, modified. Cognition is built from four primitives:

1. **LLM** — A tiny wrapper around a chat-style language model API.
2. **MEMORY** — The single state container that keeps messages, events, logs, reflections, and variables.
3. **THOUGHT** — The unit of cognition: Prompt + Context + LLM + Parsing + Validation (+ Retries + Logging).
4. **ACTION** — Anything the agent *does* (respond, call an HTTP API, write a file, query a vector store, etc.), with consistent logging.

The rest of this spec describes **design philosophy**, **object contracts**, **method/attribute lists**, **data conventions**, and **how everything fits together**—plus example usage that the finished library should support.

---

Final Notes on Style

* Keep constructors short and forgiving; let users pass just a few arguments.
* Prefer small, pure helpers (parsers/validators) over big class hierarchies.
* Do not hide failures; always leave a visible trace in `logs` and `events`.
* Default behaviors should serve 90% of use cases; exotic needs belong in user code.

"""

#############################################################################
#############################################################################

### IMPORTS AND SETTINGS

import os, sys, time, pickle, json, uuid
import http, urllib, socket, ssl, gzip, copy
import urllib.request
import pprint 
import random
import re, ast
from typing import Mapping, Any, Iterable, Optional, Tuple, Union

import time,hashlib,pickle
from random import randint
from functools import reduce

import datetime as dtt
from zoneinfo import ZoneInfo

tz_bog = ZoneInfo("America/Bogota")
tz_utc = ZoneInfo("UTC")


#############################################################################
#############################################################################

### EVENT STAMP LOGIC

class EventStamp:
    """
    Generates and decodes deterministic event stamps using Base62 encoding.
    
    Event stamps combine encoded time, document hash, and random components
    into a compact 16-character identifier.
    
    Usage:
        EventStamp.stamp()           # Generate a new stamp
        EventStamp.decode_time(s)    # Decode timestamp from stamp
        EventStamp.hashify("text")   # Generate deterministic hash
    """
    
    CHARSET = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
    
    def sha256_hash(input_string):
        """Generate a SHA-256 hash and return it as an integer."""
        hash_bytes = hashlib.sha256(input_string.encode("utf-8")).digest()
        return int.from_bytes(hash_bytes, byteorder="big")
    
    def base62_encode(number, length):
        """Encode an integer into a fixed-length Base62 string."""
        base = len(EventStamp.CHARSET)
        encoded = []
        for _ in range(length):
            number, remainder = divmod(number, base)
            encoded.append(EventStamp.CHARSET[remainder])
        return ''.join(encoded[::-1])  # Reverse to get correct order
    
    def hashify(input_string, length=32):
        """Generate a deterministic hash using all uppercase/lowercase letters and digits."""
        hashed_int = EventStamp.sha256_hash(input_string)
        return EventStamp.base62_encode(hashed_int, length)
    
    def encode_num(num, charset=None):
        """Encode a number in the given base/charset."""
        if charset is None:
            charset = EventStamp.CHARSET
        base = len(charset)
        if num < base:
            return charset[num]
        else:
            return EventStamp.encode_num(num // base, charset) + charset[num % base]
    
    def decode_num(encoded_str, charset=None):
        """Decode a base-encoded string back to an integer."""
        if charset is None:
            charset = EventStamp.CHARSET
        base = len(charset)
        char_to_value = {c: i for i, c in enumerate(charset)}
        return reduce(lambda num, c: num * base + char_to_value[c], encoded_str, 0)
    
    def encode_time(unix_time=0):
        """Encode current or given unix time."""
        if unix_time == 0:
            t = int(time.time() * 10000)
        else:
            t = int(unix_time * 10000)
        return EventStamp.encode_num(t)
    
    def encode_doc(doc={}):
        """Encode a document/value to a 5-character hash."""
        return EventStamp.hashify(str(doc), 5)
    
    def encode_rando(length=3):
        """Generate a random code of specified length."""
        n = randint(300000, 900000)
        c = '000' + EventStamp.encode_num(n)
        return c[-length:]
    
    def stamp(doc={}):
        """
        Generate an event stamp.
        
        Combines encoded time, document hash, and random component
        into a 16-character identifier.
        """
        time_code = EventStamp.encode_time()
        rando_code = EventStamp.encode_rando()
        if len(str(doc)) > 2:
            doc_code = EventStamp.encode_doc(doc)
        else:
            arb = time_code + rando_code
            doc_code = EventStamp.encode_doc(arb)
        return (time_code + doc_code + rando_code)[:16]
    
    def decode_time(stamp, charset=None):
        """Decode the time component from an event stamp."""
        if charset is None:
            charset = EventStamp.CHARSET
        stamp_prefix = stamp[:8]
        scaled_time = EventStamp.decode_num(stamp_prefix, charset)
        unix_time_seconds = scaled_time / 10000
        return unix_time_seconds


# Backwards compatibility aliases
event_stamp = EventStamp.stamp
hashify = EventStamp.hashify
encode_num = EventStamp.encode_num
decode_num = EventStamp.decode_num 

#############################################################################
#############################################################################

### HELPER FUNCTIONS


default_header = '''
Markers like <start … l4zk> and </end … l4zk> 
indicate where a text section begins and ends.
Never mix boundaries. Each block is separate. 
This is to improve your ease-of-reading.
'''

def construct_prompt(
    prompt_obj = {},
    order = [],
    header = '',
    ):
    if order: sections = list(order) 
    else: sections = [a for a in prompt_obj]
    rnum = str(randint(1,9))
    stamp = event_stamp()[-4:].lower() 
    stamp = stamp[:2]+rnum+stamp[2:]
    L = []
    if header: 
        if header=='default': 
            L.append(default_header+'\n')
        else: 
            L.append(header+'\n\n')  
    L.append('<start prompt stamp>\n\n') 
    for s in sections:
        text = prompt_obj[s]
        s2 = s.strip().replace(' ','_')  
        label1 = "<start "+s2+" stamp>\n"
        label2 = "\n</end "+s2+" stamp>\n\n"
        block = label1 + text + label2
        L.append(block) 
    L.append('</end prompt stamp>')
    prompt = ''.join(L).replace(' stamp>',' '+stamp+'>')  
    return prompt 

def construct_msgs(
    usr_prompt = '',
    vars       = {},
    sys_prompt = '',
    msgs       = [],
    ):
    if sys_prompt:
        if type(sys_prompt)==dict:
            sys_prompt = construct_prompt(sys_prompt) 
        m = {'role':'system','content':sys_prompt} 
        msgs.insert(0,m) 
    if usr_prompt:
        if type(usr_prompt)==dict:
            usr_prompt = construct_prompt(usr_prompt) 
        m = {'role':'user','content':usr_prompt} 
        msgs.append(m) 
    #msgs2 = [] 
    #for m in msgs:
    #    m_copy = m.copy()
    #    if isinstance(m_copy, dict) and 'content' in m_copy and isinstance(m_copy['content'], str):
    #        for k, v in vars.items():
    #            m_copy['content'] = m_copy['content'].replace(k, str(v))
    #    msgs2.append(m_copy) 
    #return msgs2
    msgs2 = []
    for m in msgs:
        m_copy = dict(m)
        if isinstance(m_copy.get("content"), str):
            for k, v in vars.items():
                m_copy["content"] = m_copy["content"].replace(k, str(v))
        msgs2.append(m_copy)
    return msgs2



#############################################################################


class ValidExtractError(ValueError):
    """Raised when extraction or validation fails."""

def valid_extract(raw_text: str, parsing_rules: Mapping[str, Any]) -> Any:
    """
    Extract and validate a target Python structure from noisy LLM text.

    Parameters
    ----------
    raw_text : str
        The original model output (may include extra prose, code fences, etc.).
    parsing_rules : dict
        Rules controlling extraction/validation. Required keys:
          - 'kind': currently supports 'python' (default). ('json' also supported.)
          - 'format': schema describing the expected structure, e.g. [], {}, {'name': ''}, {'num_list': [], 'info': {}}

        Schema language:
          * []          : list of anything
          * [schema]    : list of items matching 'schema'
          * {}          : dict of anything
          * {'k': sch}  : dict with required key 'k' matching 'sch'
          * {'k?': sch} : OPTIONAL key 'k' (if present, must match 'sch')
          * '' or str   : str
          * 0 or int    : int
          * 0.0 or float: float
          * True/False or bool: bool
          * None        : NoneType

    Returns
    -------
    Any
        The parsed Python object that satisfies the schema.

    Raises
    ------
    ValidExtractError
        If extraction fails or the parsed object does not validate against the schema.

    Examples
    --------
    >>> rules = {'kind': 'python', 'format': []}
    >>> txt = "Here you go:\\n```python\\n[1, 2, 3]\\n```\\nLet me know!"
    >>> valid_extract(txt, rules)
    [1, 2, 3]

    >>> rules = {'kind': 'python', 'format': {'num_list': [], 'my_info': {}, 'name': ''}}
    >>> txt = "noise { 'num_list':[1,2], 'my_info':{'x':1}, 'name':'Ada' } trailing"
    >>> valid_extract(txt, rules)
    {'num_list': [1, 2], 'my_info': {'x': 1}, 'name': 'Ada'}
    """
    if not isinstance(parsing_rules, Mapping):
        raise ValidExtractError("parsing_rules must be a mapping.")

    kind = parsing_rules.get("kind", "python")
    schema = parsing_rules.get("format", None)
    if schema is None:
        raise ValidExtractError("parsing_rules['format'] is required.")

    # 1) Collect candidate text segments in a robust order.
    candidates: Iterable[str] = _candidate_segments(raw_text, schema, prefer_fences_first=True)

    last_err: Optional[Exception] = None
    for segment in candidates:
        try:
            obj = _parse_segment(segment, kind=kind)
        except Exception as e:
            last_err = e
            continue

        ok, msg = _validate_schema(obj, schema)
        if ok:
            return obj
        last_err = ValidExtractError("Validation failed for candidate: {}".format(msg))

    # If we got here, nothing parsed+validated.
    if last_err:
        raise ValidExtractError(str(last_err))
    raise ValidExtractError("No parseable candidates found.")

# ----------------------------
# Parsing helpers
# ----------------------------

# --- Replace the fence regex with this (accepts inline fences) ---
_FENCE_RE = re.compile(
    r"```(?P<lang>[a-zA-Z0-9_\-\.]*)\s*\n?(?P<body>.*?)```",
    re.DOTALL
)

def _candidate_segments(raw_text: str, schema: Any, prefer_fences_first: bool = True) -> Iterable[str]:
    """
    Yield candidate substrings likely to contain the target structure.

    Strategy:
      1) Fenced code blocks (```) first, in order, if requested.
      2) Balanced slice for the top-level delimiter suggested by the schema.
      3) As a fallback, return raw_text itself (last resort).
    """
    # 1) From code fences
    if prefer_fences_first:
        for m in _FENCE_RE.finditer(raw_text):
            lang = (m.group("lang") or "").strip().lower()
            body = m.group("body")
            # If the fence declares "python" or "json", prioritize; otherwise still try.
            yield body

    # 2) From balanced slice based on schema's top-level delimiter
    opener, closer = _delims_for_schema(schema)
    if opener and closer:
        slice_ = _balanced_slice(raw_text, opener, closer)
        if slice_ is not None:
            yield slice_

    # 3) Whole text (very last resort)
    yield raw_text

def _parse_segment(segment: str, kind: str = "python") -> Any:
    """
    Parse a segment into a Python object according to 'kind'.
    - python: ast.literal_eval
    - json: json.loads (with fallback: try literal_eval if JSON fails, for LLM single-quote dicts)
    """
    text = segment.strip()

    if kind == "python":
        # Remove leading language hints often kept when copying from fences
        if text.startswith("python\n"):
            text = text[len("python\n") :].lstrip()
        return ast.literal_eval(text)

    if kind == "json":
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # LLMs often return Python-style dicts (single quotes). Try literal_eval as a fallback.
            return ast.literal_eval(text)

    raise ValidExtractError("Unsupported kind: {!r}".format(kind))

def _delims_for_schema(schema: Any) -> Tuple[Optional[str], Optional[str]]:
    """
    Infer top-level delimiters from the schema.
    - list-like → [ ]
    - dict-like → { }
    - tuple-like (if used) → ( )
    - string/number/bool/None → no delimiters (None, None)
    """
    # list
    if isinstance(schema, list):
        return "[", "]"
    # dict
    if isinstance(schema, dict):
        return "{", "}"
    # tuple schema (rare, but supported)
    if isinstance(schema, tuple):
        return "(", ")"
    # primitives: cannot infer a unique delimiter—return None
    return None, None


def _balanced_slice(text: str, open_ch: str, close_ch: str) -> Optional[str]:
    """
    Return the first balanced substring between open_ch and close_ch,
    scanning from the *first occurrence of open_ch* (so prose apostrophes
    before the opener don't confuse quote tracking).
    """
    start = text.find(open_ch)
    if start == -1:
        return None

    depth = 0
    in_str: Optional[str] = None  # quote char if inside ' or "
    escape = False
    i = start

    while i < len(text):
        ch = text[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == in_str:
                in_str = None
        else:
            if ch in ("'", '"'):
                in_str = ch
            elif ch == open_ch:
                depth += 1
            elif ch == close_ch and depth > 0:
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
        i += 1
    return None


# ----------------------------
# Schema validation
# ----------------------------

def _is_optional_key(k: str) -> Tuple[str, bool]:
    """Return (base_key, optional_flag) for keys with a trailing '?'."""
    if isinstance(k, str) and k.endswith("?"):
        return k[:-1], True
    return k, False

def _schema_type(schema: Any) -> Union[type, Tuple[type, ...], None]:
    """
    Map schema exemplars to Python types.
    Accepts either exemplar values ('' -> str, 0 -> int, 0.0 -> float, True -> bool, None -> NoneType)
    OR actual types (str, int, float, bool).
    """
    if schema is None:
        return type(None)
    if schema is str or isinstance(schema, str):
        return str
    if schema is int or (isinstance(schema, int) and not isinstance(schema, bool)):
        return int
    if schema is float or isinstance(schema, float):
        return float
    if schema is bool or isinstance(schema, bool):
        return bool
    if schema is list:
        return list
    if schema is dict:
        return dict
    if schema is tuple:
        return tuple
    return None  # composite or unknown marker

def _validate_schema(obj: Any, schema: Any, path: str = "$") -> Tuple[bool, str]:
    """
    Recursively validate 'obj' against 'schema'. Returns (ok, message).
    """
    # 1) Primitive types via exemplar or type
    t = _schema_type(schema)
    if t is not None and t not in (list, dict, tuple):
        if isinstance(obj, t):
            return True, "ok"
        return False, "{}: expected {}, got {}".format(path, t.__name__, type(obj).__name__)

    # 2) List schemas
    if isinstance(schema, list):
        if not isinstance(obj, list):
            return False, "{}: expected list, got {}".format(path, type(obj).__name__)
        # If schema is [], any list passes
        if len(schema) == 0:
            return True, "ok"
        # If schema is [subschema], every element must match subschema
        if len(schema) == 1:
            subschema = schema[0]
            for i, el in enumerate(obj):
                ok, msg = _validate_schema(el, subschema, "{}[{}]".format(path, i))
                if not ok:
                    return ok, msg
            return True, "ok"
        # Otherwise treat as "structure-by-position" (rare)
        if len(obj) != len(schema):
            return False, "{}: expected list length {}, got {}".format(path, len(schema), len(obj))
        for i, (el, subschema) in enumerate(zip(obj, schema)):
            ok, msg = _validate_schema(el, subschema, "{}[{}]".format(path, i))
            if not ok:
                return ok, msg
        return True, "ok"

    # 3) Dict schemas
    if isinstance(schema, dict):
        if not isinstance(obj, dict):
            return False, "{}: expected dict, got {}".format(path, type(obj).__name__)

        # Check required/optional keys in schema
        for skey, subschema in schema.items():
            base_key, optional = _is_optional_key(skey)
            if base_key not in obj:
                if optional:
                    continue
                return False, "{}: missing required key '{}'".format(path, base_key)
            ok, msg = _validate_schema(obj[base_key], subschema, "{}.{}".format(path, base_key))
            if not ok:
                return ok, msg
        return True, "ok"

    # 4) Tuple schemas (optional)
    if isinstance(schema, tuple):
        if not isinstance(obj, tuple):
            return False, "{}: expected tuple, got {}".format(path, type(obj).__name__)
        if len(schema) == 0:
            return True, "ok"
        if len(schema) == 1:
            subschema = schema[0]
            for i, el in enumerate(obj):
                ok, msg = _validate_schema(el, subschema, "{}[{}]".format(path, i))
                if not ok:
                    return ok, msg
            return True, "ok"
        if len(obj) != len(schema):
            return False, "{}: expected tuple length {}, got {}".format(path, len(schema), len(obj))
        for i, (el, subschema) in enumerate(zip(obj, schema)):
            ok, msg = _validate_schema(el, subschema, "{}[{}]".format(path, i))
            if not ok:
                return ok, msg
        return True, "ok"

    # 5) If schema is a type object (e.g., list, dict) we handled above; unknown markers:
    st = type(schema).__name__
    return False, "{}: unsupported schema marker of type {!r}".format(path, st)


ParsingExamples = """

# Examples showing how to use the valid_extract function
#------------------------------------------------------------------

# Basic list
txt = "Noise before ```python\n[1, 2, 3]\n``` noise after"
rules = {"kind": "python", "format": []}
assert valid_extract(txt, rules) == [1, 2, 3]

# Basic dict
txt2 = "Header\n{ 'a': 1, 'b': 2 }\nFooter"
rules2 = {"kind": "python", "format": {}}
assert valid_extract(txt2, rules2) == {"a": 1, "b": 2}

# Nested dict with types
txt3 = "reply: { 'num_list':[1,2,3], 'my_info':{'x':1}, 'name':'Ada' } ok."
rules3 = {"kind": "python",
            "format": {'num_list': [int], 'my_info': {}, 'name': ''}}
assert valid_extract(txt3, rules3)["name"] == "Ada"

# Optional key example
txt4 = ''' I think this is how I'd answer: ``` {'a': 1}``` is this good enough?'''
rules4 = {"kind": "python", "format": {'a': int, 'b?': ''}}
assert valid_extract(txt4, rules4) == {'a': 1}

txt = " I think this is how I'd answer: ``` {'a': 1}``` is this good enough?"
rules = {"kind": "python", "format": {"a": int, "b?": ""}}
assert valid_extract(txt, rules) == {"a": 1}

txt2 = "noise before {'a': 1} and after"
assert valid_extract(txt2, rules) == {"a": 1}

txt3 = "ok ```python\n[1,2,3]\n``` end"
assert valid_extract(txt3, {"kind": "python", "format": []}) == [1,2,3]

txt4 = "inline ```[{'k': 'v'}]```"
assert valid_extract(txt4, {"kind": "python", "format": [{"k": ""}]}) == [{"k": "v"}]

"""


#############################################################################
#############################################################################
#############################################################################


### LLM CLASS

class LLM:
    """
    The LLM class is designed to interface with various language model services.
    
    Attributes:
        service (str): The name of the service provider (e.g., 'openai', 'groq', 'anthropic').
        model (str): The specific model to be used within the service.
        api_key (str): The API key for authenticating requests.
        api_secret (str): The API secret for additional authentication.
        last_params (dict): Stores the parameters used in the last API call.

    Methods:
        __init__(model_id, key, secret):
            Initializes the LLM instance with a model ID, API key, and secret.
        
        call(msg_list, params):
            Calls the appropriate API based on the service with the given message list and parameters.
        
        _call_openai(msg_list, params):
            Sends a request to the OpenAI API with the specified messages and parameters.
        
        _call_groq(msg_list, params):
            Sends a request to the Groq API with the specified messages and parameters.
        
        _call_anthropic(msg_list, params):
            Sends a request to the Anthropic API with the specified messages and parameters.
        
        _send_request(url, data, headers):
            Helper function to send HTTP requests to the specified URL with data and headers.
    """
    def __init__(self, model_id='', key='API_KEY', secret='API_SECRET'):
        # Parse model ID and initialize service and model name
        if ':' not in model_id: model_id = 'openai:gpt-4-turbo'
        
        splitted = model_id.split(':') 
        self.service = splitted[0]
        self.model = ''.join(splitted[1:]) 
        self.api_key = key
        self.api_secret = secret
        self.last_params = {} 
        # Make the object directly callable
        self.__call__ = self.call

    def _normalize_messages(self, msg_list):
        """
        Accepts either:
        - list[str] -> converts to [{'role':'user','content': str}, ...]
        - list[dict] with 'role' and 'content' -> passes through unchanged
        - list[dict] with only 'content' -> assumes role='user'
        Returns: list[{'role': str, 'content': str or list[...]}]
        """
        norm = []
        for m in msg_list:
            if isinstance(m, dict):
                role = m.get("role", "user")
                content = m.get("content", "")
                norm.append({"role": role, "content": content})
            else:
                # treat as plain user text
                norm.append({"role": "user", "content": str(m)})
        return norm

    def call(self, msg_list, params={}):
        self.last_params = dict(params)
        # General function to call the appropriate API with msg_list and optional parameters
        if self.service == 'openai':
            return self._call_openai(msg_list, params)
        elif self.service == 'groq':
            return self._call_groq(msg_list, params)
        elif self.service == 'anthropic':
            return self._call_anthropic(msg_list, params)
        elif self.service == 'ollama':
            return self._call_ollama(msg_list, params)
        elif self.service == 'gemini':
            return self._call_gemini(msg_list, params)
        elif self.service == 'openrouter':
            return self._call_openrouter(msg_list, params)
        else:
            raise ValueError("Unsupported service '{}'.".format(self.service))

    def _call_openai(self, msg_list, params):
        url = "https://api.openai.com/v1/chat/completions"
        data = json.dumps({
            "model": self.model,
            "messages": self._normalize_messages(msg_list),
            **params
        }).encode("utf-8")
        headers = {
            "Authorization": "Bearer " + self.api_key,
            "Content-Type": "application/json",
        }
        res = self._send_request(url, data, headers)
        choices = [a["message"]["content"] for a in res.get("choices", [])]
        return choices

    def _call_groq(self, msg_list, params):
        url = "https://api.groq.com/openai/v1/chat/completions"
        data = json.dumps({
            "model": self.model,
            "messages": self._normalize_messages(msg_list),
            **params
        }).encode("utf-8")
        headers = {
            "Authorization": "Bearer " + self.api_key,
            "Content-Type": "application/json",
            "User-Agent": "Groq/Python 0.9.0",
        }
        res = self._send_request(url, data, headers)
        choices = [a["message"]["content"] for a in res.get("choices", [])]
        return choices

    def _call_anthropic(self, msg_list, params):
        url = "https://api.anthropic.com/v1/messages"
        data = json.dumps({
            "model": self.model,
            "max_tokens": params.get("max_tokens", 1024),
            "messages": self._normalize_messages(msg_list),
        }).encode("utf-8")
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        res = self._send_request(url, data, headers)
        # Anthropic returns {"content":[{"type":"text","text":"..."}], ...}
        choices = [c.get("text", "") for c in res.get("content", [])]
        return choices

    def _call_gemini(self, msg_list, params):
        """
        Calls Google Gemini/SVertexAI chat-supported models via REST API.
        Requires self.api_key to be set.
        """
        url = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent?key={}".format(self.model, self.api_key)
        # Gemini expects a list of "contents" alternating user/assistant
        # We collapse the messages into a sequence of dicts as required by Gemini
        # Gemini wants [{"role": "user/assistant", "parts": [{"text": ...}]}]
        gemini_msgs = []
        for m in self._normalize_messages(msg_list):
            # Google's role scheme: "user" or "model"
            g_role = {"user": "user", "assistant": "model", "system": "user"}.get(m["role"], "user")
            gemini_msgs.append({
                "role": g_role,
                "parts": [{"text": str(m["content"])}] if isinstance(m["content"], str) else m["content"]
            })
        payload = {
            "contents": gemini_msgs,
            **{k: v for k, v in params.items() if k != "model"}
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
        }
        res = self._send_request(url, data, headers)
        # Gemini returns { "candidates": [ { "content": { "parts": [ { "text": ... } ] } } ] }
        choices = []
        for cand in res.get("candidates", []):
            parts = cand.get("content", {}).get("parts", [])
            text = "".join([p.get("text", "") for p in parts])
            choices.append(text)
        return choices

    def _call_openrouter(self, msg_list, params):
        """
        Calls an LLM via the OpenRouter API. Requires self.api_key.
        API docs: https://openrouter.ai/docs
        Model list: https://openrouter.ai/docs#models
        """
        url = "https://openrouter.ai/api/v1/chat/completions"
        data = json.dumps({
            "model": self.model,
            "messages": self._normalize_messages(msg_list),
            **params
        }).encode("utf-8")
        headers = {
            "Authorization": "Bearer " + self.api_key,
            "Content-Type": "application/json",
            "HTTP-Referer": params.get("referer", "https://your-app.com"),
            "X-Title": params.get("title", "Thoughtflow"),
        }
        res = self._send_request(url, data, headers)
        choices = [a["message"]["content"] for a in res.get("choices", [])]
        return choices

    def _call_ollama(self, msg_list, params):
        """
        Calls a local model served via Ollama (http://localhost:11434 by default).
        Expects no authentication. Ollama messages format is like OpenAI's.
        """
        base_url = params.get("ollama_url", "http://localhost:11434")
        url = base_url.rstrip('/') + "/api/chat"
        payload = {
            "model": self.model,
            "messages": self._normalize_messages(msg_list),
            "stream": False,  # Disable streaming to get a single JSON response
            **{k: v for k, v in params.items() if k not in ("ollama_url", "model")}
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
        }
        res = self._send_request(url, data, headers)
        # Ollama returns {"message": {...}, ...} or {"choices": [{...}]}
        # Prefer OpenAI-style extraction if available, else fallback
        if "choices" in res:
            choices = [a["message"]["content"] for a in res.get("choices", [])]
        elif "message" in res:
            # single result
            msg = res["message"]
            choices = [msg.get("content", "")]
        elif "response" in res:
            # streaming/fallback
            choices = [res["response"]]
        else:
            choices = []
        return choices

    def _send_request(self, url, data, headers):
        # Sends the actual HTTP request and handles the response
        try:
            req = urllib.request.Request(url, data=data, headers=headers)
            with urllib.request.urlopen(req) as response:
                response_data = response.read().decode("utf-8")  
                # Attempt to parse JSON response; handle plain-text responses
                try:
                    return json.loads(response_data)  # Parse JSON response
                except json.JSONDecodeError:
                    # If response is not JSON, return it as-is in a structured format
                    return {"error": "Non-JSON response", "response_data": response_data}
                
        except urllib.error.HTTPError as e:
            # Return the error details in case of an HTTP error
            error_msg = e.read().decode("utf-8")
            print("HTTP Error:", error_msg)  # Log HTTP error for debugging
            return {"error": json.loads(error_msg) if error_msg else "Unknown HTTP error"}
        except Exception as e:
            return {"error": str(e)}  



#############################################################################
#############################################################################

### MEMORY CLASS

# Sentinel class to mark deleted variables
class _VarDeleted:
    """Sentinel value indicating a variable has been deleted."""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __repr__(self):
        return '<DELETED>'
    
    def __str__(self):
        return '<DELETED>'

# Singleton instance for deleted marker
VAR_DELETED = _VarDeleted()


#-----------------------------------------------------------
# Object Compression Utilities (JSON-serializable)
#-----------------------------------------------------------

import zlib
import base64

def compress_to_json(data, content_type='auto'):
    """
    Compress data to a JSON-serializable dict.
    
    Args:
        data: bytes, str, or JSON-serializable object
        content_type: 'bytes', 'text', 'json', 'pickle', or 'auto'
    
    Returns:
        dict with 'data' (base64 string), sizes, and content_type
    """
    # Convert to bytes based on type
    if content_type == 'auto':
        if isinstance(data, bytes):
            content_type = 'bytes'
            raw_bytes = data
        elif isinstance(data, str):
            content_type = 'text'
            raw_bytes = data.encode('utf-8')
        else:
            # Try JSON first, fall back to pickle
            try:
                content_type = 'json'
                raw_bytes = json.dumps(data).encode('utf-8')
            except (TypeError, ValueError):
                content_type = 'pickle'
                raw_bytes = pickle.dumps(data)
    elif content_type == 'bytes':
        raw_bytes = data
    elif content_type == 'text':
        raw_bytes = data.encode('utf-8')
    elif content_type == 'json':
        raw_bytes = json.dumps(data).encode('utf-8')
    elif content_type == 'pickle':
        raw_bytes = pickle.dumps(data)
    else:
        raise ValueError("Unknown content_type: {}".format(content_type))
    
    # Compress and base64 encode
    compressed = zlib.compress(raw_bytes, level=9)
    encoded = base64.b64encode(compressed).decode('ascii')
    
    return {
        'data': encoded,
        'size_original': len(raw_bytes),
        'size_compressed': len(compressed),
        'content_type': content_type,
    }


def decompress_from_json(obj_dict):
    """
    Decompress data from JSON-serializable dict.
    
    Args:
        obj_dict: dict from compress_to_json
    
    Returns:
        Original data in its original type
    """
    encoded = obj_dict['data']
    content_type = obj_dict['content_type']
    
    # Decode and decompress
    compressed = base64.b64decode(encoded)
    raw_bytes = zlib.decompress(compressed)
    
    # Convert back to original type
    if content_type == 'bytes':
        return raw_bytes
    elif content_type == 'text':
        return raw_bytes.decode('utf-8')
    elif content_type == 'json':
        return json.loads(raw_bytes.decode('utf-8'))
    elif content_type == 'pickle':
        return pickle.loads(raw_bytes)
    else:
        raise ValueError("Unknown content_type: {}".format(content_type))


def estimate_size(value):
    """
    Estimate the serialized size of a value in bytes.
    
    Args:
        value: Any value
        
    Returns:
        int: Estimated size in bytes
    """
    if isinstance(value, bytes):
        return len(value)
    elif isinstance(value, str):
        return len(value.encode('utf-8'))
    else:
        try:
            return len(json.dumps(value).encode('utf-8'))
        except (TypeError, ValueError):
            return len(pickle.dumps(value))


def is_obj_ref(value):
    """
    Check if a value is an object reference.
    
    Args:
        value: Any value
        
    Returns:
        bool: True if value is an object reference dict
    """
    return isinstance(value, dict) and '_obj_ref' in value


def truncate_content(content, stamp, threshold=500, header_len=200, footer_len=200):
    """
    Truncate long content by keeping header and footer with an expandable marker.
    
    If content is shorter than threshold, returns content unchanged.
    Otherwise, keeps the first header_len chars and last footer_len chars,
    with a marker in between indicating truncation and providing the stamp
    for expansion.
    
    Args:
        content: The text content to potentially truncate
        stamp: The event stamp (ID) for the content, used in expansion marker
        threshold: Minimum length before truncation applies (default 500)
        header_len: Characters to keep from start (default 200)
        footer_len: Characters to keep from end (default 200)
    
    Returns:
        str: Original content if short enough, or truncated content with marker
    
    Example:
        truncated = truncate_content(long_text, 'ABC123', threshold=500)
        # Returns: "First 200 chars...\n\n[...TRUNCATED: 1,847 chars omitted. To expand, request stamp: ABC123...]\n\n...last 200 chars"
    """
    if len(content) <= threshold:
        return content
    
    # Calculate how much we're removing
    chars_omitted = len(content) - header_len - footer_len
    
    # Build the truncation marker
    marker = "\n\n[...TRUNCATED: {:,} chars omitted. To expand, request stamp: {}...]\n\n".format(chars_omitted, stamp)
    
    # Extract header and footer
    header = content[:header_len]
    footer = content[-footer_len:]
    
    return header + marker + footer


class MEMORY:
    """
    The MEMORY class serves as an event-sourced state container for managing events, 
    logs, messages, reflections, and variables within the Thoughtflow framework. 
    
    All state changes are stored as events with sortable IDs (alphabetical = chronological).
    Events are stored in a dictionary for O(1) lookup, with separate sorted indexes for
    efficient retrieval. The memory can be fully reconstructed from its event list.

    Architecture:
        - DATA LAYER: events dict (stamp → event object) - single source of truth
        - INDEX LAYER: idx_* lists of [timestamp, stamp] pairs, sorted chronologically
        - VARIABLE LAYER: vars dict with full history as list of [stamp, value] pairs
        - OBJECT LAYER: objects dict for compressed large data storage

    Attributes:
        id (str): Unique identifier for this MEMORY instance (event_stamp).
        events (dict): Dictionary mapping event stamps to full event objects.
        idx_msgs (list): Sorted list of [timestamp, stamp] pairs for messages.
        idx_refs (list): Sorted list of [timestamp, stamp] pairs for reflections.
        idx_logs (list): Sorted list of [timestamp, stamp] pairs for logs.
        idx_vars (list): Sorted list of [timestamp, stamp] pairs for variable changes.
        idx_all (list): Master sorted list of all [timestamp, stamp] pairs.
        vars (dict): Dictionary mapping variable names to list of [stamp, value] pairs.
                     Deleted variables have VAR_DELETED as the value in their last entry.
                     Large values auto-convert to object references: {'_obj_ref': stamp}.
        var_desc_history (dict): Dictionary mapping variable names to list of [stamp, description] pairs.
                                 Tracks description evolution separately from value changes.
        objects (dict): Dictionary mapping stamps to compressed object dicts.
                        Each object is JSON-serializable with base64-encoded compressed data.
        object_threshold (int): Size threshold (bytes) for auto-converting vars to objects.
        valid_roles (set): Set of valid roles for messages.
        valid_modes (set): Set of valid modes for messages.
        valid_channels (set): Set of valid communication channels.

    Methods:
        add_msg(role, content, mode='text', channel='unknown'): Add a message event with channel.
        add_log(message): Add a log event.
        add_ref(content): Add a reflection event.
        get_msgs(...): Retrieve messages with filtering (supports channel filter).
        get_events(...): Retrieve all events with filtering.
        get_logs(limit=-1): Get log events.
        get_refs(limit=-1): Get reflection events.
        last_user_msg(): Get the last user message content.
        last_asst_msg(): Get the last assistant message content.
        last_sys_msg(): Get the last system message content.
        last_log_msg(): Get the last log message content.
        prepare_context(...): Prepare messages for LLM with smart truncation of old messages.
        set_var(key, value, desc=''): Set a variable (appends to history, auto-converts large values to objects).
        del_var(key): Mark a variable as deleted (preserves history).
        get_var(key, resolve_refs=True): Get current value (auto-resolves object refs).
        get_all_vars(resolve_refs=True): Get dict of all current non-deleted values.
        get_var_history(key, resolve_refs=False): Get full history as list of [stamp, value].
        get_var_desc(key): Get the current description of a variable.
        get_var_desc_history(key): Get full description history as list of [stamp, description].
        is_var_deleted(key): Check if a variable is currently marked as deleted.
        set_obj(data, name=None, desc='', content_type='auto'): Store compressed object, optionally link to variable.
        get_obj(stamp): Retrieve and decompress an object by stamp.
        get_obj_info(stamp): Get object metadata without decompressing.
        snapshot(): Export memory state as dict (includes events and objects).
        save(filename, compressed=False): Save memory to file (pickle format).
        load(filename, compressed=False): Load memory from file (pickle format).
        to_json(filename=None, indent=2): Export memory to JSON file or string.
        from_json(source): Class method to load memory from JSON file or string.
        copy(): Return a deep copy of the MEMORY instance.
        from_events(event_list, memory_id=None, objects=None): Class method to rehydrate from events/objects.

    Example Usage:
        memory = MEMORY()
        
        # Messages have channel tracking (for omni-directional communication)
        memory.add_msg('user', 'Hello!', channel='webapp')
        memory.add_msg('assistant', 'Hi there!', channel='webapp')
        
        # Logs and reflections are internal (no channel)
        memory.add_log('User greeted the assistant')
        memory.add_ref('User seems friendly')
        
        # Variables maintain full history (no channel needed)
        memory.set_var('foo', 42, 'A test variable')
        memory.set_var('foo', 100)  # Appends to history
        memory.get_var('foo')  # Returns 100
        memory.get_var_history('foo')  # Returns [[stamp1, 42], [stamp2, 100]]
        
        # Deletion is a tombstone, not removal
        memory.del_var('foo')
        memory.get_var('foo')  # Returns None
        memory.is_var_deleted('foo')  # Returns True
        memory.set_var('foo', 200)  # Can re-set after deletion
        
        # Large values auto-convert to compressed objects
        large_data = 'x' * 20000  # Exceeds default 10KB threshold
        memory.set_var('big_data', large_data)  # Auto-converts to object
        memory.get_var('big_data')  # Returns decompressed data
        memory.get_var('big_data', resolve_refs=False)  # Returns {'_obj_ref': stamp}
        
        # Direct object storage
        stamp = memory.set_obj(image_bytes, name='avatar', desc='User avatar')
        memory.get_var('avatar')  # Returns decompressed image_bytes
        memory.get_obj(stamp)  # Direct access by stamp
        memory.get_obj_info(stamp)  # Metadata without decompressing
        
        # Inspect internal state (public attributes)
        print(memory.events)   # All events by stamp
        print(memory.objects)  # All objects by stamp
        print(memory.vars)     # Variable histories
        
        memory.save('memory.pkl')
        memory2 = MEMORY()
        memory2.load('memory.pkl')
        
        # Export to JSON (like DataFrame.to_csv)
        memory.to_json('memory_backup.json')
        memory4 = MEMORY.from_json('memory_backup.json')
        
        # Rehydrate from events and objects (preserves all history)
        snap = memory.snapshot()
        memory3 = MEMORY.from_events(snap['events'].values(), objects=snap['objects'])
    """

    def __init__(self):
        import bisect
        self._bisect = bisect  # Store for use in methods
        
        self.id = event_stamp()
        
        # DATA LAYER: Single source of truth for all events
        self.events = {}            # stamp → full event dict
        
        # INDEX LAYER: Sorted lists of [timestamp, stamp] pairs
        # Format: [[dt_utc, stamp], ...] - aligns with Redis sorted set structure
        # Sorted by timestamp (ISO string sorts chronologically)
        self.idx_msgs = []          # Message [timestamp, stamp] pairs
        self.idx_refs = []          # Reflection [timestamp, stamp] pairs
        self.idx_logs = []          # Log [timestamp, stamp] pairs
        self.idx_vars = []          # Variable-change [timestamp, stamp] pairs
        self.idx_all  = []          # Master index (all [timestamp, stamp] pairs)
        
        # VARIABLE LAYER: Full history with timestamps
        # vars[key] = [[stamp1, value1], [stamp2, value2], ...]
        # Deleted variables have VAR_DELETED as value in their last entry
        self.vars = {}              # var_name → list of [stamp, value] pairs
        self.var_desc_history = {}  # var_name → list of [stamp, description] pairs
        
        # OBJECT LAYER: Compressed storage for large data
        # objects[stamp] = {
        #     'data': base64_encoded_compressed_string,
        #     'size_original': int,
        #     'size_compressed': int,
        #     'content_type': str,  # 'bytes', 'text', 'json', 'pickle'
        # }
        self.objects = {}           # stamp → compressed object dict
        
        # Threshold for auto-converting variables to objects (bytes)
        self.object_threshold = 10000  # 10KB default
        
        # Valid values
        self.valid_roles = {
            'system',
            'user',
            'assistant',
            'reflection',
            'action',
            'query',
            'result',
            'logger',
        }
        self.valid_modes = {
            'text',
            'audio',
            'voice',
        }
        self.valid_channels = {
            'webapp',
            'ios',
            'android',
            'telegram',
            'whatsapp',
            'slack',
            'api',
            'cli',
            'unknown',
        }

    #--- Internal Methods ---

    def _add_to_index(self, index_list, timestamp, stamp):
        """
        Insert [timestamp, stamp] pair maintaining sorted order by timestamp.
        
        Args:
            index_list: One of the idx_* lists
            timestamp: ISO timestamp string (dt_utc)
            stamp: Event stamp ID
        """
        # bisect.insort sorts by first element of tuple/list (timestamp)
        self._bisect.insort(index_list, [timestamp, stamp])

    def _store_event(self, event_type, obj):
        """
        Store event in data layer and add to appropriate indexes.
        This is the single entry point for all event creation.
        
        Args:
            event_type: One of 'msg', 'ref', 'log', 'var'
            obj: The full event dict (must contain 'stamp' and 'dt_utc' keys)
        """
        stamp = obj['stamp']
        timestamp = obj['dt_utc']
        
        # Store in data layer
        self.events[stamp] = obj
        
        # Add to type-specific index (with [timestamp, stamp] format)
        if event_type == 'msg':
            self._add_to_index(self.idx_msgs, timestamp, stamp)
        elif event_type == 'ref':
            self._add_to_index(self.idx_refs, timestamp, stamp)
        elif event_type == 'log':
            self._add_to_index(self.idx_logs, timestamp, stamp)
        elif event_type == 'var':
            self._add_to_index(self.idx_vars, timestamp, stamp)
        
        # Always add to master index
        self._add_to_index(self.idx_all, timestamp, stamp)

    def _get_events_from_index(self, index, limit=-1):
        """
        Get events from an index, optionally limited to last N.
        
        Args:
            index: One of the idx_* lists (format: [[timestamp, stamp], ...])
            limit: Max events to return (-1 = all)
            
        Returns:
            List of event dicts
        """
        pairs = index if limit <= 0 else index[-limit:]
        # Extract stamp (second element) from each [timestamp, stamp] pair
        return [self.events[ts_stamp[1]] for ts_stamp in pairs if ts_stamp[1] in self.events]

    def _get_latest_desc(self, key):
        """
        Get the latest description for a variable from its description history.
        
        Args:
            key: Variable name
            
        Returns:
            Latest description string, or empty string if none exists
        """
        history = self.var_desc_history.get(key)
        if not history:
            return ''
        return history[-1][1]  # Return description from last [stamp, desc] pair

    #--- Public Methods ---

    def add_msg(self, role, content, mode='text', channel='unknown'):
        """
        Add a message event with channel tracking.
        
        Args:
            role: Message role (user, assistant, system, etc.)
            content: Message content
            mode: Communication mode (text, audio, voice)
            channel: Communication channel (webapp, ios, telegram, etc.)
        """
        if role not in self.valid_roles:
            raise ValueError("Invalid role '{}'. Must be one of: {}".format(role, sorted(self.valid_roles)))
        if mode not in self.valid_modes:
            raise ValueError("Invalid mode '{}'. Must be one of: {}".format(mode, sorted(self.valid_modes)))
        if channel not in self.valid_channels:
            raise ValueError("Invalid channel '{}'. Must be one of: {}".format(channel, sorted(self.valid_channels)))
        
        stamp = event_stamp({'role': role, 'content': content})
        msg = {
            'stamp'   : stamp,
            'type'    : 'msg',
            'role'    : role,
            'content' : content,
            'mode'    : mode,
            'channel' : channel,
            'dt_bog'  : str(dtt.datetime.now(tz_bog))[:23],
            'dt_utc'  : str(dtt.datetime.now(tz_utc))[:23],
        }
        self._store_event('msg', msg)

    def add_log(self, message):
        """
        Add a log event.
        
        Args:
            message: Log message content
        """
        stamp = event_stamp({'content': message})
        log_entry = {
            'stamp'   : stamp,
            'type'    : 'log',
            'role'    : 'logger',
            'content' : message,
            'mode'    : 'text',
            'dt_bog'  : str(dtt.datetime.now(tz_bog))[:23],
            'dt_utc'  : str(dtt.datetime.now(tz_utc))[:23],
        }
        self._store_event('log', log_entry)

    def add_ref(self, content):
        """
        Add a reflection event.
        
        Args:
            content: Reflection content
        """
        stamp = event_stamp({'content': content})
        ref = {
            'stamp'   : stamp,
            'type'    : 'ref',
            'role'    : 'reflection',
            'content' : content,
            'mode'    : 'text',
            'dt_bog'  : str(dtt.datetime.now(tz_bog))[:23],
            'dt_utc'  : str(dtt.datetime.now(tz_utc))[:23],
        }
        self._store_event('ref', ref) 

    #---

    def get_msgs(self, 
                 limit=-1, 
                 include=None, 
                 exclude=None, 
                 repr='list',
                 channel=None,
                ):
        """
        Get messages with flexible filtering.
        
        Args:
            limit: Max messages to return (-1 = all)
            include: List of roles to include (None = all)
            exclude: List of roles to exclude (None = none)
            repr: Output format ('list', 'str', 'pprint1')
            channel: Filter by channel (None = all)
            
        Returns:
            Messages in the specified format
        """
        # Get all messages from index
        events = self._get_events_from_index(self.idx_msgs, -1)
        
        # Apply filters
        if include:
            events = [e for e in events if e.get('role') in include]
        if exclude:
            exclude = exclude or []
            events = [e for e in events if e.get('role') not in exclude]
        if channel:
            events = [e for e in events if e.get('channel') == channel]
        
        if limit > 0:
            events = events[-limit:]
        
        if repr == 'list':
            return events
        elif repr == 'str':
            return '\n'.join(["{}: {}".format(e['role'], e['content']) for e in events])
        elif repr == 'pprint1':
            return pprint.pformat(events, indent=1)
        else:
            raise ValueError("Invalid repr option. Choose from 'list', 'str', or 'pprint1'.")

    def get_events(self, limit=-1, event_types=None, channel=None):
        """
        Get all events, optionally filtered by type and channel.
        
        Args:
            limit: Max events (-1 = all)
            event_types: List like ['msg', 'log', 'ref', 'var'] (None = all)
            channel: Filter by channel (None = all)
            
        Returns:
            List of event dicts
        """
        events = self._get_events_from_index(self.idx_all, -1)
        
        if event_types:
            events = [e for e in events if e.get('type') in event_types]
        if channel:
            events = [e for e in events if e.get('channel') == channel]
        
        if limit > 0:
            events = events[-limit:]
        
        return events

    def get_logs(self, limit=-1):
        """
        Get log events.
        
        Args:
            limit: Max logs to return (-1 = all)
            
        Returns:
            List of log event dicts
        """
        events = self._get_events_from_index(self.idx_logs, -1)
        
        if limit > 0:
            events = events[-limit:]
        
        return events

    def get_refs(self, limit=-1):
        """
        Get reflection events.
        
        Args:
            limit: Max reflections to return (-1 = all)
            
        Returns:
            List of reflection event dicts
        """
        events = self._get_events_from_index(self.idx_refs, -1)
        
        if limit > 0:
            events = events[-limit:]
        
        return events

    def last_user_msg(self):
        """Get the content of the last user message."""
        msgs = self.get_msgs(include=['user'])
        return msgs[-1]['content'] if msgs else ''

    def last_asst_msg(self):
        """Get the content of the last assistant message."""
        msgs = self.get_msgs(include=['assistant'])
        return msgs[-1]['content'] if msgs else ''

    def last_sys_msg(self):
        """Get the content of the last system message."""
        msgs = self.get_msgs(include=['system'])
        return msgs[-1]['content'] if msgs else ''

    def last_log_msg(self):
        """Get the content of the last log message."""
        logs = self.get_logs()
        return logs[-1]['content'] if logs else ''

    def prepare_context(
        self,
        recent_count=6,
        truncate_threshold=500,
        header_len=200,
        footer_len=200,
        include_roles=('user', 'assistant'),
        format='list',
    ):
        """
        Prepare messages for LLM context with smart truncation of old messages.
        
        Messages within the most recent `recent_count` are returned unchanged.
        Older messages that exceed `truncate_threshold` chars have their middle
        content truncated, preserving a header and footer with an expandable marker.
        
        The truncation marker includes the message's stamp, allowing an LLM to
        request expansion of specific messages via memory.events[stamp].
        
        Args:
            recent_count: Number of recent messages to keep untruncated (default 6)
            truncate_threshold: Min chars before truncation applies (default 500)
            header_len: Characters to keep from start (default 200)
            footer_len: Characters to keep from end (default 200)
            include_roles: Tuple of roles to include (default ('user', 'assistant'))
            format: 'list' returns list of dicts, 'openai' returns OpenAI-compatible format
        
        Returns:
            List of message dicts with 'role' and 'content' keys.
            Older messages may have truncated content with expansion markers.
        
        Example:
            # Get context-ready messages for LLM
            context = memory.prepare_context(recent_count=6, truncate_threshold=500)
            
            # Use with OpenAI API
            context = memory.prepare_context(format='openai')
            response = client.chat.completions.create(
                model='gpt-4',
                messages=context
            )
        """
        # Get all messages for included roles
        msgs = self.get_msgs(include=list(include_roles))
        
        if not msgs:
            return []
        
        # Determine cutoff point for truncation
        # Messages at index < cutoff_idx are candidates for truncation
        cutoff_idx = max(0, len(msgs) - recent_count)
        
        result = []
        for i, msg in enumerate(msgs):
            stamp = msg.get('stamp', '')
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            
            # Apply truncation to older messages
            if i < cutoff_idx:
                content = truncate_content(
                    content, 
                    stamp, 
                    threshold=truncate_threshold,
                    header_len=header_len,
                    footer_len=footer_len
                )
            
            if format == 'openai':
                # OpenAI expects 'user', 'assistant', 'system' roles
                result.append({'role': role, 'content': content})
            else:
                # List format includes more metadata
                result.append({
                    'role': role,
                    'content': content,
                    'stamp': stamp,
                    'truncated': i < cutoff_idx and len(msg.get('content', '')) > truncate_threshold,
                })
        
        return result

    #---
    
    def set_var(self, key, value, desc=''):
        """
        Store a variable by appending to its history list.
        Variable changes are first-class events in the event stream.
        Each variable maintains a full history of [stamp, value] pairs.
        
        Large values (exceeding object_threshold) are automatically converted
        to compressed objects, with an object reference stored in the history.
        
        Descriptions are tracked separately in var_desc_history since they
        change less frequently than values.
        
        Args:
            key: Variable name
            value: Variable value (any type)
            desc: Optional description (appended to description history if provided)
        """
        # Check if value should be stored as object (auto-conversion)
        value_size = estimate_size(value)
        if value_size > self.object_threshold:
            # Store as object, use reference in history
            obj_stamp = event_stamp({'obj': str(value)[:50]})
            compressed_obj = compress_to_json(value)
            self.objects[obj_stamp] = compressed_obj
            stored_value = {'_obj_ref': obj_stamp}
        else:
            stored_value = value
        
        stamp = event_stamp({'var': key, 'value': str(value)[:100]})
        
        # Initialize history list if this is a new variable
        if key not in self.vars:
            self.vars[key] = []
        
        # Append new [stamp, stored_value] pair to history
        self.vars[key].append([stamp, stored_value])
        
        # Track description changes separately (only when provided)
        if desc:
            if key not in self.var_desc_history:
                self.var_desc_history[key] = []
            self.var_desc_history[key].append([stamp, desc])
        
        # Get latest description from history (or the one we just set)
        current_desc = desc if desc else self._get_latest_desc(key)
        
        # Create variable-change event
        var_event = {
            'stamp'    : stamp,
            'type'     : 'var',
            'role'     : 'system',
            'var_name' : key,
            'var_value': stored_value,  # Store reference if large, else value
            'var_desc' : current_desc,
            'content'  : "Variable '{}' set".format(key) + (' (as object ref)' if is_obj_ref(stored_value) else ''),
            'mode'     : 'text',
            'dt_bog'   : str(dtt.datetime.now(tz_bog))[:23],
            'dt_utc'   : str(dtt.datetime.now(tz_utc))[:23],
        }
        self._store_event('var', var_event)

    def del_var(self, key):
        """
        Mark a variable as deleted by appending a VAR_DELETED tombstone.
        The variable's history is preserved; it can be re-set later.
        
        Args:
            key: Variable name to delete
            
        Raises:
            KeyError: If the variable doesn't exist
        """
        if key not in self.vars:
            raise KeyError("Variable '{}' does not exist".format(key))
        
        stamp = event_stamp({'var': key, 'action': 'delete'})
        
        # Append deletion marker to history
        self.vars[key].append([stamp, VAR_DELETED])
        
        # Create variable-delete event
        var_event = {
            'stamp'    : stamp,
            'type'     : 'var',
            'role'     : 'system',
            'var_name' : key,
            'var_value': None,
            'var_deleted': True,
            'var_desc' : self._get_latest_desc(key),
            'content'  : "Variable '{}' deleted".format(key),
            'mode'     : 'text',
            'dt_bog'   : str(dtt.datetime.now(tz_bog))[:23],
            'dt_utc'   : str(dtt.datetime.now(tz_utc))[:23],
        }
        self._store_event('var', var_event)

    def get_var(self, key, resolve_refs=True):
        """
        Return the current value of a variable.
        
        If the value is an object reference, it is automatically resolved
        and the decompressed data is returned (unless resolve_refs=False).
        
        Args:
            key: Variable name
            resolve_refs: If True (default), resolve object references to actual data
            
        Returns:
            Current value, or None if not found or deleted
        """
        history = self.vars.get(key)
        if not history:
            return None
        
        # Get the last value
        last_stamp, last_value = history[-1]
        
        # Return None if deleted
        if last_value is VAR_DELETED:
            return None
        
        # Resolve object reference if applicable
        if resolve_refs and is_obj_ref(last_value):
            return self.get_obj(last_value['_obj_ref'])
        
        return last_value

    def is_var_deleted(self, key):
        """
        Check if a variable is currently marked as deleted.
        
        Args:
            key: Variable name
            
        Returns:
            True if the variable exists and is deleted, False otherwise
        """
        history = self.vars.get(key)
        if not history:
            return False
        
        last_stamp, last_value = history[-1]
        return last_value is VAR_DELETED

    def get_all_vars(self, resolve_refs=True):
        """
        Get a dictionary of all current non-deleted variable values.
        
        Args:
            resolve_refs: If True (default), resolve object references to actual data
        
        Returns:
            dict: Variable name → current value (excludes deleted variables)
        """
        result = {}
        for key, history in self.vars.items():
            if history:
                last_stamp, last_value = history[-1]
                if last_value is not VAR_DELETED:
                    # Resolve object reference if applicable
                    if resolve_refs and is_obj_ref(last_value):
                        result[key] = self.get_obj(last_value['_obj_ref'])
                    else:
                        result[key] = last_value
        return result

    def get_var_history(self, key, resolve_refs=False):
        """
        Get full history of a variable as list of [stamp, value] pairs.
        Includes all historical values and deletion markers.
        
        Args:
            key: Variable name
            resolve_refs: If True, resolve object references to actual data.
                          Default False to preserve the raw history structure.
            
        Returns:
            List of [stamp, value] pairs, or empty list if variable doesn't exist.
            Deleted entries have VAR_DELETED as the value.
            Object references appear as {'_obj_ref': stamp} unless resolve_refs=True.
        """
        history = self.vars.get(key, [])
        if not resolve_refs:
            return list(history)
        
        # Resolve object references
        resolved = []
        for stamp, value in history:
            if is_obj_ref(value):
                resolved.append([stamp, self.get_obj(value['_obj_ref'])])
            else:
                resolved.append([stamp, value])
        return resolved

    def get_var_desc(self, key):
        """
        Get the current (latest) description of a variable.
        
        Args:
            key: Variable name
            
        Returns:
            Latest description string, or default message if no description exists
        """
        desc = self._get_latest_desc(key)
        return desc if desc else "No description found."

    def get_var_desc_history(self, key):
        """
        Get full history of a variable's descriptions as list of [stamp, description] pairs.
        
        Args:
            key: Variable name
            
        Returns:
            List of [stamp, description] pairs, or empty list if variable has no descriptions.
        """
        return list(self.var_desc_history.get(key, []))

    #--- Object Methods ---

    def set_obj(self, data, name=None, desc='', content_type='auto'):
        """
        Store a large object in compressed form.
        
        Objects are compressed using zlib and base64-encoded for JSON serialization.
        Optionally creates a variable reference to the stored object.
        
        Args:
            data: The data to store (bytes, str, or any JSON/pickle-serializable object)
            name: Optional variable name to create a reference
            desc: Description (used only if name is provided)
            content_type: 'bytes', 'text', 'json', 'pickle', or 'auto'
        
        Returns:
            str: The object stamp (ID)
        
        Example:
            # Store raw data, get stamp back
            stamp = memory.set_obj(large_text)
            
            # Store and create variable reference
            memory.set_obj(image_bytes, name='profile_pic', desc='User avatar')
            memory.get_var('profile_pic')  # Returns decompressed image_bytes
        """
        stamp = event_stamp({'obj': str(data)[:50]})
        
        # Compress and store
        compressed_obj = compress_to_json(data, content_type)
        self.objects[stamp] = compressed_obj
        
        # Optionally create a variable reference
        if name:
            obj_ref = {'_obj_ref': stamp}
            # Store reference directly in vars (bypassing size check)
            var_stamp = event_stamp({'var': name})
            
            # Initialize history if needed
            if name not in self.vars:
                self.vars[name] = []
            
            # Append [stamp, obj_ref] to history
            self.vars[name].append([var_stamp, obj_ref])
            
            # Track description changes separately (only when provided)
            if desc:
                if name not in self.var_desc_history:
                    self.var_desc_history[name] = []
                self.var_desc_history[name].append([var_stamp, desc])
            
            # Get latest description for the event
            current_desc = desc if desc else self._get_latest_desc(name)
            
            # Store the var event
            var_event = {
                'type'     : 'var',
                'stamp'    : var_stamp,
                'var_name' : name,
                'var_value': obj_ref,  # Store the reference, not the data
                'var_deleted': False,
                'var_desc' : current_desc,
                'content'  : "Variable '{}' set to object ref: {}".format(name, stamp),
                'mode'     : 'text',
                'dt_bog'   : str(dtt.datetime.now(tz_bog))[:23],
                'dt_utc'   : str(dtt.datetime.now(tz_utc))[:23],
            }
            self._store_event('var', var_event)
        
        return stamp

    def get_obj(self, stamp):
        """
        Retrieve and decompress an object by its stamp.
        
        Args:
            stamp: The object's event stamp
        
        Returns:
            The decompressed original data, or None if not found
        
        Example:
            data = memory.get_obj('A1B2C3...')
        """
        obj_dict = self.objects.get(stamp)
        if obj_dict is None:
            return None
        return decompress_from_json(obj_dict)

    def get_obj_info(self, stamp):
        """
        Get metadata about a stored object without decompressing it.
        
        Args:
            stamp: The object's event stamp
        
        Returns:
            dict with size_original, size_compressed, content_type, or None if not found
        """
        obj_dict = self.objects.get(stamp)
        if obj_dict is None:
            return None
        return {
            'stamp': stamp,
            'size_original': obj_dict['size_original'],
            'size_compressed': obj_dict['size_compressed'],
            'content_type': obj_dict['content_type'],
            'compression_ratio': obj_dict['size_compressed'] / obj_dict['size_original'] if obj_dict['size_original'] > 0 else 0,
        }

    #---

    def snapshot(self):
        """
        Export memory state as dict.
        Stores events and objects - indexes can be rehydrated from events.
        
        Returns:
            dict with 'id', 'events', and 'objects' keys
        """
        return {
            'id': self.id,
            'events': dict(self.events),    # All events by stamp
            'objects': dict(self.objects),  # All objects by stamp (already JSON-serializable)
        }

    def save(self, filename, compressed=False):
        """
        Save memory to file.
        
        Args:
            filename: Path to save file
            compressed: If True, use gzip compression
        """
        import gzip
        data = self.snapshot()
        if compressed:
            with gzip.open(filename, 'wb') as f:
                pickle.dump(data, f)
        else:
            with open(filename, 'wb') as f:
                pickle.dump(data, f)

    def load(self, filename, compressed=False):
        """
        Load memory from file by rehydrating from events.
        
        Args:
            filename: Path to load file
            compressed: If True, expect gzip compression
        """
        import gzip
        if compressed:
            with gzip.open(filename, 'rb') as f:
                data = pickle.load(f)
        else:
            with open(filename, 'rb') as f:
                data = pickle.load(f)
        
        # Rehydrate from events (pass objects if present)
        event_list = list(data.get('events', {}).values())
        objects = data.get('objects', {})
        mem = MEMORY.from_events(event_list, data.get('id'), objects=objects)
        
        # Copy state to self
        self.id = mem.id
        self.events = mem.events
        self.idx_msgs = mem.idx_msgs
        self.idx_refs = mem.idx_refs
        self.idx_logs = mem.idx_logs
        self.idx_vars = mem.idx_vars
        self.idx_all = mem.idx_all
        self.vars = mem.vars
        self.var_desc_history = mem.var_desc_history
        self.objects = mem.objects

    def copy(self):
        """Return a deep copy of the MEMORY instance."""
        return copy.deepcopy(self)

    def to_json(self, filename=None, indent=2):
        """
        Export memory to JSON format.
        
        Like DataFrame.to_csv(), this allows saving memory state to a portable
        JSON format that can be loaded later with from_json().
        
        Args:
            filename: If provided, write to file. Otherwise return JSON string.
            indent: JSON indentation level (default 2, use None for compact)
        
        Returns:
            JSON string if filename is None, else None
        
        Example:
            # Save to file
            memory.to_json('memory_backup.json')
            
            # Get JSON string
            json_str = memory.to_json()
        """
        # Prepare data for JSON serialization
        # Need to handle VAR_DELETED sentinel in vars history
        def serialize_var_history(var_dict):
            """Convert VAR_DELETED sentinel to JSON-safe marker."""
            result = {}
            for key, history in var_dict.items():
                serialized_history = []
                for stamp, value in history:
                    if value is VAR_DELETED:
                        serialized_history.append([stamp, '__VAR_DELETED__'])
                    else:
                        serialized_history.append([stamp, value])
                result[key] = serialized_history
            return result
        
        data = {
            'version': '1.0',
            'id': self.id,
            'events': self.events,
            'objects': self.objects,
            'vars': serialize_var_history(self.vars),
            'var_desc_history': self.var_desc_history,
            'idx_msgs': self.idx_msgs,
            'idx_refs': self.idx_refs,
            'idx_logs': self.idx_logs,
            'idx_vars': self.idx_vars,
            'idx_all': self.idx_all,
        }
        
        json_str = json.dumps(data, indent=indent, ensure_ascii=False)
        
        if filename:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(json_str)
            return None
        return json_str

    @classmethod
    def from_json(cls, source):
        """
        Create MEMORY instance from JSON.
        
        Like DataFrame.read_csv(), this loads a memory from a JSON file or string
        that was saved with to_json().
        
        Args:
            source: JSON string or filename path
        
        Returns:
            New MEMORY instance
        
        Example:
            # Load from file
            memory = MEMORY.from_json('memory_backup.json')
            
            # Load from JSON string
            memory = MEMORY.from_json(json_str)
        """
        import os
        
        # Determine if source is a file or JSON string
        if os.path.isfile(source):
            with open(source, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = json.loads(source)
        
        # Helper to restore VAR_DELETED sentinel
        def deserialize_var_history(var_dict):
            """Convert JSON marker back to VAR_DELETED sentinel."""
            result = {}
            for key, history in var_dict.items():
                deserialized_history = []
                for stamp, value in history:
                    if value == '__VAR_DELETED__':
                        deserialized_history.append([stamp, VAR_DELETED])
                    else:
                        deserialized_history.append([stamp, value])
                result[key] = deserialized_history
            return result
        
        # Create new instance
        mem = cls()
        mem.id = data.get('id', mem.id)
        mem.events = data.get('events', {})
        mem.objects = data.get('objects', {})
        mem.vars = deserialize_var_history(data.get('vars', {}))
        mem.var_desc_history = data.get('var_desc_history', {})
        mem.idx_msgs = data.get('idx_msgs', [])
        mem.idx_refs = data.get('idx_refs', [])
        mem.idx_logs = data.get('idx_logs', [])
        mem.idx_vars = data.get('idx_vars', [])
        mem.idx_all = data.get('idx_all', [])
        
        return mem

    @classmethod
    def from_events(cls, event_list, memory_id=None, objects=None):
        """
        Rehydrate a MEMORY instance from a list of events.
        This is the inverse of snapshot - enables cloud sync.
        
        Args:
            event_list: List of event dicts (order doesn't matter, will be sorted)
            memory_id: Optional ID for the memory instance
            objects: Optional dict of objects (stamp → compressed object dict)
            
        Returns:
            New MEMORY instance with all events loaded
        """
        mem = cls()
        if memory_id:
            mem.id = memory_id
        
        # Restore objects if provided
        if objects:
            mem.objects = dict(objects)
        
        # Sort events by timestamp (dt_utc) for chronological order
        sorted_events = sorted(event_list, key=lambda e: e.get('dt_utc', ''))
        
        for ev in sorted_events:
            stamp = ev.get('stamp')
            timestamp = ev.get('dt_utc', '')
            if not stamp:
                continue
            
            event_type = ev.get('type', 'msg')
            
            # Store in data layer
            mem.events[stamp] = ev
            
            # Create [timestamp, stamp] pair for indexes
            ts_pair = [timestamp, stamp]
            
            # Add to appropriate index (direct append since already sorted by timestamp)
            if event_type == 'msg':
                mem.idx_msgs.append(ts_pair)
            elif event_type == 'ref':
                mem.idx_refs.append(ts_pair)
            elif event_type == 'log':
                mem.idx_logs.append(ts_pair)
            elif event_type == 'var':
                mem.idx_vars.append(ts_pair)
                # Replay variable state into history list
                var_name = ev.get('var_name')
                if var_name:
                    # Initialize history list if needed
                    if var_name not in mem.vars:
                        mem.vars[var_name] = []
                    
                    # Determine value (check for deletion marker)
                    if ev.get('var_deleted', False):
                        value = VAR_DELETED
                    else:
                        value = ev.get('var_value')
                    
                    # Append to history
                    mem.vars[var_name].append([stamp, value])
                    
                    # Rebuild description history if present
                    var_desc = ev.get('var_desc')
                    if var_desc:
                        if var_name not in mem.var_desc_history:
                            mem.var_desc_history[var_name] = []
                        # Only add if different from last description (avoid duplicates)
                        desc_hist = mem.var_desc_history[var_name]
                        if not desc_hist or desc_hist[-1][1] != var_desc:
                            desc_hist.append([stamp, var_desc])
            
            mem.idx_all.append(ts_pair)
        
        return mem

    #---

    # The render method provides a flexible way to display or export the MEMORY's messages or events.
    # It supports event type selection, output format, advanced filtering, metadata inclusion, pretty-printing, and message condensing.
    def render(
        self,
        include=('msgs',),           # Tuple/list of event types to include: 'msgs', 'logs', 'refs', 'vars', 'events'
        output_format='plain',       # 'plain', 'markdown', 'json', 'table', 'conversation'
        role_filter=None,            # List of roles to include (None = all)
        mode_filter=None,            # List of modes to include (None = all)
        channel_filter=None,         # Channel to filter by (None = all)
        content_filter=None,         # String or list of keywords to filter content (None = all)
        include_metadata=True,       # Whether to include metadata (timestamps, roles, etc.)
        pretty=True,                 # Pretty-print for human readability
        max_length=None,             # Max total length of output (int, None = unlimited)
        condense_msg=True,           # If True, snip/condense messages that exceed max_length
        time_range=None,             # Tuple (start_dt, end_dt) to filter by datetime (None = all)
        event_limit=None,            # Max number of events to include (None = all)
        # Conversation/LLM-optimized options:
        max_message_length=1000,     # Max length per individual message (for 'conversation' format)
        max_total_length=8000,       # Max total length of the entire conversation (for 'conversation' format)
        include_roles=('user', 'assistant'),  # Which roles to include (for 'conversation' format)
        message_separator="\n\n",    # Separator between messages (for 'conversation' format)
        role_prefix=True,            # Whether to include role prefixes like "User:" and "Assistant:" (for 'conversation' format)
        truncate_indicator="...",    # What to show when content is truncated (for 'conversation' format)
    ):
        """
        Render MEMORY contents with flexible filtering and formatting.

        This method unifies all rendering and export logic, including:
        - General event/message rendering (plain, markdown, table, json)
        - Advanced filtering (by role, mode, channel, content, time, event type)
        - Metadata inclusion and pretty-printing
        - Output length limiting and message condensing/snipping
        - LLM-optimized conversation export (via output_format='conversation'), 
          which produces a clean text blob of user/assistant messages with 
          configurable length and formatting options.

        Args:
            include: Which event types to include ('msgs', 'logs', 'refs', 'vars', 'events')
            output_format: 'plain', 'markdown', 'json', 'table', or 'conversation'
            role_filter: List of roles to include (None = all)
            mode_filter: List of modes to include (None = all)
            channel_filter: Channel to filter by (None = all)
            content_filter: String or list of keywords to filter content (None = all)
            include_metadata: Whether to include metadata (timestamps, roles, etc.)
            pretty: Pretty-print for human readability
            max_length: Max total length of output (for general formats)
            condense_msg: If True, snip/condense messages that exceed max_length
            time_range: Tuple (start_dt, end_dt) to filter by datetime (None = all)
            event_limit: Max number of events to include (None = all)
            max_message_length: Max length per message (for 'conversation' format)
            max_total_length: Max total length (for 'conversation' format)
            include_roles: Which roles to include (for 'conversation' format)
            message_separator: Separator between messages (for 'conversation' format)
            role_prefix: Whether to include role prefixes (for 'conversation' format)
            truncate_indicator: Indicator for truncated content (for 'conversation' format)

        Returns:
            str or dict: Rendered output in the specified format.

        Example usage:
            mem = MEMORY()
            mem.add_msg('user', 'Hello!')
            mem.add_msg('assistant', 'Hi there!')
            print(mem.render())  # Default: plain text, all messages

            # Render only user messages in markdown
            print(mem.render(role_filter=['user'], output_format='markdown'))

            # Render as a table, including logs and refs
            print(mem.render(include=('msgs', 'logs', 'refs'), output_format='table'))

            # Render with a content keyword filter and max length
            print(mem.render(content_filter='hello', max_length=50))

            # Export as LLM-optimized conversation
            print(mem.render(output_format='conversation', max_total_length=2000))
            
            # Filter by channel
            print(mem.render(channel_filter='telegram'))
        """
        import json
        from datetime import datetime

        # Helper: flatten include to set for fast lookup
        include_set = set(include)

        # Helper: filter events by type using the new index-based retrieval
        def filter_events():
            events = []
            if 'events' in include_set:
                # Include all events from master index
                events = self._get_events_from_index(self.idx_all, -1)
            else:
                # Selectively include types
                if 'msgs' in include_set:
                    events.extend(self._get_events_from_index(self.idx_msgs, -1))
                if 'logs' in include_set:
                    events.extend(self._get_events_from_index(self.idx_logs, -1))
                if 'refs' in include_set:
                    events.extend(self._get_events_from_index(self.idx_refs, -1))
                if 'vars' in include_set:
                    events.extend(self._get_events_from_index(self.idx_vars, -1))
            return events

        # Helper: filter by role, mode, channel, content, and time
        def advanced_filter(evlist):
            filtered = []
            for ev in evlist:
                # Role filter
                if role_filter:
                    ev_role = ev.get('role') or ev.get('type')
                    if ev_role not in role_filter:
                        continue
                # Mode filter
                if mode_filter and ev.get('mode') not in mode_filter:
                    continue
                # Channel filter
                if channel_filter and ev.get('channel') != channel_filter:
                    continue
                # Content filter
                if content_filter:
                    content = ev.get('content', '')
                    if isinstance(content_filter, str):
                        if content_filter.lower() not in content.lower():
                            continue
                    else:  # list of keywords
                        if not any(kw.lower() in content.lower() for kw in content_filter):
                            continue
                # Time filter
                if time_range:
                    # Try to get timestamp from event
                    dt_str = ev.get('dt_utc') or ev.get('dt_bog')
                    if dt_str:
                        try:
                            dt = datetime.fromisoformat(dt_str)
                            start, end = time_range
                            if (start and dt < start) or (end and dt > end):
                                continue
                        except Exception:
                            pass  # Ignore if can't parse
                filtered.append(ev)
            return filtered

        # Helper: sort events by stamp (alphabetical = chronological)
        def sort_events(evlist):
            return sorted(evlist, key=lambda ev: ev.get('stamp', ''))

        # Step 1: Gather and filter events
        events = filter_events()
        events = advanced_filter(events)
        events = sort_events(events)
        if event_limit:
            events = events[-event_limit:]  # Most recent N

        # --- Conversation/LLM-optimized format ---
        if output_format == 'conversation':
            # Only include messages and filter by include_roles
            conv_msgs = [ev for ev in events if ev.get('role') in include_roles]
            # Already sorted by stamp

            conversation_parts = []
            current_length = 0
            for msg in conv_msgs:
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')

                # Truncate individual message if needed
                if len(content) > max_message_length:
                    content = content[:max_message_length - len(truncate_indicator)] + truncate_indicator

                # Format the message
                if role_prefix:
                    if role == 'user':
                        formatted_msg = "User: " + content
                    elif role == 'assistant':
                        formatted_msg = "Assistant: " + content
                    else:
                        formatted_msg = role.title() + ": " + content
                else:
                    formatted_msg = content

                # Check if adding this message would exceed total length
                message_length = len(formatted_msg) + len(message_separator)
                if current_length + message_length > max_total_length:
                    # If we can't fit the full message, try to fit a truncated version
                    remaining_space = max_total_length - current_length - len(truncate_indicator)
                    if remaining_space > 50:  # Only add if there's reasonable space
                        if role_prefix:
                            prefix_len = len(role.title() + ": ")
                            truncated_content = content[:remaining_space - prefix_len] + truncate_indicator
                            formatted_msg = role.title() + ": " + truncated_content
                        else:
                            formatted_msg = content[:remaining_space] + truncate_indicator
                        conversation_parts.append(formatted_msg)
                    break

                conversation_parts.append(formatted_msg)
                current_length += message_length

            return message_separator.join(conversation_parts)

        # --- JSON format ---
        output = None
        total_length = 0
        snip_notice = " [snipped]"  # For snipped messages

        if output_format == 'json':
            # Output as JSON (list of dicts)
            if not include_metadata:
                # Remove metadata fields
                def strip_meta(ev):
                    return {k: v for k, v in ev.items() if k in ('role', 'content', 'type', 'channel')}
                out_events = [strip_meta(ev) for ev in events]
            else:
                out_events = events
            output = json.dumps(out_events, indent=2 if pretty else None, default=str)
            if max_length and len(output) > max_length:
                output = output[:max_length] + snip_notice

        elif output_format in ('plain', 'markdown', 'table'):
            # Build lines for each event
            lines = []
            for ev in events:
                # Compose line based on event type
                event_type = ev.get('type', 'msg')
                if event_type == 'log' or ev.get('role') == 'logger':
                    prefix = "[LOG]"
                    content = ev.get('content', '')
                elif event_type == 'ref':
                    prefix = "[REF]"
                    content = ev.get('content', '')
                elif event_type == 'var':
                    prefix = "[VAR]"
                    content = "{} = {}".format(ev.get('var_name', '?'), ev.get('var_value', '?'))
                else:
                    prefix = "[{}]".format(ev.get('role', 'MSG').upper())
                    content = ev.get('content', '')

                # Optionally include metadata
                meta = ""
                if include_metadata:
                    dt = ev.get('dt_utc') or ev.get('dt_bog')
                    stamp = ev.get('stamp', '')
                    channel = ev.get('channel', '')
                    meta = " ({})".format(dt) if dt else ""
                    if output_format == 'table':
                        meta = "\t{}\t{}\t{}".format(dt or '', stamp or '', channel or '')

                # Condense message if needed
                line = "{} {}{}".format(prefix, content, meta)
                if max_length and total_length + len(line) > max_length:
                    if condense_msg:
                        # Snip the content to fit
                        allowed = max_length - total_length - len(snip_notice)
                        if allowed > 0:
                            line = line[:allowed] + snip_notice
                        else:
                            line = snip_notice
                        lines.append(line)
                        break
                    else:
                        break
                lines.append(line)
                total_length += len(line) + 1  # +1 for newline

            # Format as table if requested
            if output_format == 'table':
                # Table header
                header = "Type\tContent\tDatetime\tStamp\tChannel"
                table_lines = [header]
                for ev in events:
                    typ = ev.get('type', ev.get('role', ''))
                    if typ == 'var':
                        content = "{} = {}".format(ev.get('var_name', '?'), ev.get('var_value', '?'))
                    else:
                        content = ev.get('content', '')
                    dt = ev.get('dt_utc') or ev.get('dt_bog') or ''
                    stamp = ev.get('stamp', '')
                    channel = ev.get('channel', '')
                    row = "{}\t{}\t{}\t{}\t{}".format(typ, content, dt, stamp, channel)
                    table_lines.append(row)
                output = "\n".join(table_lines)
            else:
                sep = "\n" if pretty else " "
                output = sep.join(lines)

        else:
            raise ValueError("Unknown output_format: {}".format(output_format))

        return output


MemoryManipulationExamples = """

MEMORY Class Usage Tutorial
===========================

This tutorial demonstrates common workflows and transactions using the MEMORY class.
The MEMORY class is an event-sourced state container for managing messages, logs, 
reflections, and variables in agentic or conversational systems.

Key Features:
- Everything is an event with a sortable ID (alphabetical = chronological)
- Events stored in a dictionary for O(1) lookup
- Channel tracking for messages (omni-directional communication)
- Full variable history with timestamps
- Memory can be rehydrated from event list for cloud sync

------------------------------------------------------------
1. Initialization
------------------------------------------------------------

>>> mem = MEMORY()

Creates a new MEMORY instance with empty event stores and indexes.

------------------------------------------------------------
2. Adding and Retrieving Messages with Channel Support
------------------------------------------------------------

# Add user and assistant messages with channel tracking
>>> mem.add_msg('user', 'Hello, assistant!', channel='webapp')
>>> mem.add_msg('assistant', 'Hello, user! How can I help you?', channel='webapp')

# Messages from different channels
>>> mem.add_msg('user', 'Quick question via phone', channel='ios')
>>> mem.add_msg('user', 'Following up on Telegram', channel='telegram')

# Retrieve all messages as a list of dicts
>>> mem.get_msgs()
[{'role': 'user', 'content': 'Hello, assistant!', 'channel': 'webapp', ...}, ...]

# Filter messages by channel
>>> mem.get_msgs(channel='telegram')

# Retrieve only user messages as a string
>>> mem.get_msgs(include=['user'], repr='str')
'user: Hello, assistant!'

# Get the last assistant message
>>> mem.last_asst_msg()
'Hello, user! How can I help you?'

------------------------------------------------------------
3. Logging and Reflections
------------------------------------------------------------

# Add a log entry
>>> mem.add_log('System initialized.')

# Add a reflection (agent's internal reasoning)
>>> mem.add_ref('User seems to be asking about weather patterns.')

# Retrieve the last log message
>>> mem.last_log_msg()
'System initialized.'

# Get all logs
>>> mem.get_logs()

# Get all reflections
>>> mem.get_refs()

------------------------------------------------------------
4. Managing Variables (Full History Tracking)
------------------------------------------------------------

# Set a variable with a description (logged as an event!)
>>> mem.set_var('session_id', 'abc123', desc='Current session identifier')

# Update the variable (appends to history, doesn't overwrite)
>>> mem.set_var('session_id', 'xyz789')

# Retrieve the current value of a variable
>>> mem.get_var('session_id')
'xyz789'

# Get all current non-deleted variables as a dict
>>> mem.get_all_vars()
{'session_id': 'xyz789'}

# Get full variable history as list of [stamp, value] pairs
>>> mem.get_var_history('session_id')
[['stamp1...', 'abc123'], ['stamp2...', 'xyz789']]

# Get variable description
>>> mem.get_var_desc('session_id')
'Current session identifier'

# Delete a variable (marks as deleted but preserves history)
>>> mem.del_var('session_id')

# After deletion, get_var returns None
>>> mem.get_var('session_id')
None

# Check if a variable is deleted
>>> mem.is_var_deleted('session_id')
True

# History still shows all changes including deletion
>>> mem.get_var_history('session_id')
[['stamp1...', 'abc123'], ['stamp2...', 'xyz789'], ['stamp3...', <DELETED>]]

# Variable can be re-set after deletion
>>> mem.set_var('session_id', 'new_value')
>>> mem.get_var('session_id')
'new_value'

------------------------------------------------------------
5. Saving, Loading, and Copying State
------------------------------------------------------------

# Save MEMORY state to a file
>>> mem.save('memory_state.pkl')

# Save with compression
>>> mem.save('memory_state.pkl.gz', compressed=True)

# Load MEMORY state from a file (rehydrates from events)
>>> mem2 = MEMORY()
>>> mem2.load('memory_state.pkl')

# Deep copy the MEMORY object
>>> mem3 = mem.copy()

------------------------------------------------------------
6. Rehydrating from Events (Cloud Sync Ready)
------------------------------------------------------------

# Export all events
>>> events = mem.get_events()

# Create a new memory from events (order doesn't matter, sorted by stamp)
>>> mem_copy = MEMORY.from_events(events)

# Export snapshot for cloud storage
>>> snapshot = mem.snapshot()
# snapshot = {'id': '...', 'events': {...}}

------------------------------------------------------------
7. Rendering and Exporting Memory Contents
------------------------------------------------------------

# Render all messages as plain text (default)
>>> print(mem.render())

# Render only user messages in markdown format
>>> print(mem.render(role_filter=['user'], output_format='markdown'))

# Render as a table, including logs and reflections
>>> print(mem.render(include=('msgs', 'logs', 'refs'), output_format='table'))

# Filter by channel
>>> print(mem.render(channel_filter='telegram'))

# Render with a content keyword filter and max length
>>> print(mem.render(content_filter='hello', max_length=50))

# Export as LLM-optimized conversation (for prompt construction)
>>> print(mem.render(output_format='conversation', max_total_length=2000))

------------------------------------------------------------
8. Advanced Filtering and Formatting
------------------------------------------------------------

# Filter by role, mode, and channel
>>> print(mem.render(role_filter=['assistant'], mode_filter=['text'], channel_filter='webapp'))

# Filter by time range (using datetime objects)
>>> from datetime import datetime, timedelta
>>> start = datetime.utcnow() - timedelta(hours=1)
>>> end = datetime.utcnow()
>>> print(mem.render(time_range=(start, end)))

# Limit number of events/messages
>>> print(mem.render(event_limit=5))

# Get all events of specific types
>>> mem.get_events(event_types=['msg', 'ref'])

------------------------------------------------------------
9. Example: Full Workflow
------------------------------------------------------------

>>> mem = MEMORY()
>>> mem.add_msg('user', 'What is the weather today?', channel='webapp')
>>> mem.add_msg('assistant', 'The weather is sunny and warm.', channel='webapp')
>>> mem.set_var('weather', 'sunny and warm', desc='Latest weather info')
>>> mem.add_ref('User is interested in outdoor activities.')
>>> mem.add_log('Weather query processed successfully.')
>>> print(mem.render(output_format='conversation'))

# Export all events and rehydrate
>>> all_events = mem.get_events()
>>> mem_restored = MEMORY.from_events(all_events, mem.id)

------------------------------------------------------------
For more details, see the MEMORY class docstring and method documentation.
------------------------------------------------------------
"""


#############################################################################
#############################################################################

### THOUGHT CLASS



class THOUGHT:
    """
    The THOUGHT class represents a single, modular reasoning or action step within an agentic 
    workflow. It is designed to operate on MEMORY objects, orchestrating LLM calls, memory queries, 
    and variable manipulations in a composable and traceable manner. 
    THOUGHTs are the atomic units of reasoning, planning, and execution in the Thoughtflow framework, 
    and can be chained or composed to build complex agent behaviors.

    CONCEPT:
    A thought is a self-contained, modular process of (1) creating a structured prompt for an LLM, 
    (2) Executing the LLM request, (3) cleaning / validating the LLM response, and (4) retry execution 
    if it is necesary. It is the discrete unit of cognition. It is the execution of a single cognitive task. 
    In-so-doing, we have created the fundamental component of architecting multi-step cognitive systems.

    The Simple Equation of a Thought:
    Thoughts = Prompt + Context + LLM + Parsing + Validation


    COMPONENTS:

    1. PROMPT
    The Prompt() object is essentially the structured template which may contain certain parameters to fill-out. 
    This defines the structure and the rules for executing the LLM request.

    2. CONTEXT
    This is the relevant context which comes from a Memory() object. It is passed to a prompt object in the 
    structure of a dictionary containing the variables required / optional. Any context that is given, but 
    does not exist as a variable in the prompt, will be excluded.

    3. LLM REQUEST
    This is the simple transaction of submitting a structured Messages object to an LLM in order to receive 
    a response. The messages object may include a system prompt and a series of historical user / assistant 
    interactions. Passed in this request is also parameters like temperature.

    4. PARSING
    It is often that LLMs offer extra text even if they are told not to. For this reason, it is important 
    to parse the response such that we are only handling the content that was requested, and nothing more. 
    So if we are asking for a Python List, the parsed response should begin with "[" and end with "]".

    5. VALIDATION
    It is possible that even if a response was successfully parsed that it is not valid, given the constraints 
    of the Thought. For this reason, it is helpful to have a validation routine that stamps the response as valid 
    according to a fixed list of rules. "max_retries" is a param that tells the Thought how many times it can 
    retry the prompt before returning an error.


    Supported Operations:
        - llm_call: Execute an LLM request with prompt and context (default)
        - memory_query: Query memory state and return variables/data without LLM
        - variable_set: Set or compute memory variables from context
        - conditional: Execute logic based on memory conditions

    Key Features:
        - Callable interface: mem = thought(mem) or mem = thought(mem, vars)
        - Automatic retry with configurable attempts and repair prompts
        - Schema-based response parsing via valid_extract or custom parsers
        - Multiple validators: has_keys, list_min_len, custom callables
        - Pre/post hooks for custom processing
        - Full execution tracing and history
        - Serialization support via to_dict()/from_dict()
        - Channel support for message tracking

    Parameters:
        name (str): Unique identifier for this thought
        llm (LLM): LLM instance for execution (required for llm_call operation)
        prompt (str|dict): Prompt template with {variable} placeholders
        operation (str): Type of operation ('llm_call', 'memory_query', 'variable_set', 'conditional')
        system_prompt (str): Optional system prompt for LLM context (via config)
        parser (str|callable): Response parser ('text', 'json', 'list', or callable)
        parsing_rules (dict): Schema for valid_extract parsing (e.g., {'kind': 'python', 'format': []})
        validator (str|callable): Response validator ('any', 'has_keys:k1,k2', 'list_min_len:N', or callable)
        max_retries (int): Maximum retry attempts (default: 1)
        retry_delay (float): Delay between retries in seconds (default: 0)
        required_vars (list): Variables required from memory
        optional_vars (list): Optional variables from memory
        output_var (str): Variable name for storing result (default: '{name}_result')
        pre_hook (callable): Function called before execution: fn(thought, memory, vars, **kwargs)
        post_hook (callable): Function called after execution: fn(thought, memory, result, error)
        channel (str): Channel for message tracking (default: 'system')
        add_reflection (bool): Whether to add reflection on success (default: True)

    Example usage:
        # Basic LLM call with result storage
        mem = MEMORY()
        llm = LLM(model="openai:gpt-4o-mini", api_key="...")
        thought = THOUGHT(
            name="summarize",
            llm=llm,
            prompt="Summarize the last user message: {last_user_msg}",
            operation="llm_call"
        )
        mem = thought(mem)  # Executes the thought, updates memory with result
        result = mem.get_var("summarize_result")

        # Schema-based parsing example
        thought = THOUGHT(
            name="extract_info",
            llm=llm,
            prompt="Extract name and age from: {text}",
            parsing_rules={"kind": "python", "format": {"name": "", "age": 0}}
        )

        # Memory query example (no LLM)
        thought = THOUGHT(
            name="get_context",
            operation="memory_query",
            required_vars=["user_name", "session_id"]
        )

        # Variable set example
        thought = THOUGHT(
            name="init_session",
            operation="variable_set",
            prompt={"session_active": True, "start_time": None}  # dict of values to set
        )


    !!! IMPORTANT !!!
    The resulting functionality from this class must enable the following pattern:
    mem = thought(mem) # where mem is a MEMORY object
    or
    mem = thought(mem,vars) # where vars (optional)is a dictionary of variables to pass to the thought

    THOUGHT OPERATIONS MUST BE CALLABLE.

    """
    
    # Valid operation types
    VALID_OPERATIONS = {'llm_call', 'memory_query', 'variable_set', 'conditional'}

    def __init__(self, name=None, llm=None, prompt=None, operation=None, **kwargs):
        """
        Initialize a THOUGHT instance.

        Args:
            name (str): Name of the thought.
            llm: LLM interface or callable.
            prompt: Prompt template (str or dict).
            operation (str): Operation type (e.g., 'llm_call', 'memory_query', etc).
            **kwargs: Additional configuration parameters.
        """
        self.name = name
        self.id = event_stamp() 
        self.llm = llm
        self.prompt = prompt
        self.operation = operation

        # Store any additional configuration parameters
        self.config = kwargs.copy()

        # Optionally, store a description or docstring if provided
        self.description = kwargs.get("description", None)

        # Optionally, store validation rules, parsing functions, etc.
        self.validation = kwargs.get("validation", None)
        self.parse_fn = kwargs.get("parse_fn", None)
        self.max_retries = kwargs.get("max_retries", 1)
        self.retry_delay = kwargs.get("retry_delay", 0)

        # Optionally, store default context variables or requirements
        self.required_vars = kwargs.get("required_vars", [])
        self.optional_vars = kwargs.get("optional_vars", [])

        # Optionally, store output variable name
        self.output_var = kwargs.get("output_var", "{}_result".format(self.name) if self.name else None)

        # Internal state for tracking last result, errors, etc.
        self.last_result = None
        self.last_error = None
        self.last_prompt = None
        self.last_msgs = None
        self.last_response = None

        # Allow for custom hooks (pre/post processing)
        self.pre_hook = kwargs.get("pre_hook", None)
        self.post_hook = kwargs.get("post_hook", None)
        
        # Execution history tracking
        self.execution_history = []


    def __call__(self, memory, vars={}, **kwargs):
        """
        Execute the thought on the given MEMORY object.

        Args:
            memory: MEMORY object.
            vars: Optional dictionary of variables to pass to the thought.
            **kwargs: Additional parameters for execution.
        Returns:
            Updated MEMORY object with result stored (if applicable).
        """
        import time as time_module
        
        start_time = time_module.time()
        
        # Allow vars to be None
        if vars is None:
            vars = {}
        
        # Pre-hook
        if self.pre_hook and callable(self.pre_hook):
            self.pre_hook(self, memory, vars, **kwargs)

        # Determine operation type
        operation = self.operation or 'llm_call'
        
        # Dispatch to appropriate handler based on operation type
        if operation == 'llm_call':
            result, last_error, attempts_made = self._execute_llm_call(memory, vars, **kwargs)
        elif operation == 'memory_query':
            result, last_error, attempts_made = self._execute_memory_query(memory, vars, **kwargs)
        elif operation == 'variable_set':
            result, last_error, attempts_made = self._execute_variable_set(memory, vars, **kwargs)
        elif operation == 'conditional':
            result, last_error, attempts_made = self._execute_conditional(memory, vars, **kwargs)
        else:
            raise ValueError("Unknown operation: {}. Valid operations: {}".format(operation, self.VALID_OPERATIONS))
        
        # Calculate execution duration
        duration_ms = (time_module.time() - start_time) * 1000
        
        # Build execution event for logging
        execution_event = {
            'thought_name': self.name,
            'thought_id': self.id,
            'operation': operation,
            'attempts': attempts_made,
            'success': result is not None,
            'duration_ms': round(duration_ms, 2),
            'output_var': self.output_var
        }

        # If failed after all retries
        if result is None and last_error is not None:
            execution_event['error'] = last_error
            if hasattr(memory, "add_log") and callable(getattr(memory, "add_log", None)):
                memory.add_log("Thought execution failed: " + json.dumps(execution_event))
            # Store None as result
            self.update_memory(memory, None)
        else:
            if hasattr(memory, "add_log") and callable(getattr(memory, "add_log", None)):
                memory.add_log("Thought execution complete: " + json.dumps(execution_event))
            self.update_memory(memory, result)
        
        # Track execution history on the THOUGHT instance
        self.execution_history.append({
            'stamp': event_stamp(),
            'memory_id': getattr(memory, 'id', None),
            'operation': operation,
            'duration_ms': duration_ms,
            'success': result is not None or last_error is None,
            'attempts': attempts_made,
            'error': self.last_error
        })

        # Post-hook
        if self.post_hook and callable(self.post_hook):
            self.post_hook(self, memory, self.last_result, self.last_error)

        return memory

    def _execute_llm_call(self, memory, vars, **kwargs):
        """
        Execute an LLM call operation with retry logic.
        
        Returns:
            tuple: (result, last_error, attempts_made)
        """
        import copy as copy_module
        import time as time_module
        
        retries_left = self.max_retries
        last_error = None
        result = None
        attempts_made = 0
        
        # Store original prompt to avoid mutation - work with a copy
        original_prompt = copy_module.deepcopy(self.prompt)
        working_prompt = copy_module.deepcopy(self.prompt)

        while retries_left > 0:
            attempts_made += 1
            try:
                # Temporarily set working prompt for this iteration
                self.prompt = working_prompt
                
                # Build context and prompt/messages
                ctx = self.get_context(memory)
                ctx.update(vars)
                msgs = self.build_msgs(memory, ctx)

                # Run LLM
                llm_kwargs = self.config.get("llm_params", {})
                llm_kwargs.update(kwargs)
                response = self.run_llm(msgs, **llm_kwargs)
                self.last_response = response

                # Get channel from config for message tracking
                channel = self.config.get("channel", "system")
                
                # Add assistant message to memory (if possible)
                if hasattr(memory, "add_msg") and callable(getattr(memory, "add_msg", None)):
                    memory.add_msg("assistant", response, channel=channel)

                # Parse
                parsed = self.parse_response(response)
                self.last_result = parsed

                # Validate
                valid, why = self.validate(parsed)
                if valid:
                    result = parsed
                    self.last_error = None
                    # Logging
                    if hasattr(memory, "add_log") and callable(getattr(memory, "add_log", None)):
                        memory.add_log("Thought '{}' completed successfully".format(self.name))
                    # Add reflection for reasoning trace (if configured)
                    if self.config.get("add_reflection", True):
                        if hasattr(memory, "add_ref") and callable(getattr(memory, "add_ref", None)):
                            # Truncate response for reflection if too long
                            response_preview = str(response)[:300]
                            if len(str(response)) > 300:
                                response_preview += "..."
                            memory.add_ref("Thought '{}': {}".format(self.name, response_preview))
                    break
                else:
                    last_error = why
                    self.last_error = why
                    if hasattr(memory, "add_log") and callable(getattr(memory, "add_log", None)):
                        memory.add_log("Thought '{}' validation failed: {}".format(self.name, why))
                    # Create repair suffix for next retry (modify working_prompt, not original)
                    repair_suffix = "\n(Please return only the requested format; your last answer failed: {}.)" .format(why)
                    if isinstance(original_prompt, str):
                        working_prompt = original_prompt.rstrip() + repair_suffix
                    elif isinstance(original_prompt, dict):
                        working_prompt = copy_module.deepcopy(original_prompt)
                        last_key = list(working_prompt.keys())[-1]
                        working_prompt[last_key] = working_prompt[last_key].rstrip() + repair_suffix
            except Exception as e:
                last_error = str(e)
                self.last_error = last_error
                if hasattr(memory, "add_log") and callable(getattr(memory, "add_log", None)):
                    memory.add_log("Thought '{}' error: {}".format(self.name, last_error))
                # Create repair suffix for next retry (modify working_prompt, not original)
                repair_suffix = "\n(Please return only the requested format; your last answer failed: {}.)".format(last_error)
                if isinstance(original_prompt, str):
                    working_prompt = original_prompt.rstrip() + repair_suffix
                elif isinstance(original_prompt, dict):
                    working_prompt = copy_module.deepcopy(original_prompt)
                    last_key = list(working_prompt.keys())[-1]
                    working_prompt[last_key] = working_prompt[last_key].rstrip() + repair_suffix
            retries_left -= 1
            if self.retry_delay:
                time_module.sleep(self.retry_delay)

        # Restore original prompt after execution (prevents permanent mutation)
        self.prompt = original_prompt
        
        return result, last_error, attempts_made

    def _execute_memory_query(self, memory, vars, **kwargs):
        """
        Execute a memory query operation (no LLM involved).
        Retrieves specified variables from memory and returns them as a dict.
        
        Returns:
            tuple: (result, last_error, attempts_made)
        """
        try:
            result = {}
            
            # Get required variables
            for var in self.required_vars:
                if hasattr(memory, "get_var") and callable(getattr(memory, "get_var", None)):
                    val = memory.get_var(var)
                else:
                    val = getattr(memory, var, None)
                
                if val is None:
                    return None, "Required variable '{}' not found in memory".format(var), 1
                result[var] = val
            
            # Get optional variables
            for var in self.optional_vars:
                if hasattr(memory, "get_var") and callable(getattr(memory, "get_var", None)):
                    val = memory.get_var(var)
                else:
                    val = getattr(memory, var, None)
                
                if val is not None:
                    result[var] = val
            
            # Include any vars passed directly
            result.update(vars)
            
            self.last_result = result
            self.last_error = None
            
            if hasattr(memory, "add_log") and callable(getattr(memory, "add_log", None)):
                memory.add_log("Thought '{}' memory query completed".format(self.name))
            
            return result, None, 1
            
        except Exception as e:
            self.last_error = str(e)
            return None, str(e), 1

    def _execute_variable_set(self, memory, vars, **kwargs):
        """
        Execute a variable set operation.
        Sets variables in memory from the prompt (as dict) or vars parameter.
        
        Returns:
            tuple: (result, last_error, attempts_made)
        """
        try:
            values_to_set = {}
            
            # If prompt is a dict, use it as the values to set
            if isinstance(self.prompt, dict):
                values_to_set.update(self.prompt)
            
            # Override/add with vars parameter
            values_to_set.update(vars)
            
            # Set each variable in memory
            for key, value in values_to_set.items():
                if hasattr(memory, "set_var") and callable(getattr(memory, "set_var", None)):
                    desc = self.config.get("var_descriptions", {}).get(key, "Set by thought: {}".format(self.name))
                    memory.set_var(key, value, desc=desc)
                elif hasattr(memory, "vars"):
                    if key not in memory.vars:
                        memory.vars[key] = []
                    stamp = event_stamp(value)
                    memory.vars[key].append([stamp, value])
            
            self.last_result = values_to_set
            self.last_error = None
            
            if hasattr(memory, "add_log") and callable(getattr(memory, "add_log", None)):
                memory.add_log("Thought '{}' set {} variables".format(self.name, len(values_to_set)))
            
            return values_to_set, None, 1
            
        except Exception as e:
            self.last_error = str(e)
            return None, str(e), 1

    def _execute_conditional(self, memory, vars, **kwargs):
        """
        Execute a conditional operation.
        Evaluates a condition from config and returns the appropriate result.
        
        Config options:
            condition (callable): Function that takes (memory, vars) and returns bool
            if_true: Value/action if condition is true
            if_false: Value/action if condition is false
        
        Returns:
            tuple: (result, last_error, attempts_made)
        """
        try:
            condition_fn = self.config.get("condition")
            if_true = self.config.get("if_true")
            if_false = self.config.get("if_false")
            
            if condition_fn is None:
                return None, "No condition function provided for conditional operation", 1
            
            if not callable(condition_fn):
                return None, "Condition must be callable", 1
            
            # Evaluate condition
            ctx = self.get_context(memory)
            ctx.update(vars)
            condition_result = condition_fn(memory, ctx)
            
            # Return appropriate value
            if condition_result:
                result = if_true
                if callable(if_true):
                    result = if_true(memory, ctx)
            else:
                result = if_false
                if callable(if_false):
                    result = if_false(memory, ctx)
            
            self.last_result = result
            self.last_error = None
            
            if hasattr(memory, "add_log") and callable(getattr(memory, "add_log", None)):
                memory.add_log("Thought '{}' conditional evaluated to {}".format(self.name, bool(condition_result)))
            
            return result, None, 1
            
        except Exception as e:
            self.last_error = str(e)
            return None, str(e), 1

    def build_prompt(self, memory, context_vars=None):
        """
        Build the prompt for the LLM using construct_prompt.

        Args:
            memory: MEMORY object providing context.
            context_vars (dict): Optional context variables to fill the prompt.

        Returns:
            str: The constructed prompt string.
        """
        # Get context variables (merge get_context and context_vars)
        ctx = self.get_context(memory)
        if context_vars:
            ctx.update(context_vars)
        prompt_template = self.prompt
        # If prompt is a dict, use construct_prompt, else format as string
        if isinstance(prompt_template, dict):
            prompt = construct_prompt(prompt_template)
        elif isinstance(prompt_template, str):
            try:
                prompt = prompt_template.format(**ctx)
            except Exception:
                # fallback: just return as is
                prompt = prompt_template
        else:
            prompt = str(prompt_template)
        self.last_prompt = prompt
        return prompt

    def build_msgs(self, memory, context_vars=None):
        """
        Build the messages list for the LLM using construct_msgs.

        Args:
            memory: MEMORY object providing context.
            context_vars (dict): Optional context variables to fill the prompt.

        Returns:
            list: List of message dicts for LLM input.
        """
        ctx = self.get_context(memory)
        if context_vars:
            ctx.update(context_vars)
        # Compose system and user prompts
        sys_prompt = self.config.get("system_prompt", "")
        usr_prompt = self.build_prompt(memory, ctx)
        # Optionally, allow for prior messages from memory
        msgs = []
        if hasattr(memory, "get_msgs"):
            # Optionally, get recent messages for context
            msgs = memory.get_msgs(repr="list") if callable(getattr(memory, "get_msgs", None)) else []
        # Build messages using construct_msgs
        msgs_out = construct_msgs(
            usr_prompt=usr_prompt,
            vars=ctx,
            sys_prompt=sys_prompt,
            msgs=msgs
        )
        self.last_msgs = msgs_out
        return msgs_out

    def get_context(self, memory):
        """
        Extract relevant context from the MEMORY object for this thought.

        Args:
            memory: MEMORY object.

        Returns:
            dict: Context variables for prompt filling.
        """
        ctx = {}
        # If required_vars is specified, try to get those from memory
        if hasattr(self, "required_vars") and self.required_vars:
            for var in self.required_vars:
                # Try to get from memory.get_var if available
                if hasattr(memory, "get_var") and callable(getattr(memory, "get_var", None)):
                    val = memory.get_var(var)
                else:
                    val = getattr(memory, var, None)
                if val is not None:
                    ctx[var] = val
        # Optionally, add optional_vars if present in memory
        if hasattr(self, "optional_vars") and self.optional_vars:
            for var in self.optional_vars:
                if hasattr(memory, "get_var") and callable(getattr(memory, "get_var", None)):
                    val = memory.get_var(var)
                else:
                    val = getattr(memory, var, None)
                if val is not None:
                    ctx[var] = val
        # Add some common context keys if available
        if hasattr(memory, "last_user_msg") and callable(getattr(memory, "last_user_msg", None)):
            ctx["last_user_msg"] = memory.last_user_msg()
        if hasattr(memory, "last_asst_msg") and callable(getattr(memory, "last_asst_msg", None)):
            ctx["last_asst_msg"] = memory.last_asst_msg()
        if hasattr(memory, "get_msgs") and callable(getattr(memory, "get_msgs", None)):
            ctx["messages"] = memory.get_msgs(repr="list")
        # Add all memory.vars if present
        if hasattr(memory, "vars"):
            ctx.update(getattr(memory, "vars", {}))
        return ctx

    def run_llm(self, msgs, **llm_kwargs):
        """
        Execute the LLM call with the given messages.
        !!! USE THE EXISTING LLM CLASS !!!

        Args:
            msgs (list): List of message dicts.
            **llm_kwargs: Additional LLM parameters.

        Returns:
            str: Raw LLM response.
        """
        if self.llm is None:
            raise ValueError("No LLM instance provided to this THOUGHT.")
        # The LLM class is expected to be callable: llm(msgs, **kwargs)
        # If LLM is a class with .call, use that (standard interface)
        if hasattr(self.llm, "call") and callable(getattr(self.llm, "call", None)):
            response = self.llm.call(msgs, llm_kwargs)
        elif hasattr(self.llm, "chat") and callable(getattr(self.llm, "chat", None)):
            response = self.llm.chat(msgs, **llm_kwargs)
        else:
            response = self.llm(msgs, **llm_kwargs)
        
        # Handle list response from LLM.call() - it returns a list of choices
        if isinstance(response, list):
            response = response[0] if response else ""
        
        # If response is a dict with 'content', extract it
        if isinstance(response, dict) and "content" in response:
            return response["content"]
        
        return response

    def parse_response(self, response):
        """
        Parse the LLM response to extract the desired content.

        Args:
            response (str): Raw LLM response.

        Returns:
            object: Parsed result (e.g., string, list, dict).
        
        Supports:
            - Custom parse_fn callable
            - Schema-based parsing via parsing_rules (uses valid_extract)
            - Built-in parsers: 'text', 'json', 'list'
        """
        # Use custom parse_fn if provided
        if self.parse_fn and callable(self.parse_fn):
            return self.parse_fn(response)
        
        # Check for schema-based parsing rules (using valid_extract)
        parsing_rules = self.config.get("parsing_rules")
        if parsing_rules:
            try:
                return valid_extract(response, parsing_rules)
            except ValidExtractError as e:
                raise ValueError("Schema-based parsing failed: {}".format(e))
        
        # Use built-in parser based on config
        parser = self.config.get("parser", None)
        if parser is None:
            # Default: return as string
            return response
        if parser == "text":
            return response
        elif parser == "json":
            import re
            # Remove code fences if present
            text = response.strip()
            text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
            # Find first JSON object or array
            match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
            if match:
                json_str = match.group(1)
                return json.loads(json_str)
            else:
                raise ValueError("No JSON object or array found in response.")
        elif parser == "list":
            import ast, re
            # Find first list literal
            match = re.search(r"(\[.*\])", response, re.DOTALL)
            if match:
                list_str = match.group(1)
                return ast.literal_eval(list_str)
            else:
                raise ValueError("No list found in response.")
        elif callable(parser):
            return parser(response)
        else:
            # Unknown parser, return as is
            return response

    def validate(self, parsed_result):
        """
        Validate the parsed result according to the thought's rules.

        Args:
            parsed_result: The parsed output from the LLM.

        Returns:
            (bool, why): True if valid, False otherwise, and reason string.
        """
        # Use custom validation if provided
        if self.validation and callable(self.validation):
            try:
                valid, why = self.validation(parsed_result)
                return bool(valid), why
            except Exception as e:
                return False, "Validation exception: {}".format(e)
        # Use built-in validator based on config
        validator = self.config.get("validator", None)
        if validator is None or validator == "any":
            return True, ""
        elif isinstance(validator, str):
            if validator.startswith("has_keys:"):
                keys = [k.strip() for k in validator.split(":", 1)[1].split(",")]
                if isinstance(parsed_result, dict):
                    missing = [k for k in keys if k not in parsed_result]
                    if not missing:
                        return True, ""
                    else:
                        return False, "Missing keys: {}".format(missing)
                else:
                    return False, "Result is not a dict"
            elif validator.startswith("list_min_len:"):
                try:
                    min_len = int(validator.split(":", 1)[1])
                except Exception:
                    min_len = 1
                if isinstance(parsed_result, list) and len(parsed_result) >= min_len:
                    return True, ""
                else:
                    return False, "List too short (min {})".format(min_len)
            elif validator == "summary_v1":
                # Example: summary must be a string of at least 10 chars
                if isinstance(parsed_result, str) and len(parsed_result.strip()) >= 10:
                    return True, ""
                else:
                    return False, "Summary too short"
            else:
                return True, ""
        elif callable(validator):
            try:
                valid, why = validator(parsed_result)
                return bool(valid), why
            except Exception as e:
                return False, "Validation exception: {}".format(e)
        else:
            return True, ""

    def update_memory(self, memory, result):
        """
        Update the MEMORY object with the result of this thought.

        Args:
            memory: MEMORY object.
            result: The result to store.

        Returns:
            MEMORY: Updated memory object.
        """
        # Store result in vars or via set_var if available
        varname = self.output_var or ("{}_result".format(self.name) if self.name else "thought_result")
        if hasattr(memory, "set_var") and callable(getattr(memory, "set_var", None)):
            memory.set_var(varname, result, desc="Result of thought: {}".format(self.name))
        elif hasattr(memory, "vars"):
            # Fallback: directly access vars dict if set_var not available
            if varname not in memory.vars:
                memory.vars[varname] = []
            stamp = event_stamp(result) if 'event_stamp' in globals() else 'no_stamp'
            memory.vars[varname].append({'object': result, 'stamp': stamp})
        else:
            setattr(memory, varname, result)
        return memory

    def to_dict(self):
        """
        Return a serializable dictionary representation of this THOUGHT.
        
        Note: The LLM instance, parse_fn, validation, and hooks cannot be serialized,
        so they are represented by type/name only. When deserializing, these must be
        provided separately.
        
        Returns:
            dict: Serializable representation of this thought.
        """
        return {
            "name": self.name,
            "id": self.id,
            "prompt": self.prompt,
            "operation": self.operation,
            "config": self.config,
            "description": self.description,
            "max_retries": self.max_retries,
            "retry_delay": self.retry_delay,
            "output_var": self.output_var,
            "required_vars": self.required_vars,
            "optional_vars": self.optional_vars,
            "execution_history": self.execution_history,
            # Store metadata about non-serializable items
            "llm_type": type(self.llm).__name__ if self.llm else None,
            "has_parse_fn": self.parse_fn is not None,
            "has_validation": self.validation is not None,
            "has_pre_hook": self.pre_hook is not None,
            "has_post_hook": self.post_hook is not None,
        }

    @classmethod
    def from_dict(cls, data, llm=None, parse_fn=None, validation=None, pre_hook=None, post_hook=None):
        """
        Reconstruct a THOUGHT from a dictionary representation.
        
        Args:
            data (dict): Dictionary representation of a THOUGHT.
            llm: LLM instance to use (required for execution).
            parse_fn: Optional custom parse function.
            validation: Optional custom validation function.
            pre_hook: Optional pre-execution hook.
            post_hook: Optional post-execution hook.
            
        Returns:
            THOUGHT: Reconstructed THOUGHT object.
        """
        # Extract config and merge with explicit kwargs
        config = data.get("config", {}).copy()
        
        thought = cls(
            name=data.get("name"),
            llm=llm,
            prompt=data.get("prompt"),
            operation=data.get("operation"),
            description=data.get("description"),
            max_retries=data.get("max_retries", 1),
            retry_delay=data.get("retry_delay", 0),
            output_var=data.get("output_var"),
            required_vars=data.get("required_vars", []),
            optional_vars=data.get("optional_vars", []),
            parse_fn=parse_fn,
            validation=validation,
            pre_hook=pre_hook,
            post_hook=post_hook,
            **config
        )
        
        # Restore ID if provided
        if data.get("id"):
            thought.id = data["id"]
        
        # Restore execution history
        thought.execution_history = data.get("execution_history", [])
        
        return thought

    def copy(self):
        """
        Return a deep copy of this THOUGHT.
        
        Note: The LLM instance is shallow-copied (same reference), as LLM
        instances typically should be shared. All other attributes are deep-copied.
        
        Returns:
            THOUGHT: A new THOUGHT instance with copied attributes.
        """
        import copy as copy_module
        
        new_thought = THOUGHT(
            name=self.name,
            llm=self.llm,  # Shallow copy - same LLM instance
            prompt=copy_module.deepcopy(self.prompt),
            operation=self.operation,
            description=self.description,
            max_retries=self.max_retries,
            retry_delay=self.retry_delay,
            output_var=self.output_var,
            required_vars=copy_module.deepcopy(self.required_vars),
            optional_vars=copy_module.deepcopy(self.optional_vars),
            parse_fn=self.parse_fn,
            validation=self.validation,
            pre_hook=self.pre_hook,
            post_hook=self.post_hook,
            **copy_module.deepcopy(self.config)
        )
        
        # Copy internal state
        new_thought.id = event_stamp()  # Generate new ID for the copy
        new_thought.execution_history = copy_module.deepcopy(self.execution_history)
        new_thought.last_result = copy_module.deepcopy(self.last_result)
        new_thought.last_error = self.last_error
        new_thought.last_prompt = self.last_prompt
        new_thought.last_msgs = copy_module.deepcopy(self.last_msgs)
        new_thought.last_response = self.last_response
        
        return new_thought

    def __repr__(self):
        """
        Return a detailed string representation of this THOUGHT.
        
        Returns:
            str: Detailed representation including key attributes.
        """
        return ("THOUGHT(name='{}', operation='{}', "
                "max_retries={}, output_var='{}')".format(
                    self.name, self.operation, self.max_retries, self.output_var))

    def __str__(self):
        """
        Return a human-readable string representation of this THOUGHT.
        
        Returns:
            str: Simple description of the thought.
        """
        return "Thought: {}".format(self.name or 'unnamed')






ThoughtClassTests = """
# --- THOUGHT Class Tests ---

# Test 1: Basic THOUGHT instantiation and attributes
>>> from thoughtflow6 import THOUGHT, MEMORY, event_stamp
>>> t = THOUGHT(name="test_thought", prompt="Hello {name}", max_retries=3)
>>> t.name
'test_thought'
>>> t.max_retries
3
>>> t.output_var
'test_thought_result'
>>> t.operation is None  # Defaults to None, which means 'llm_call'
True
>>> len(t.execution_history)
0

# Test 2: Serialization round-trip with to_dict/from_dict
>>> t1 = THOUGHT(name="serialize_test", prompt="test prompt", max_retries=3, output_var="my_output")
>>> data = t1.to_dict()
>>> data['name']
'serialize_test'
>>> data['max_retries']
3
>>> data['output_var']
'my_output'
>>> t2 = THOUGHT.from_dict(data)
>>> t2.name == t1.name
True
>>> t2.max_retries == t1.max_retries
True
>>> t2.output_var == t1.output_var
True

# Test 3: Copy creates independent instance
>>> t1 = THOUGHT(name="copy_test", prompt="original prompt")
>>> t2 = t1.copy()
>>> t2.name = "modified"
>>> t1.name
'copy_test'
>>> t2.name
'modified'
>>> t1.id != t2.id  # Copy gets new ID
True

# Test 4: __repr__ and __str__
>>> t = THOUGHT(name="repr_test", operation="llm_call", max_retries=2, output_var="result")
>>> "repr_test" in repr(t)
True
>>> "llm_call" in repr(t)
True
>>> str(t)
'Thought: repr_test'
>>> t2 = THOUGHT()  # unnamed
>>> str(t2)
'Thought: unnamed'

# Test 5: Memory query operation (no LLM)
>>> mem = MEMORY()
>>> mem.set_var("user_name", "Alice", desc="Test user")
>>> mem.set_var("session_id", "sess123", desc="Test session")
>>> t = THOUGHT(
...     name="query_test",
...     operation="memory_query",
...     required_vars=["user_name", "session_id"]
... )
>>> mem2 = t(mem)
>>> result = mem2.get_var("query_test_result")
>>> result['user_name']
'Alice'
>>> result['session_id']
'sess123'

# Test 6: Variable set operation
>>> mem = MEMORY()
>>> t = THOUGHT(
...     name="setvar_test",
...     operation="variable_set",
...     prompt={"status": "active", "count": 42}
... )
>>> mem2 = t(mem)
>>> mem2.get_var("status")
'active'
>>> mem2.get_var("count")
42

# Test 7: Execution history tracking
>>> mem = MEMORY()
>>> t = THOUGHT(name="history_test", operation="memory_query", required_vars=[])
>>> len(t.execution_history)
0
>>> mem = t(mem)
>>> len(t.execution_history)
1
>>> t.execution_history[0]['success']
True
>>> 'duration_ms' in t.execution_history[0]
True
>>> 'stamp' in t.execution_history[0]
True

# Test 8: Conditional operation
>>> mem = MEMORY()
>>> mem.set_var("threshold", 50)
>>> t = THOUGHT(
...     name="cond_test",
...     operation="conditional",
...     condition=lambda m, ctx: ctx.get('value', 0) > ctx.get('threshold', 0),
...     if_true="above",
...     if_false="below"
... )
>>> mem2 = t(mem, vars={'value': 75})
>>> mem2.get_var("cond_test_result")
'above'
>>> mem3 = t(mem, vars={'value': 25})
>>> mem3.get_var("cond_test_result")
'below'

# Test 9: VALID_OPERATIONS class attribute
>>> 'llm_call' in THOUGHT.VALID_OPERATIONS
True
>>> 'memory_query' in THOUGHT.VALID_OPERATIONS
True
>>> 'variable_set' in THOUGHT.VALID_OPERATIONS
True
>>> 'conditional' in THOUGHT.VALID_OPERATIONS
True

# Test 10: Parse response with parsing_rules (valid_extract integration)
>>> t = THOUGHT(name="parse_test", parsing_rules={"kind": "python", "format": []})
>>> t.parse_response("Here is the list: [1, 2, 3]")
[1, 2, 3]
>>> t2 = THOUGHT(name="parse_dict", parsing_rules={"kind": "python", "format": {"name": "", "count": 0}})
>>> t2.parse_response("Result: {'name': 'test', 'count': 5}")
{'name': 'test', 'count': 5}

# Test 11: Built-in parsers
>>> t = THOUGHT(name="json_test", parser="json")
>>> t.parse_response('Here is JSON: {"key": "value"}')
{'key': 'value'}
>>> t2 = THOUGHT(name="list_test", parser="list")
>>> t2.parse_response("Numbers: [1, 2, 3, 4, 5]")
[1, 2, 3, 4, 5]
>>> t3 = THOUGHT(name="text_test", parser="text")
>>> t3.parse_response("plain text")
'plain text'

# Test 12: Built-in validators
>>> t = THOUGHT(name="val_test", validator="has_keys:name,age")
>>> t.validate({"name": "Alice", "age": 30})
(True, '')
>>> t.validate({"name": "Bob"})
(False, 'Missing keys: [\\'age\\']')
>>> t2 = THOUGHT(name="list_val", validator="list_min_len:3")
>>> t2.validate([1, 2, 3])
(True, '')
>>> t2.validate([1, 2])
(False, 'List too short (min 3)')

"""


#############################################################################
#############################################################################

### ACTION CLASS


class ACTION:
    """
    The ACTION class encapsulates an external or internal operation that can be invoked within a Thoughtflow agent.
    It is designed to represent a single, named action (such as a tool call, API request, or function) whose result
    is stored in the agent's state for later inspection, branching, or retry.
    
    An ACTION represents a discrete, named operation (function, API call, tool invocation) that can be defined once
    and executed multiple times with different parameters. When executed, the ACTION handles logging, error management,
    and result storage in a consistent way.
    
    Attributes:
        name (str): Identifier for this action, used for logging and storing results.
        id (str): Unique identifier for this action instance (event_stamp).
        fn (callable): The function to execute when this action is called.
        config (dict): Default configuration parameters that will be passed to the function.
        result_key (str): Key where results are stored in memory (defaults to "{name}_result").
        description (str): Human-readable description of what this action does.
        last_result (Any): The most recent result from executing this action.
        last_error (Exception): The most recent error from executing this action, if any.
        execution_count (int): Number of times this action has been executed.
        execution_history (list): Full execution history with timing and success/error tracking.
    
    Methods:
        __init__(name, fn, config=None, result_key=None, description=None):
            Initializes an ACTION with a name, function, and optional configuration.
            
        __call__(memory, **kwargs):
            Executes the action function with the memory object and any override parameters.
            The function receives (memory, **merged_kwargs) where merged_kwargs combines
            self.config with any call-specific kwargs.
            
            Returns the memory object with results stored via set_var.
            Logs execution details with JSON-formatted event data.
            Tracks execution timing and history.
            
            Handles exceptions during execution by logging them rather than raising them,
            allowing the workflow to continue and decide how to handle failures.
            
        get_last_result():
            Returns the most recent result from executing this action.
            
        was_successful():
            Returns True if the last execution was successful, False otherwise.
            
        reset_stats():
            Resets execution statistics (count, last_result, last_error, execution_history).
            
        copy():
            Returns a copy of this ACTION with a new ID and reset statistics.
            
        to_dict():
            Returns a serializable dictionary representation of this action.
            
        from_dict(cls, data, fn_registry):
            Class method to reconstruct an ACTION from a dictionary representation.
    
    Example Usage:
        # Define a web search action
        def search_web(memory, query, max_results=3):
            # Implementation of web search
            results = web_api.search(query, limit=max_results)
            return {"status": "success", "hits": results}
            
        search_action = ACTION(
            name="web_search",
            fn=search_web,
            config={"max_results": 5},
            description="Searches the web for information"
        )
        
        # Execute the action
        memory = MEMORY()
        memory = search_action(memory, query="thoughtflow framework")
        
        # Access results
        result = memory.get_var("web_search_result")
        
        # Check execution history
        print(search_action.execution_history[-1]['duration_ms'])  # Execution time
        print(search_action.execution_history[-1]['success'])      # True/False
    
    Design Principles:
        1. Explicit and inspectable operations with consistent logging
        2. Predictable result storage via memory.set_var
        3. Error handling that doesn't interrupt workflow execution
        4. Composability with other Thoughtflow components (MEMORY, THOUGHT)
        5. Serialization support for reproducibility
        6. Full execution history with timing for debugging and optimization
    """
    
    def __init__(self, name, fn, config=None, result_key=None, description=None):
        """
        Initialize an ACTION with a name, function, and optional configuration.
        
        Args:
            name (str): Identifier for this action, used for logging and result storage.
            fn (callable): The function to execute when this action is called.
            config (dict, optional): Default configuration parameters passed to the function.
            result_key (str, optional): Key where results are stored in memory (defaults to "{name}_result").
            description (str, optional): Human-readable description of what this action does.
        """
        self.name = name
        self.id = event_stamp()  # Unique identifier for this action instance
        self.fn = fn
        self.config = config or {}
        self.result_key = result_key or "{}_result".format(name)
        self.description = description or "Action: {}".format(name)
        self.last_result = None
        self.last_error = None
        self.execution_count = 0
        self.execution_history = []  # Full execution tracking with timing
    
    def __call__(self, memory, **kwargs):
        """
        Execute the action function with the memory object and any override parameters.
        
        Args:
            memory (MEMORY): The memory object to update with results.
            **kwargs: Parameters that override the default config for this execution.
            
        Returns:
            MEMORY: The updated memory object with results stored in memory.vars[result_key].
            
        Note:
            The function receives (memory, **merged_kwargs) where merged_kwargs combines
            self.config with any call-specific kwargs.
            
            Exceptions during execution are logged rather than raised, allowing the
            workflow to continue and decide how to handle failures.
        """
        import time as time_module
        
        start_time = time_module.time()
        
        # Merge default config with call-specific kwargs
        merged_kwargs = {**self.config, **kwargs}
        self.execution_count += 1
        
        try:
            # Execute the function
            result = self.fn(memory, **merged_kwargs)
            self.last_result = result
            self.last_error = None
            
            # Calculate execution duration
            duration_ms = (time_module.time() - start_time) * 1000
            
            # Store result in memory using set_var (correct API)
            if hasattr(memory, "set_var") and callable(getattr(memory, "set_var", None)):
                memory.set_var(self.result_key, result, desc="Result of action: {}".format(self.name))
            
            # Build execution event for logging (JSON format like THOUGHT)
            execution_event = {
                'action_name': self.name,
                'action_id': self.id,
                'status': 'success',
                'duration_ms': round(duration_ms, 2),
                'result_key': self.result_key
            }
            
            # Log successful execution (single message with JSON, no invalid details param)
            if hasattr(memory, "add_log") and callable(getattr(memory, "add_log", None)):
                memory.add_log("Action execution complete: " + json.dumps(execution_event))
            
            # Track execution history
            self.execution_history.append({
                'stamp': event_stamp(),
                'memory_id': getattr(memory, 'id', None),
                'duration_ms': duration_ms,
                'success': True,
                'error': None
            })
                
        except Exception as e:
            # Handle and log exceptions
            self.last_error = e
            
            # Calculate execution duration
            duration_ms = (time_module.time() - start_time) * 1000
            
            # Build error event for logging
            error_event = {
                'action_name': self.name,
                'action_id': self.id,
                'status': 'error',
                'error': str(e),
                'duration_ms': round(duration_ms, 2),
                'result_key': self.result_key
            }
            
            # Log failed execution (single message with JSON)
            if hasattr(memory, "add_log") and callable(getattr(memory, "add_log", None)):
                memory.add_log("Action execution failed: " + json.dumps(error_event))
            
            # Store error info in memory using set_var
            if hasattr(memory, "set_var") and callable(getattr(memory, "set_var", None)):
                memory.set_var(self.result_key, error_event, desc="Error in action: {}".format(self.name))
            
            # Track execution history
            self.execution_history.append({
                'stamp': event_stamp(),
                'memory_id': getattr(memory, 'id', None),
                'duration_ms': duration_ms,
                'success': False,
                'error': str(e)
            })
        
        return memory
    
    def get_last_result(self):
        """
        Returns the most recent result from executing this action.
        
        Returns:
            Any: The last result or None if the action hasn't been executed.
        """
        return self.last_result
    
    def was_successful(self):
        """
        Returns True if the last execution was successful, False otherwise.
        
        Returns:
            bool: True if the last execution completed without errors, False otherwise.
        """
        return self.last_error is None and self.execution_count > 0
    
    def reset_stats(self):
        """
        Resets execution statistics (count, last_result, last_error, execution_history).
        
        Returns:
            ACTION: Self for method chaining.
        """
        self.execution_count = 0
        self.last_result = None
        self.last_error = None
        self.execution_history = []
        return self
    
    def copy(self):
        """
        Return a copy of this ACTION with a new ID.
        
        The function reference is shared (same callable), but config is copied.
        Execution statistics are reset in the copy.
        
        Returns:
            ACTION: A new ACTION instance with copied attributes and new ID.
        """
        new_action = ACTION(
            name=self.name,
            fn=self.fn,  # Same function reference
            config=self.config.copy() if self.config else None,
            result_key=self.result_key,
            description=self.description
        )
        # New ID is already assigned in __init__, no need to set it
        return new_action
    
    def to_dict(self):
        """
        Returns a serializable dictionary representation of this action.
        
        Note: The function itself cannot be serialized, so it's represented by name.
        When deserializing, a function registry must be provided.
        
        Returns:
            dict: Serializable representation of this action.
        """
        return {
            "name": self.name,
            "id": self.id,
            "fn_name": self.fn.__name__,
            "config": self.config,
            "result_key": self.result_key,
            "description": self.description,
            "execution_count": self.execution_count,
            "execution_history": self.execution_history
        }
    
    @classmethod
    def from_dict(cls, data, fn_registry):
        """
        Reconstruct an ACTION from a dictionary representation.
        
        Args:
            data (dict): Dictionary representation of an ACTION.
            fn_registry (dict): Dictionary mapping function names to function objects.
            
        Returns:
            ACTION: Reconstructed ACTION object.
            
        Raises:
            KeyError: If the function name is not found in the registry.
        """
        if data["fn_name"] not in fn_registry:
            raise KeyError("Function '{}' not found in registry".format(data['fn_name']))
            
        action = cls(
            name=data["name"],
            fn=fn_registry[data["fn_name"]],
            config=data["config"],
            result_key=data["result_key"],
            description=data["description"]
        )
        # Restore ID if provided, otherwise keep the new one from __init__
        if data.get("id"):
            action.id = data["id"]
        action.execution_count = data.get("execution_count", 0)
        action.execution_history = data.get("execution_history", [])
        return action
    
    def __str__(self):
        """
        Returns a string representation of this action.
        
        Returns:
            str: String representation.
        """
        return "ACTION({}, desc='{}', executions={})".format(self.name, self.description, self.execution_count)
    
    def __repr__(self):
        """
        Returns a detailed string representation of this action.
        
        Returns:
            str: Detailed string representation.
        """
        return ("ACTION(name='{}', fn={}, "
                "config={}, result_key='{}', "
                "description='{}', execution_count={})".format(
                    self.name, self.fn.__name__, self.config, 
                    self.result_key, self.description, self.execution_count))


### ACTION CLASS TESTS

ActionClassTests = """
# --- ACTION Class Tests ---


"""

#############################################################################
#############################################################################
























