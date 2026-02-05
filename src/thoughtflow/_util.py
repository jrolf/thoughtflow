"""
Internal utilities for ThoughtFlow.

This module contains helper functions and classes used by ThoughtFlow.
"""

from __future__ import annotations

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

### VAR_DELETED SENTINEL

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


#############################################################################
#############################################################################

### OBJECT COMPRESSION UTILITIES

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
