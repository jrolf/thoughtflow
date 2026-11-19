"""
MEMORY class for ThoughtFlow.

The MEMORY class serves as an event-sourced state container for managing events, 
logs, messages, reflections, and variables within the ThoughtFlow framework.

Example:
    >>> from thoughtflow import MEMORY
    >>>
    >>> memory = MEMORY()
    >>> memory.add_msg('user', 'Hello!', channel='webapp')
    >>> memory.add_msg('assistant', 'Hi there!', channel='webapp')
    >>> memory.set_var('session_id', 'abc123', desc='Current session')
    >>>
    >>> # Get messages
    >>> memory.get_msgs(include=['user'])
    >>>
    >>> # Prepare context for LLM
    >>> context = memory.prepare_context(format='openai')
    >>>
    >>> # Save/load state
    >>> memory.save('memory.pkl')
    >>> memory.to_json('memory.json')
"""

from __future__ import annotations

import json
import copy
import bisect
import os
import pickle
import pprint
import tempfile
import threading
import datetime as dtt

from thoughtflow._util import (
    event_stamp,
    VAR_DELETED,
    compress_to_json,
    decompress_from_json,
    estimate_size,
    is_obj_ref,
    truncate_content,
    tz_bog,
    tz_utc,
)


# Module-level lock guarding atomic copy-on-write updates to MEMORY.valid_channels
# when concurrent worker threads construct scopes with custom room names. Kept off
# MEMORY instances so copy.deepcopy() and pickle serialization stay unaffected.
_SCOPE_CHANNEL_LOCK = threading.Lock()


def _register_valid_channels(base_memory, channels):
    """Atomically register custom room/channel names on ``base_memory.valid_channels``."""
    clean = {ch for ch in channels if ch}
    if not clean or clean.issubset(base_memory.valid_channels):
        return
    with _SCOPE_CHANNEL_LOCK:
        if not clean.issubset(base_memory.valid_channels):
            base_memory.valid_channels = base_memory.valid_channels | clean


class MEMORY:
    """
    The MEMORY class serves as an event-sourced state container for managing events, 
    logs, messages, reflections, and variables within the ThoughtFlow framework. 
    
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
        add_msg(role, content, mode='text', channel='unknown', metadata=None): Add a message event with channel and optional metadata.
        add_augment(content, target='last_user', ...): Add tagged context for optional LLM-view merging.
        get_llm_msgs(merge_augments=False, ...): Build LLM-ready message dicts; optional augment folding.
        add_log(message): Add a log event.
        add_ref(content): Add a reflection event.
        emit(kind, payload, schema_version=1): Store a typed machine-readable lifecycle event.
        get_emits(kind=None, limit=-1): Retrieve typed emit events in chronological order.
        add_exchange(kind, key, service, model, request, response): Record an LLM/EMBED exchange (powers record/replay).
        get_exchanges(kind=None): Get recorded model exchanges.
        get_msgs(...): Retrieve messages with filtering (supports channel filter).
        get_events(...): Retrieve all events with filtering.
        get_logs(limit=-1): Get log events.
        get_refs(limit=-1): Get reflection events.
        last_user_msg(): Get the last user message content.
        last_asst_msg(): Get the last assistant message content.
        last_sys_msg(): Get the last system message content.
        last_log_msg(): Get the last log message content.
        last_result_msg(): Get the last result message.
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
        """
        Initialize an empty event-sourced MEMORY container.

        Sets up four internal layers: ``events`` (stamp-keyed event store),
        ``idx_*`` (sorted ``[dt_utc, seq, stamp]`` indexes), ``vars`` /
        ``var_desc_history`` (append-only variable histories with tombstones),
        and ``objects`` (zlib-compressed large payloads above ``object_threshold``).
        """
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
        self.idx_all  = []          # Master index (all [timestamp, seq, stamp] triples)
        self._index_seq = 0         # Insertion tie-breaker when dt_utc collides
        self._event_seq = 0         # Monotonic per-event causal counter persisted on event dicts
        self.revision = 0           # Monotonic session revision for compare-and-swap persistence
        
        # VARIABLE LAYER: Full history with timestamps
        # vars[key] = [[stamp1, value1], [stamp2, value2], ...]
        # Deleted variables have VAR_DELETED as value in their last entry
        self.vars = {}              # var_name → list of [stamp, value] pairs
        self.var_desc_history = {}  # var_name → list of [stamp, description] pairs
        self.var_meta_history = {}  # var_name → list of [stamp, metadata_dict] pairs
        
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
            'tool',
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

    def _add_to_index(self, index_list, timestamp, stamp):
        """
        Insert [timestamp, seq, stamp] maintaining sorted order by timestamp.

        When two events share the same dt_utc string (common in tight loops),
        seq preserves insertion order instead of falling back to stamp sorting.
        """
        self._index_seq += 1
        bisect.insort(index_list, [timestamp, self._index_seq, stamp])

    def _stamp_from_index_pair(self, pair):
        """Return the stamp from a 2- or 3-element index pair (legacy compat)."""
        return pair[-1]

    def _store_event(self, event_type, obj):
        """
        Store event in data layer and add to appropriate indexes.
        This is the single entry point for all event creation.

        Args:
            event_type: One of 'msg', 'ref', 'log', 'var', 'llm', or
                'emit'. LLM and emit events use only the master index.
            obj: The full event dict (must contain 'stamp' and 'dt_utc' keys)
        """
        stamp = obj["stamp"]
        timestamp = obj["dt_utc"]

        # Persist a monotonic causal sequence number inside the event dict so
        # unordered rehydration via from_events() preserves sub-millisecond
        # write order and variable deletion tombstones across sync/merge.
        self._event_seq += 1
        self.revision += 1
        obj.setdefault("_seq", self._event_seq)

        # Store in data layer
        self.events[stamp] = obj

        # Message, reflection, log, and variable events also use a
        # type-specific [timestamp, sequence, stamp] index. LLM and emit
        # events intentionally remain master-index-only.
        if event_type == "msg":
            self._add_to_index(self.idx_msgs, timestamp, stamp)
        elif event_type == "ref":
            self._add_to_index(self.idx_refs, timestamp, stamp)
        elif event_type == "log":
            self._add_to_index(self.idx_logs, timestamp, stamp)
        elif event_type == "var":
            self._add_to_index(self.idx_vars, timestamp, stamp)

        # Always add to master index
        self._add_to_index(self.idx_all, timestamp, stamp)

    def _get_events_from_index(self, index, limit=-1):
        """
        Get events from an index, optionally limited to last N.
        
        Args:
            index: One of the idx_* lists ([timestamp, stamp] or [timestamp, seq, stamp])
            limit: Max events to return (-1 = all)
            
        Returns:
            List of event dicts
        """
        pairs = index if limit <= 0 else index[-limit:]
        return [
            self.events[self._stamp_from_index_pair(ts_stamp)]
            for ts_stamp in pairs
            if self._stamp_from_index_pair(ts_stamp) in self.events
        ]

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

    def _get_latest_meta(self, key):
        """Return a copy of the latest structured metadata dict for ``key``, or None."""
        history = self.var_meta_history.get(key)
        if not history:
            return None
        return copy.deepcopy(history[-1][1])

    @staticmethod
    def _normalize_var_metadata(metadata=None, source=None):
        """Combine optional ``metadata`` dict and ``source`` provenance into one dict."""
        if metadata is not None and not isinstance(metadata, dict):
            raise ValueError("Variable metadata must be a dict or None")
        if metadata is None and source is None:
            return None
        combined = copy.deepcopy(metadata) if metadata is not None else {}
        if source is not None:
            combined['source'] = copy.deepcopy(source)
        return combined

    @staticmethod
    def _atomic_write_bytes(filename, raw_bytes):
        """Write ``raw_bytes`` atomically to ``filename`` via same-directory temp file + replace."""
        target = os.path.abspath(os.fspath(filename))
        parent = os.path.dirname(target)
        if parent:
            os.makedirs(parent, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(prefix=".memory_", suffix=".tmp", dir=parent or None)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(raw_bytes)
            os.replace(tmp_path, target)
        except Exception:
            if os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
            raise

    @staticmethod
    def _validate_emit_kind(kind):
        """
        Validate an emit event kind before any MEMORY mutation.

        Args:
            kind: Must be a non-whitespace string naming the lifecycle fact.

        Raises:
            ValueError: When kind is not a string or contains only whitespace.
        """
        if not isinstance(kind, str) or not kind.strip():
            raise ValueError(
                "emit kind must be a non-empty string, got {!r}".format(kind)
            )

    @staticmethod
    def _validate_emit_payload(payload):
        """
        Validate an emit payload before any MEMORY mutation.

        Payloads must be plain dicts whose contents survive JSON export.
        Callers remain responsible for redacting secrets and bounding size.

        Args:
            payload: Must be a dict serializable by json.dumps.

        Raises:
            ValueError: When payload is not a dict or is not JSON-safe.
        """
        if not isinstance(payload, dict):
            raise ValueError(
                "emit payload must be a dict, got {!r}".format(type(payload).__name__)
            )
        try:
            json.dumps(payload)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "emit payload must be JSON-serializable: {}".format(exc)
            ) from exc

    @staticmethod
    def _validate_emit_schema_version(schema_version):
        """
        Validate emit schema_version before any MEMORY mutation.

        Args:
            schema_version: Positive integer version for the kind's payload shape.

        Raises:
            ValueError: When schema_version is not a positive integer.
        """
        if not isinstance(schema_version, int) or isinstance(schema_version, bool):
            raise ValueError(
                "emit schema_version must be a positive integer, got {!r}".format(
                    schema_version
                )
            )
        if schema_version < 1:
            raise ValueError(
                "emit schema_version must be a positive integer, got {!r}".format(
                    schema_version
                )
            )

    @staticmethod
    def _normalize_stored_tool_calls(tool_calls):
        """Validate and deep-copy assistant tool_calls for storage in MEMORY."""
        if not isinstance(tool_calls, list):
            raise ValueError("tool_calls must be a list of dicts or None")
        normalized = []
        for idx, tc in enumerate(tool_calls):
            if not isinstance(tc, dict):
                raise ValueError("Each tool_call entry must be a dict")
            item = copy.deepcopy(tc)
            if not item.get("id"):
                item["id"] = "call_{}".format(idx)
            normalized.append(item)
        return normalized

    @staticmethod
    def _wire_tool_call(tc, idx=0):
        """Convert a stored tool_call dict into OpenAI wire format."""
        if "function" in tc and isinstance(tc["function"], dict):
            fn = dict(tc["function"])
            args = fn.get("arguments", "")
            if not isinstance(args, str):
                fn["arguments"] = json.dumps(args)
            return {
                "id": tc.get("id") or "call_{}".format(idx),
                "type": tc.get("type") or "function",
                "function": fn,
            }
        raw_args = tc.get("raw_arguments")
        if raw_args is not None and isinstance(raw_args, str):
            args_str = raw_args
        else:
            args_val = tc.get("arguments", {})
            args_str = args_val if isinstance(args_val, str) else json.dumps(args_val)
        return {
            "id": tc.get("id") or "call_{}".format(idx),
            "type": "function",
            "function": {
                "name": tc.get("name", ""),
                "arguments": args_str,
            },
        }

    def add_msg(
        self,
        role,
        content="",
        mode='text',
        channel='unknown',
        metadata=None,
        tool_calls=None,
        tool_call_id=None,
        name=None,
    ):
        """
        Add a message event with channel tracking and optional structured tool fields.

        Args:
            role: Message role (user, assistant, system, tool, etc.)
            content: Message content (defaults to ``""``; ``None`` coerced to ``""``)
            mode: Communication mode (text, audio, voice)
            channel: Communication channel (webapp, ios, telegram, etc.)
            metadata: Optional dict of extension metadata (e.g. {'internal': True}
                for UI-hidden RAG context). Omitted from the stored event when empty.
            tool_calls: Optional list of tool-call dicts on an ``assistant`` message
                (either ``LLM.chat()``'s ``{"id", "name", "arguments"}`` shape or
                OpenAI wire ``{"id", "type", "function": {...}}`` shape).
            tool_call_id: Optional string ID linking a ``tool`` role message to its
                preceding assistant tool call. Required when ``role == 'tool'``.
            name: Optional sender or tool name stored on the message event.
        """
        if role not in self.valid_roles:
            raise ValueError("Invalid role '{}'. Must be one of: {}".format(role, sorted(self.valid_roles)))
        if mode not in self.valid_modes:
            raise ValueError("Invalid mode '{}'. Must be one of: {}".format(mode, sorted(self.valid_modes)))
        if channel not in self.valid_channels:
            raise ValueError("Invalid channel '{}'. Must be one of: {}".format(channel, sorted(self.valid_channels)))
        if metadata is not None and not isinstance(metadata, dict):
            raise ValueError("metadata must be a dict or None")
        if tool_calls is not None and role != 'assistant':
            raise ValueError("tool_calls is only valid on 'assistant' messages, not '{}'".format(role))
        if role == 'tool':
            if not tool_call_id or not isinstance(tool_call_id, str):
                raise ValueError("role='tool' messages require a non-empty string tool_call_id")
        elif tool_call_id is not None and not isinstance(tool_call_id, str):
            raise ValueError("tool_call_id must be a string or None")

        if content is None:
            content = ""

        stored_tool_calls = (
            self._normalize_stored_tool_calls(tool_calls)
            if tool_calls is not None
            else None
        )

        stamp_seed = {'role': role, 'content': content}
        if stored_tool_calls is not None:
            stamp_seed['tool_calls'] = stored_tool_calls
        if tool_call_id is not None:
            stamp_seed['tool_call_id'] = tool_call_id

        stamp = event_stamp(stamp_seed)
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
        if stored_tool_calls is not None:
            msg['tool_calls'] = stored_tool_calls
        if tool_call_id is not None:
            msg['tool_call_id'] = tool_call_id
        if name is not None:
            msg['name'] = str(name)
        if metadata:
            msg['metadata'] = metadata
        self._store_event('msg', msg)

    def add_augment(
        self,
        content,
        target='last_user',
        role='system',
        mode='text',
        channel='unknown',
        metadata=None,
    ):
        """
        Add context that can augment a user turn for optional LLM view merging.

        Stores a normal message event tagged with ``metadata['augments']``.
        The event log is unchanged; only ``get_llm_msgs(merge_augments=True)``
        (or an AGENT with ``merge_augments=True``) folds this content into the
        most recent preceding user message when building the LLM payload.

        Args:
            content: Augmenting text (e.g. retrieved RAG chunks).
            target: Augmentation target. Only ``'last_user'`` is supported.
            role: Stored message role (default ``'system'``).
            mode: Communication mode (default ``'text'``).
            channel: Communication channel (default ``'unknown'``).
            metadata: Optional extra metadata (e.g. ``{'internal': True}``).
        """
        meta = dict(metadata or {})
        meta['augments'] = target
        self.add_msg(role, content, mode=mode, channel=channel, metadata=meta)

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

    def emit(self, kind, payload, schema_version=1):
        """
        Store a typed, machine-readable lifecycle event in the event log.

        Use ``emit`` for structured facts that harnesses, evaluators, and
        lifecycle helpers can query with ``get_emits``. This is the typed
        channel alongside human-oriented ``add_log`` prose and model
        ``add_exchange`` record/replay events.

        Each emit is a normal event with ``type='emit'``. Payloads are
        deep-copied on write so caller mutation cannot rewrite history.
        Callers must keep payloads JSON-safe, redact secrets, and bound size;
        MEMORY does not enforce a payload size cap.

        Args:
            kind: String containing non-whitespace characters that names the
                lifecycle fact (e.g.
                ``'plan_rejected'``, ``'run_started'``).
            payload: JSON-serializable dict of structured fields for this kind.
            schema_version: Positive integer version of the payload shape for
                this kind (default 1).

        Raises:
            ValueError: When kind, payload, or schema_version fail validation.
        """
        self._validate_emit_kind(kind)
        self._validate_emit_payload(payload)
        self._validate_emit_schema_version(schema_version)

        stored_payload = copy.deepcopy(payload)

        stamp_doc = {"kind": kind, "payload": stored_payload}
        stamp = event_stamp(stamp_doc)
        collision = 0
        while stamp in self.events:
            collision += 1
            collision_doc = copy.deepcopy(stamp_doc)
            collision_doc["collision"] = collision
            stamp = event_stamp(collision_doc)
        emit_event = {
            "stamp": stamp,
            "type": "emit",
            "kind": kind,
            "payload": stored_payload,
            "schema_version": schema_version,
            "dt_bog": str(dtt.datetime.now(tz_bog))[:23],
            "dt_utc": str(dtt.datetime.now(tz_utc))[:23],
        }
        self._store_event("emit", emit_event)

    def get_emits(self, kind=None, limit=-1):
        """
        Get typed emit events in chronological order.

        Reads from the master event index so ordering matches insertion order,
        including multiple emits in the same clock tick.

        Args:
            kind: When provided, keep only events with this kind string.
                Must contain non-whitespace characters when not None.
            limit: Max events to return (-1 = all). When positive, returns
                the most recent N events after kind filtering.

        Returns:
            Deep-copied list of emit event dicts. Mutating a returned payload
            cannot rewrite the stored event.

        Raises:
            ValueError: When kind is not a string or contains only whitespace.
        """
        if kind is not None:
            self._validate_emit_kind(kind)

        events = self.get_events(event_types=["emit"])

        if kind is not None:
            events = [event for event in events if event.get("kind") == kind]

        if limit > 0:
            events = events[-limit:]

        return copy.deepcopy(events)

    def add_exchange(
        self,
        kind,
        key,
        service,
        model,
        request,
        response,
        usage=None,
        default_params=None,
    ):
        """
        Record a model or tool exchange (LLM, EMBED, DM, or TOOL call) as a memory event.

        This is the seam that powers ThoughtFlow's record/replay system:
        because MEMORY is event-sourced, capturing the nondeterministic
        boundary (the model call) as an event makes the whole flow
        deterministically replayable. See LLM.record() / LLM.replay(),
        EMBED.record() / EMBED.replay(), and DM.record() / DM.replay().

        Args:
            kind: 'chat' for LLM exchanges, 'embed' for EMBED exchanges,
                'decide' for DM exchanges, 'tool' for TOOL exchanges.
            key: Deterministic content hash of the request (exchange_key).
            service: Provider name (e.g. 'openai').
            model: Model name.
            request: JSON-serializable dict describing the request.
            response: JSON-serializable response payload.
            usage: Optional normalized token/cost usage dict for the call.
            default_params: Optional constructor-level model params active
                when the exchange was recorded, enabling ReplayLLM to adopt
                them automatically on replay.
        """
        stamp = event_stamp({'key': key, 'kind': kind, 'response': response})
        exchange = {
            'stamp'    : stamp,
            'type'     : 'llm',
            'role'     : 'llm',
            'kind'     : kind,
            'key'      : key,
            'service'  : service,
            'model'    : model,
            'request'  : request,
            'response' : response,
            'dt_bog'   : str(dtt.datetime.now(tz_bog))[:23],
            'dt_utc'   : str(dtt.datetime.now(tz_utc))[:23],
        }
        if usage is not None:
            exchange['usage'] = copy.deepcopy(usage)
        if default_params is not None:
            exchange['default_params'] = copy.deepcopy(default_params)
        self._store_event('llm', exchange)

    def get_exchanges(self, kind=None):
        """
        Get recorded model exchanges in chronological order.

        Args:
            kind: Filter by exchange kind ('chat', 'embed', 'decide', or 'tool').
                None = all.

        Returns:
            List of exchange event dicts.
        """
        events = self.get_events(event_types=['llm'])
        if kind:
            events = [e for e in events if e.get('kind') == kind]
        return events

    @staticmethod
    def _metadata_matches(event, metadata_filter):
        """Return True when every key in metadata_filter matches the event metadata."""
        if not metadata_filter:
            return True
        meta = event.get('metadata') or {}
        return all(meta.get(key) == value for key, value in metadata_filter.items())

    def get_msgs(self, 
                 limit=-1, 
                 include=None, 
                 exclude=None, 
                 repr='list',
                 channel=None,
                 metadata_filter=None,
                 exclude_metadata=None,
                ):
        """
        Get messages with flexible filtering.
        
        Args:
            limit: Max messages to return (-1 = all)
            include: List of roles to include (None = all)
            exclude: List of roles to exclude (None = none)
            repr: Output format ('list', 'str', 'pprint1')
            channel: Filter by channel (None = all)
            metadata_filter: Keep only messages whose metadata matches all
                key-value pairs (e.g. {'internal': True})
            exclude_metadata: Drop messages whose metadata matches all
                key-value pairs (e.g. {'internal': True} for UI-visible history)
            
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
        if metadata_filter:
            events = [e for e in events if self._metadata_matches(e, metadata_filter)]
        if exclude_metadata:
            events = [e for e in events if not self._metadata_matches(e, exclude_metadata)]
        
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

    OPENAI_LLM_ROLES = ('system', 'user', 'assistant', 'tool')

    def _event_to_llm_msg(self, event, format='raw'):
        """Project one stored message event into an LLM message dict."""
        role = event.get('role', 'user')
        content = event.get('content', '')
        out = {'role': role, 'content': content}
        if event.get('tool_calls'):
            if format == 'openai':
                out['tool_calls'] = [
                    self._wire_tool_call(tc, idx=i)
                    for i, tc in enumerate(event['tool_calls'])
                ]
            else:
                out['tool_calls'] = copy.deepcopy(event['tool_calls'])
        if event.get('tool_call_id'):
            out['tool_call_id'] = event['tool_call_id']
        if event.get('name'):
            out['name'] = event['name']
        return out

    def get_llm_msgs(
        self,
        merge_augments=False,
        include=None,
        exclude=None,
        format='raw',
        channel=None,
        metadata_filter=None,
        exclude_metadata=None,
        budget_tokens=None,
        pinned=True,
        summarizer=None,
        token_counter=None,
    ):
        """
        Build LLM-ready message dicts from stored events.

        Default (``format='raw'``, ``merge_augments=False``): one dict per stored
        message preserving ``role``, ``content``, and any structured ``tool_calls``,
        ``tool_call_id``, or ``name`` fields.

        When ``format='openai'``, internal non-OpenAI roles (``reflection``,
        ``logger``, ``query``, ``action``, ``result``) are filtered out unless
        ``include`` was explicitly passed, and assistant ``tool_calls`` are
        emitted in OpenAI wire shape (``{"id", "type": "function", "function":
        {"name", "arguments": "<json>"}}``) ready to pass directly to ``LLM.chat()``.

        When ``merge_augments=True``, events tagged ``metadata['augments'] ==
        'last_user'`` are prepended into the most recent preceding user message
        for that turn and omitted as separate messages. Stored events are never
        modified.

        Args:
            merge_augments: Fold augmenting events into user messages for the
                LLM view only (default False).
            include: Optional list of roles to include (passed to ``get_msgs``).
            exclude: Optional list of roles to exclude (passed to ``get_msgs``).
            format: ``'raw'`` (default) or ``'openai'`` (provider-valid history).
            budget_tokens: Optional token budget for the returned view. Oldest
                unpinned messages are dropped first. Stored events are never
                modified. ``None`` (default) disables budgeting.
            pinned: When budgeting, always keep system messages and the most
                recent user message (default True).
            summarizer: Optional ``fn(dropped_msgs) -> str``. When messages are
                dropped for budget, its result is inserted as one system
                message so the model still sees a digest.
            token_counter: Optional ``fn(text) -> int``; defaults to a
                ``len(text) // 4`` estimate.

        Messages covered by a ``compact()`` summary are replaced in the view by
        that summary (the originals stay in the event log).

        Returns:
            list[dict]: Messages ready for ``LLM.call()`` or ``LLM.chat()``.
        """
        if format not in ('raw', 'openai'):
            raise ValueError("Invalid format '{}'. Choose 'raw' or 'openai'.".format(format))

        effective_include = include
        if format == 'openai' and effective_include is None:
            effective_include = list(self.OPENAI_LLM_ROLES)

        events = self.get_msgs(
            include=effective_include,
            exclude=exclude,
            channel=channel,
            metadata_filter=metadata_filter,
            exclude_metadata=exclude_metadata,
        )
        return self._build_llm_view(
            events,
            merge_augments=merge_augments,
            format=format,
            budget_tokens=budget_tokens,
            pinned=pinned,
            summarizer=summarizer,
            token_counter=token_counter,
        )

    @staticmethod
    def _estimate_tokens(text):
        """Cheap, dependency-free token estimate (about 4 characters per token)."""
        return max(1, len(str(text or '')) // 4)

    def _build_llm_view(
        self,
        events,
        merge_augments=False,
        format='raw',
        budget_tokens=None,
        pinned=True,
        summarizer=None,
        token_counter=None,
    ):
        """Apply compaction summaries, folding, and optional token budgeting."""
        covered = set()
        for event in events:
            meta = event.get('metadata') or {}
            if meta.get('summary'):
                covered.update(meta.get('summary_of') or [])
        if covered:
            summaries = [e for e in events if (e.get('metadata') or {}).get('summary')]
            rest = [
                e for e in events
                if not (e.get('metadata') or {}).get('summary')
                and e.get('stamp') not in covered
            ]
            events = summaries + rest

        msgs = self._fold_llm_events(events, merge_augments=merge_augments, format=format)
        if budget_tokens is None:
            return msgs

        count = token_counter or self._estimate_tokens

        def cost(msg):
            total = count(msg.get('content', ''))
            if msg.get('tool_calls'):
                total += count(json.dumps(msg['tool_calls'], default=str))
            return total

        keep = set()
        if pinned:
            for i, msg in enumerate(msgs):
                if msg.get('role') == 'system':
                    keep.add(i)
            for i in range(len(msgs) - 1, -1, -1):
                if msgs[i].get('role') == 'user':
                    keep.add(i)
                    break
        used = sum(cost(msgs[i]) for i in keep)
        for i in range(len(msgs) - 1, -1, -1):
            if i in keep:
                continue
            c = cost(msgs[i])
            if used + c > budget_tokens:
                break
            keep.add(i)
            used += c

        # Keep tool turns paired: drop an assistant tool_calls message when any of
        # its results exists but was dropped, then drop results left without a caller.
        result_idx = {}
        for i, msg in enumerate(msgs):
            if msg.get('role') == 'tool':
                result_idx[msg.get('tool_call_id')] = i
        for i in sorted(keep):
            ids = [tc.get('id') for tc in msgs[i].get('tool_calls') or []]
            if any(cid in result_idx and result_idx[cid] not in keep for cid in ids):
                keep.discard(i)
        live_ids = set()
        for i in sorted(keep):
            for tc in msgs[i].get('tool_calls') or []:
                live_ids.add(tc.get('id'))
        for i in sorted(keep):
            if msgs[i].get('role') == 'tool' and msgs[i].get('tool_call_id') not in live_ids:
                keep.discard(i)

        out = [msgs[i] for i in sorted(keep)]
        dropped = [msgs[i] for i in range(len(msgs)) if i not in keep]
        if dropped and summarizer is not None:
            digest = {'role': 'system', 'content': str(summarizer(dropped))}
            lead = 0
            while lead < len(out) and out[lead].get('role') == 'system':
                lead += 1
            out.insert(lead, digest)
        return out

    def compact(self, keep=6, summarizer=None, channel='unknown'):
        """
        Summarize older conversation turns without deleting them.

        Adds one ``system`` message tagged ``metadata={'summary': True,
        'internal': True, 'summary_of': [stamps]}`` covering every user,
        assistant, and tool message except the most recent ``keep``. Original
        events stay in the log; ``get_llm_msgs`` shows the summary instead of
        the covered messages. Already-summarized messages are not re-covered.

        Args:
            keep: Number of most recent conversational messages left untouched.
            summarizer: Optional ``fn(msgs) -> str`` over the event dicts being
                covered. Default: one truncated ``role: content`` line each.
            channel: Channel for the summary message.

        Returns:
            dict or None: ``{'stamp', 'covered'}`` for the new summary, or
            ``None`` when there was nothing to compact.
        """
        events = self.get_msgs(include=['user', 'assistant', 'tool'])
        covered = set()
        for event in self.get_msgs(include=['system']):
            meta = event.get('metadata') or {}
            if meta.get('summary'):
                covered.update(meta.get('summary_of') or [])
        live = [e for e in events if e.get('stamp') not in covered]
        cut = max(0, len(live) - keep) if keep > 0 else len(live)
        # Never split an assistant tool_calls message from its tool results.
        while 0 < cut < len(live) and live[cut].get('role') == 'tool':
            cut -= 1
        older = live[:cut]
        if not older:
            return None
        if summarizer is not None:
            text = str(summarizer(older))
        else:
            text = 'Summary of earlier conversation:\n' + '\n'.join(
                '{}: {}'.format(e.get('role'), str(e.get('content', ''))[:80])
                for e in older
            )
        stamps = [e['stamp'] for e in older]
        self.add_msg(
            'system',
            text,
            channel=channel,
            metadata={'summary': True, 'internal': True, 'summary_of': stamps},
        )
        self.emit('memory_compacted', {'covered': len(stamps), 'kept': keep})
        base = getattr(self, 'base', self)
        return {'stamp': base.get_msgs(include=['system'])[-1]['stamp'], 'covered': len(stamps)}

    def suspend(self, reason, pending=None, resume_at=None, suspension_id=None):
        """
        Mark this run as suspended, waiting for an external decision.

        Stores a ``_suspension`` variable (JSON-safe, survives ``to_dict`` /
        ``from_dict``) and emits ``run_suspended``. A later
        ``resolve_suspension`` resumes it exactly once.

        Args:
            reason: Short string such as ``'approval_required'``.
            pending: JSON-safe dict describing what is waiting (tool calls, step).
            resume_at: Optional timestamp or label for scheduled resumes.
            suspension_id: Optional stable id; defaults to a stamp of the contents.

        Returns:
            dict: The stored suspension record.
        """
        record = {
            'id': suspension_id or event_stamp({'reason': reason, 'pending': pending, 'n': len(self.get_events())}),
            'reason': reason,
            'pending': copy.deepcopy(pending) if pending is not None else {},
            'resume_at': resume_at,
            'status': 'suspended',
            'decision': None,
        }
        self.set_var('_suspension', record, desc='Suspended-run marker')
        self.emit('run_suspended', {'id': record['id'], 'reason': reason})
        return copy.deepcopy(record)

    def get_suspension(self):
        """Return the current suspension record, or None if never suspended."""
        record = self.get_var('_suspension')
        return copy.deepcopy(record) if record else None

    def is_suspended(self):
        """True while a suspension is recorded and not yet resolved."""
        record = self.get_suspension()
        return bool(record) and record.get('status') == 'suspended'

    def resolve_suspension(self, decision=None):
        """
        Resolve the current suspension. Safe to call more than once.

        Returns:
            dict: ``{'status': 'resolved', 'suspension': record}`` the first
            time, ``{'status': 'already_resolved', ...}`` on repeats (the stored
            decision is not overwritten), or ``{'status': 'not_suspended'}``.
        """
        record = self.get_suspension()
        if record is None:
            return {'status': 'not_suspended', 'suspension': None}
        if record.get('status') != 'suspended':
            return {'status': 'already_resolved', 'suspension': record}
        record['status'] = 'resolved'
        record['decision'] = copy.deepcopy(decision)
        self.set_var('_suspension', record, desc='Suspended-run marker')
        self.emit('run_resumed', {'id': record['id']})
        return {'status': 'resolved', 'suspension': copy.deepcopy(record)}

    def _fold_llm_events(self, events, merge_augments=False, format='raw'):
        """Project filtered message events into LLM dicts with optional augment folding."""
        if not merge_augments:
            return [self._event_to_llm_msg(event, format=format) for event in events]

        result = []
        for event in events:
            meta = event.get('metadata') or {}
            if meta.get('augments') == 'last_user':
                augment_content = event.get('content', '')
                for i in range(len(result) - 1, -1, -1):
                    if result[i].get('role') == 'user':
                        merged = augment_content + '\n\n' + result[i]['content']
                        updated = dict(result[i])
                        updated['content'] = merged
                        result[i] = updated
                        break
                continue

            result.append(self._event_to_llm_msg(event, format=format))

        return result

    def get_events(self, limit=-1, event_types=None, channel=None, since=None):
        """
        Get all events, optionally filtered by causal ``since`` stamp, type, and channel.

        Args:
            limit: Max events (-1 = all)
            event_types: List like ['msg', 'log', 'ref', 'var', 'llm', 'emit']
                (None = all)
            channel: Filter by channel (None = all)
            since: Optional event stamp; when provided, returns only events
                recorded strictly after ``since`` in the master index.

        Returns:
            List of event dicts

        Raises:
            KeyError: When ``since`` is provided and does not exist in this memory.
        """
        pairs = self.idx_all
        if since is not None:
            found_idx = None
            for idx, pair in enumerate(pairs):
                if self._stamp_from_index_pair(pair) == since:
                    found_idx = idx
                    break
            if found_idx is None:
                raise KeyError("Event stamp {!r} not found in memory.".format(since))
            pairs = pairs[found_idx + 1:]

        events = [
            self.events[self._stamp_from_index_pair(pair)]
            for pair in pairs
            if self._stamp_from_index_pair(pair) in self.events
        ]

        if event_types:
            events = [e for e in events if e.get("type") in event_types]
        if channel:
            events = [e for e in events if e.get("channel") == channel]

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

    def last_user_msg(self, content_only=False):
        """
        Get the last user message.
        
        Args:
            content_only: If True, return just the content string. 
                          If False (default), return the full event dict.
        
        Returns:
            dict or str: Full event dict, or content string if content_only=True.
                         Returns None (or '' if content_only) if no messages.
        """
        msgs = self.get_msgs(include=['user'])
        if not msgs:
            return '' if content_only else None
        return msgs[-1]['content'] if content_only else msgs[-1]

    def last_asst_msg(self, content_only=False):
        """
        Get the last assistant message.
        
        Args:
            content_only: If True, return just the content string. 
                          If False (default), return the full event dict.
        
        Returns:
            dict or str: Full event dict, or content string if content_only=True.
                         Returns None (or '' if content_only) if no messages.
        """
        msgs = self.get_msgs(include=['assistant'])
        if not msgs:
            return '' if content_only else None
        return msgs[-1]['content'] if content_only else msgs[-1]

    def last_sys_msg(self, content_only=False):
        """
        Get the last system message.
        
        Args:
            content_only: If True, return just the content string. 
                          If False (default), return the full event dict.
        
        Returns:
            dict or str: Full event dict, or content string if content_only=True.
                         Returns None (or '' if content_only) if no messages.
        """
        msgs = self.get_msgs(include=['system'])
        if not msgs:
            return '' if content_only else None
        return msgs[-1]['content'] if content_only else msgs[-1]

    def last_log_msg(self, content_only=False):
        """
        Get the last log message.
        
        Args:
            content_only: If True, return just the content string. 
                          If False (default), return the full event dict.
        
        Returns:
            dict or str: Full event dict, or content string if content_only=True.
                         Returns None (or '' if content_only) if no logs.
        """
        logs = self.get_logs()
        if not logs:
            return '' if content_only else None
        return logs[-1]['content'] if content_only else logs[-1]

    def last_result_msg(self, content_only=False):
        """
        Get the last result message.

        Args:
            content_only: If True, return just the content string.
                          If False (default), return the full event dict.

        Returns:
            dict or str: Full event dict, or content string if content_only=True.
                         Returns None (or '' if content_only) if no result messages.
        """
        msgs = self.get_msgs(include=['result'])
        if not msgs:
            return '' if content_only else None
        return msgs[-1]['content'] if content_only else msgs[-1]

    def last_ref(self, content_only=False):
        """
        Get the last reflection.
        
        Args:
            content_only: If True, return just the content string. 
                          If False (default), return the full event dict.
        
        Returns:
            dict or str: Full event dict, or content string if content_only=True.
                         Returns None (or '' if content_only) if no reflections.
        """
        refs = self.get_refs()
        if not refs:
            return '' if content_only else None
        return refs[-1]['content'] if content_only else refs[-1]

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
                out_msg = {'role': role, 'content': content}
                if msg.get('tool_calls'):
                    out_msg['tool_calls'] = [
                        self._wire_tool_call(tc, idx=j)
                        for j, tc in enumerate(msg['tool_calls'])
                    ]
                if msg.get('tool_call_id'):
                    out_msg['tool_call_id'] = msg['tool_call_id']
                if msg.get('name'):
                    out_msg['name'] = msg['name']
                result.append(out_msg)
            else:
                # List format includes more metadata
                result.append({
                    'role': role,
                    'content': content,
                    'stamp': stamp,
                    'truncated': i < cutoff_idx and len(msg.get('content', '')) > truncate_threshold,
                })
        
        return result

    def set_var(self, key, value, desc='', metadata=None, source=None):
        """
        Store a variable by appending to its history list.
        Variable changes are first-class events in the event stream.
        Each variable maintains a full history of [stamp, value] pairs.
        
        Large values (exceeding object_threshold) are automatically converted
        to compressed objects, with an object reference stored in the history.
        
        Descriptions and structured metadata (provenance, confidence, turn)
        are tracked in dedicated histories paired by stamp.
        
        Args:
            key: Variable name
            value: Variable value (any type)
            desc: Optional description (appended to description history if provided)
            metadata: Optional JSON-serializable dict of structured provenance
            source: Optional shorthand provenance stored under ``metadata['source']``
        """
        meta_dict = self._normalize_var_metadata(metadata=metadata, source=source)

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

        if meta_dict is not None:
            if key not in self.var_meta_history:
                self.var_meta_history[key] = []
            self.var_meta_history[key].append([stamp, meta_dict])
        
        # Get latest description and metadata from history
        current_desc = desc if desc else self._get_latest_desc(key)
        current_meta = meta_dict if meta_dict is not None else self._get_latest_meta(key)
        
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
        if current_meta is not None:
            var_event['var_meta'] = current_meta
        self._store_event('var', var_event)

    def upsert(self, key, value, desc='', metadata=None, source=None):
        """
        Set ``key`` only when ``value`` (or provided ``desc`` / ``metadata``) actually changed.

        Avoids bloating variable history and the event log when consolidators
        or trackers repeatedly affirm the same value across turns.

        Args:
            key (str): Variable name.
            value: Desired variable value.
            desc (str, optional): Variable description.
            metadata (dict, optional): Structured metadata dict.
            source (Any, optional): Provenance stored under ``metadata['source']``.

        Returns:
            bool: ``True`` if a new entry was written; ``False`` if unchanged (no-op).

        Example:
            >>> memory.upsert("budget", 15000, source={"turn": 4})
            True
            >>> memory.upsert("budget", 15000, source={"turn": 4})
            False
        """
        meta_dict = self._normalize_var_metadata(metadata=metadata, source=source)
        history = self.vars.get(key)
        if history and history[-1][1] is not VAR_DELETED:
            current_val = self.get_var(key, resolve_refs=True)
            same_val = (type(current_val) is type(value)) and (current_val == value)
            same_desc = (not desc) or (desc == self._get_latest_desc(key))
            same_meta = (meta_dict is None) or (meta_dict == self._get_latest_meta(key))
            if same_val and same_desc and same_meta:
                return False

        self.set_var(key, value, desc=desc, metadata=metadata, source=source)
        return True

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

    def get_var_meta(self, key):
        """
        Return a copy of the latest structured metadata dict for ``key``, or None.

        Args:
            key (str): Variable name.

        Returns:
            dict or None: Latest metadata dict when present and variable is active.
        """
        history = self.vars.get(key)
        if not history or history[-1][1] is VAR_DELETED:
            return None
        return self._get_latest_meta(key)

    def get_var_meta_history(self, key):
        """Return full ``[[stamp, metadata_dict], ...]`` history for ``key``."""
        return copy.deepcopy(self.var_meta_history.get(key, []))

    def find_vars(
        self,
        prefix=None,
        desc_contains=None,
        changed_since=None,
        metadata_filter=None,
        include_meta=False,
        resolve_refs=True,
    ):
        """
        Query active variables by prefix, description text, causal stamp, or metadata.

        Args:
            prefix (str, optional): Keep variables whose name starts with ``prefix``.
            desc_contains (str, optional): Case-insensitive substring match on description.
            changed_since (str, optional): Event stamp; keep variables modified strictly
                after ``changed_since`` in ``idx_all``.
            metadata_filter (dict, optional): Key-value filter matched against latest
                variable metadata (and nested ``metadata['source']`` when a dict).
            include_meta (bool): When True, return ``{key: {'value', 'stamp', 'desc', 'metadata'}}``
                instead of ``{key: value}``. Defaults to False.
            resolve_refs (bool): Resolve compressed ``_obj_ref`` values (default True).

        Returns:
            dict: Matching active variables.

        Raises:
            KeyError: When ``changed_since`` is provided and not found in ``idx_all``.
        """
        stamps_after = None
        if changed_since is not None:
            after_events = self.get_events(since=changed_since)
            stamps_after = {ev.get("stamp") for ev in after_events}

        desc_needle = desc_contains.lower() if isinstance(desc_contains, str) else None
        matches = {}

        for key, history in self.vars.items():
            if not history:
                continue
            last_stamp, last_raw = history[-1]
            if last_raw is VAR_DELETED:
                continue
            if prefix is not None and not key.startswith(prefix):
                continue
            desc = self._get_latest_desc(key)
            if desc_needle is not None and desc_needle not in (desc or "").lower():
                continue
            if stamps_after is not None:
                if not any(entry_stamp in stamps_after for entry_stamp, _ in history):
                    continue
            meta = self._get_latest_meta(key)
            if metadata_filter:
                meta_map = meta or {}
                src_map = meta_map.get("source") if isinstance(meta_map.get("source"), dict) else {}
                matched_all = True
                for mk, mv in metadata_filter.items():
                    if mk in meta_map and meta_map[mk] == mv:
                        continue
                    if mk in src_map and src_map[mk] == mv:
                        continue
                    matched_all = False
                    break
                if not matched_all:
                    continue

            if resolve_refs and is_obj_ref(last_raw):
                val = self.get_obj(last_raw["_obj_ref"])
            else:
                val = last_raw

            if include_meta:
                matches[key] = {
                    "value": val,
                    "stamp": last_stamp,
                    "desc": desc,
                    "metadata": meta,
                }
            else:
                matches[key] = val

        return matches

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

    def snapshot(self):
        """
        Export memory state as dict.
        Stores events and objects - indexes can be rehydrated from events.
        
        Returns:
            dict with 'id', 'revision', 'events', 'objects', and 'var_meta_history' keys
        """
        return {
            'id': self.id,
            'revision': self.revision,
            'events': dict(self.events),    # All events by stamp
            'objects': dict(self.objects),  # All objects by stamp (already JSON-serializable)
            'var_meta_history': copy.deepcopy(self.var_meta_history),
        }

    def save(self, filename, compressed=False, slim=False, indent=2):
        """
        Atomically save memory to disk (JSON for ``.json`` paths, pickle otherwise).

        Uses a same-directory temporary file plus ``os.replace`` so crashes or
        process kills never leave half-written session files behind.

        Args:
            filename: Path to save file (``.json`` writes portable JSON; any
                other extension writes binary pickle compatible with ``load``).
            compressed: If True, use gzip compression on binary pickle output.
            slim: Passed to ``to_json(slim=...)`` when saving a ``.json`` file.
            indent: JSON indentation when saving a ``.json`` file (default 2).
        """
        import gzip
        path_str = os.fspath(filename)
        if not compressed and str(path_str).lower().endswith('.json'):
            self.to_json(filename=path_str, indent=indent, slim=slim)
            return
        data = self.snapshot()
        raw_pickle = pickle.dumps(data)
        if compressed:
            raw_bytes = gzip.compress(raw_pickle)
        else:
            raw_bytes = raw_pickle
        self._atomic_write_bytes(path_str, raw_bytes)

    def load(self, filename, compressed=False):
        """
        Load memory from file (supports both ``.json`` snapshots and binary pickle).

        Args:
            filename: Path to load file
            compressed: If True, expect gzip compression on binary pickle
        """
        import gzip
        path_str = os.fspath(filename)
        if not compressed and str(path_str).lower().endswith('.json'):
            mem = MEMORY.from_json(path_str)
            self._adopt_loaded_memory(mem)
            return

        if compressed:
            with gzip.open(path_str, 'rb') as f:
                data = pickle.load(f)
        else:
            with open(path_str, 'rb') as f:
                data = pickle.load(f)

        # Rehydrate from events (pass objects if present)
        event_list = list(data.get('events', {}).values())
        objects = data.get('objects', {})
        mem = MEMORY.from_events(event_list, data.get('id'), objects=objects)
        if 'var_meta_history' in data and isinstance(data['var_meta_history'], dict):
            mem.var_meta_history = copy.deepcopy(data['var_meta_history'])
        if 'revision' in data and isinstance(data['revision'], int):
            mem.revision = data['revision']
        self._adopt_loaded_memory(mem)

    def _adopt_loaded_memory(self, mem):
        """Copy internal layers from a rehydrated MEMORY ``mem`` onto ``self``."""
        self.id = mem.id
        self.revision = mem.revision
        self.events = mem.events
        self.idx_msgs = mem.idx_msgs
        self.idx_refs = mem.idx_refs
        self.idx_logs = mem.idx_logs
        self.idx_vars = mem.idx_vars
        self.idx_all = mem.idx_all
        self._index_seq = mem._index_seq
        self._event_seq = mem._event_seq
        self.vars = mem.vars
        self.var_desc_history = mem.var_desc_history
        self.var_meta_history = mem.var_meta_history
        self.objects = mem.objects
        self.valid_channels = set(mem.valid_channels)

    def scope(
        self,
        actor,
        read_rooms=None,
        write_room=None,
        public_keys=(),
        export_keys=(),
    ):
        """
        Return a zero-copy scoped perspective over this MEMORY.

        A scope lets multiple actors, parallel branches, or debate rooms share
        a single event-sourced MEMORY without copying events, leaking private
        room messages into another actor's prompt, colliding on scratchpad
        variables such as ``{name}_result``, or decompressing unrelated large
        objects stored on the parent memory.

        Args:
            actor (str): Non-empty identifier for this actor/branch. Scoped
                variable writes land under ``{actor}__{key}`` unless the key is
                listed in ``export_keys``.
            read_rooms (iterable[str], optional): Room or channel names this
                scope may read. When provided, ``get_msgs``, ``get_llm_msgs``,
                ``last_user_msg``, and ``last_asst_msg`` see only messages
                whose ``metadata['room']`` or ``channel`` is in ``read_rooms``.
                When ``None``, all messages on the parent memory are visible.
            write_room (str, optional): Room/channel name applied to messages
                added through this scope. Automatically registered in
                ``self.valid_channels`` so domain rooms (e.g. ``'public_room'``,
                ``'alpha_board'``) work alongside built-in channels.
            public_keys (iterable[str], optional): Shared parent variable names
                readable (read-only unless also in ``export_keys``) through
                this scope.
            export_keys (iterable[str], optional): Shared parent variable names
                that are both readable and writable directly on the parent
                memory without actor prefixing.

        Returns:
            _MemoryScope: A MEMORY-compatible view backed directly by ``self``.
        """
        return _MemoryScope(
            base=self,
            actor=actor,
            read_rooms=read_rooms,
            write_room=write_room,
            public_keys=public_keys,
            export_keys=export_keys,
        )

    def copy(self):
        """Return a deep copy of the MEMORY instance."""
        return copy.deepcopy(self)

    def to_json(self, filename=None, indent=2, slim=False, keep_recent_turns=None):
        """
        Export memory to JSON format (optionally slimmed for serverless transport).
        
        Like DataFrame.to_csv(), this allows saving memory state to a portable
        JSON format that can be loaded later with from_json(). When ``filename``
        is provided, writes atomically via a same-directory temporary file plus
        ``os.replace``.
        
        Args:
            filename: If provided, write atomically to file. Otherwise return JSON string.
            indent: JSON indentation level (default 2, use None for compact).
            slim: When True, strips bookkeeping ``log`` and ``ref`` events (or drops
                those older than ``keep_recent_turns`` user turns), trims variable
                history to the latest entry per variable, and garbage-collects
                unreferenced compressed objects.
            keep_recent_turns: Optional non-negative integer; when provided (with or
                without ``slim=True``), retains ``log`` and ``ref`` events at or after
                the N-th most recent ``user`` message and drops older bookkeeping.
        
        Returns:
            JSON string if filename is None, else None
        
        Example:
            # Save to file atomically
            memory.to_json('memory_backup.json')
            
            # Export lean payload for serverless session store
            slim_json = memory.to_json(slim=True, indent=None)
        """
        def serialize_var_history(var_dict, latest_only=False):
            """Convert VAR_DELETED sentinel to JSON-safe marker."""
            result = {}
            for key, history in var_dict.items():
                entries = history[-1:] if (latest_only and history) else history
                serialized_history = []
                for stamp, value in entries:
                    if value is VAR_DELETED:
                        serialized_history.append([stamp, '__VAR_DELETED__'])
                    else:
                        serialized_history.append([stamp, value])
                result[key] = serialized_history
            return result

        use_slim = bool(slim) or (keep_recent_turns is not None)
        if not use_slim:
            events_out = self.events
            objects_out = self.objects
            vars_out = serialize_var_history(self.vars, latest_only=False)
            desc_out = self.var_desc_history
            meta_out = self.var_meta_history
            idx_msgs_out = self.idx_msgs
            idx_refs_out = self.idx_refs
            idx_logs_out = self.idx_logs
            idx_vars_out = self.idx_vars
            idx_all_out = self.idx_all
        else:
            # Determine cutoff position in idx_all for log/ref retention
            cutoff_idx = len(self.idx_all)
            if keep_recent_turns is not None:
                turns = int(keep_recent_turns)
                if turns > 0:
                    user_stamps = [
                        self._stamp_from_index_pair(p)
                        for p in self.idx_msgs
                        if (self.events.get(self._stamp_from_index_pair(p)) or {}).get('role') == 'user'
                    ]
                    if user_stamps:
                        anchor_stamp = user_stamps[-min(turns, len(user_stamps))]
                        for pos, pair in enumerate(self.idx_all):
                            if self._stamp_from_index_pair(pair) == anchor_stamp:
                                cutoff_idx = pos
                                break

            latest_var_stamps = {
                history[-1][0]
                for history in self.vars.values()
                if history
            }
            retained_stamps = set()
            for pos, pair in enumerate(self.idx_all):
                st = self._stamp_from_index_pair(pair)
                ev = self.events.get(st)
                if ev is None:
                    continue
                etype = ev.get('type', 'msg')
                if etype in ('log', 'ref'):
                    if pos >= cutoff_idx:
                        retained_stamps.add(st)
                elif etype == 'var':
                    if st in latest_var_stamps:
                        retained_stamps.add(st)
                else:
                    retained_stamps.add(st)

            events_out = {st: self.events[st] for st in retained_stamps if st in self.events}
            vars_out = serialize_var_history(self.vars, latest_only=True)
            desc_out = {
                k: hist[-1:] for k, hist in self.var_desc_history.items() if hist
            }
            meta_out = {
                k: hist[-1:] for k, hist in self.var_meta_history.items() if hist
            }
            idx_msgs_out = [p for p in self.idx_msgs if self._stamp_from_index_pair(p) in retained_stamps]
            idx_refs_out = [p for p in self.idx_refs if self._stamp_from_index_pair(p) in retained_stamps]
            idx_logs_out = [p for p in self.idx_logs if self._stamp_from_index_pair(p) in retained_stamps]
            idx_vars_out = [p for p in self.idx_vars if self._stamp_from_index_pair(p) in retained_stamps]
            idx_all_out = [p for p in self.idx_all if self._stamp_from_index_pair(p) in retained_stamps]

            # Garbage-collect unreferenced compressed objects
            referenced_objs = set()
            for history in self.vars.values():
                if history:
                    val = history[-1][1]
                    if is_obj_ref(val):
                        referenced_objs.add(val['_obj_ref'])
            for ev in events_out.values():
                vval = ev.get('var_value')
                if is_obj_ref(vval):
                    referenced_objs.add(vval['_obj_ref'])
            objects_out = {
                ost: obj for ost, obj in self.objects.items() if ost in referenced_objs
            }

        data = {
            'version': '1.0',
            'revision': self.revision,
            'id': self.id,
            'events': events_out,
            'objects': objects_out,
            'vars': vars_out,
            'var_desc_history': desc_out,
            'var_meta_history': meta_out,
            'idx_msgs': idx_msgs_out,
            'idx_refs': idx_refs_out,
            'idx_logs': idx_logs_out,
            'idx_vars': idx_vars_out,
            'idx_all': idx_all_out,
        }
        
        json_str = json.dumps(data, indent=indent, ensure_ascii=False)
        
        if filename:
            self._atomic_write_bytes(filename, json_str.encode('utf-8'))
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
        source_path = os.fspath(source) if isinstance(source, os.PathLike) else source
        if isinstance(source_path, str) and os.path.isfile(source_path):
            with open(source_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = json.loads(source_path)
        
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
        mem.var_meta_history = data.get('var_meta_history', {})
        mem.idx_msgs = data.get('idx_msgs', [])
        mem.idx_refs = data.get('idx_refs', [])
        mem.idx_logs = data.get('idx_logs', [])
        mem.idx_vars = data.get('idx_vars', [])
        mem.idx_all = data.get('idx_all', [])
        mem._index_seq = len(mem.idx_all)
        seq_values = [
            ev.get('_seq', 0)
            for ev in mem.events.values()
            if isinstance(ev.get('_seq'), int)
        ]
        mem._event_seq = max(seq_values) if seq_values else len(mem.events)
        if isinstance(data.get('revision'), int):
            mem.revision = data['revision']
        else:
            mem.revision = len(mem.idx_all)
        for ev in mem.events.values():
            ch = ev.get('channel')
            if isinstance(ch, str) and ch:
                mem.valid_channels.add(ch)

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
        
        # Sort events chronologically by dt_utc, breaking sub-millisecond ties
        # via the persisted _seq counter and event stamp (so merging forked
        # branches that share post-fork _seq numbers is order-independent),
        # while falling back to input order only for legacy events without _seq.
        indexed_events = list(enumerate(event_list))
        indexed_events.sort(
            key=lambda pair: (
                pair[1].get('dt_utc', ''),
                0 if isinstance(pair[1].get('_seq'), int) else 1,
                pair[1]['_seq'] if isinstance(pair[1].get('_seq'), int) else pair[0],
                pair[1].get('stamp', ''),
            )
        )
        sorted_events = [pair[1] for pair in indexed_events]
        max_seq = 0
        seen_stamps = set()
        
        for ev in sorted_events:
            stamp = ev.get('stamp')
            timestamp = ev.get('dt_utc', '')
            if not stamp or stamp in seen_stamps:
                continue
            seen_stamps.add(stamp)
            if isinstance(ev.get('_seq'), int) and ev['_seq'] > max_seq:
                max_seq = ev['_seq']
            
            event_type = ev.get('type', 'msg')
            
            # Store in data layer
            mem.events[stamp] = ev
            
            # Create index pair; seq is assigned on load for stable ordering
            seq = len(mem.idx_all) + 1
            ts_pair = [timestamp, seq, stamp]
            
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

                    var_meta = ev.get('var_meta')
                    if isinstance(var_meta, dict):
                        if var_name not in mem.var_meta_history:
                            mem.var_meta_history[var_name] = []
                        meta_hist = mem.var_meta_history[var_name]
                        if not meta_hist or meta_hist[-1][1] != var_meta:
                            meta_hist.append([stamp, copy.deepcopy(var_meta)])

            ch = ev.get('channel')
            if isinstance(ch, str) and ch:
                mem.valid_channels.add(ch)
            
            mem.idx_all.append(ts_pair)

        mem._index_seq = len(mem.idx_all)
        mem._event_seq = max(max_seq, len(mem.events))
        mem.revision = len(mem.idx_all)
        return mem

    def merge(self, other):
        """
        Union this MEMORY with ``other`` by event stamp, returning a new merged MEMORY.

        Designed for serverless compare-and-swap conflict resolution: when two
        concurrent invocations rehydrate the same base session (`revision` K),
        append non-conflicting turns/events, and collide on write, calling
        ``base_a.merge(base_b)`` deterministically unions their events,
        compressed objects, and variable histories in causal order and advances
        ``revision`` if ``other`` contributed unseen stamps.

        Args:
            other (MEMORY or _MemoryScope): Concurrent memory branch to union.

        Returns:
            MEMORY: New merged MEMORY instance preserving ``self.id``.

        Example:
            >>> merged = session_a.merge(session_b)
        """
        other_root = getattr(other, 'base', other)
        if not isinstance(other_root, MEMORY):
            raise TypeError(
                "merge() expects a MEMORY instance, got {}.".format(type(other).__name__)
            )

        added_new = any(st not in self.events for st in other_root.events)
        combined_events = list(self.events.values()) + [
            ev for st, ev in other_root.events.items() if st not in self.events
        ]
        combined_objects = dict(other_root.objects)
        combined_objects.update(self.objects)

        merged = MEMORY.from_events(
            combined_events,
            memory_id=self.id,
            objects=combined_objects,
        )
        merged.valid_channels = set(self.valid_channels) | set(other_root.valid_channels)
        base_rev = max(int(self.revision), int(other_root.revision))
        merged.revision = base_rev + (1 if added_new else 0)
        return merged

    def render(
        self,
        include=('msgs',),           # Tuple/list of event types to include: 'msgs', 'logs', 'refs', 'vars', 'events'
        format='plain',       # 'plain', 'markdown', 'json', 'table', 'conversation'
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
        - LLM-optimized conversation export (via format='conversation'), 
          which produces a clean text blob of user/assistant messages with 
          configurable length and formatting options.

        Args:
            include: Which event types to include ('msgs', 'logs', 'refs', 'vars', 'events')
            format: 'plain', 'markdown', 'json', 'table', or 'conversation'
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
            print(mem.render(role_filter=['user'], format='markdown'))

            # Render as a table, including logs and refs
            print(mem.render(include=('msgs', 'logs', 'refs'), format='table'))

            # Render with a content keyword filter and max length
            print(mem.render(content_filter='hello', max_length=50))

            # Export as LLM-optimized conversation
            print(mem.render(format='conversation', max_total_length=2000))
            
            # Filter by channel
            print(mem.render(channel_filter='telegram'))
        """
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
                            # Unparseable timestamp: keep the event rather
                            # than silently dropping it from the rendered view
                            pass
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
        if format == 'conversation':
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

        if format == 'json':
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

        elif format in ('plain', 'markdown', 'table'):
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
                    if format == 'table':
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
            if format == 'table':
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
            raise ValueError("Unknown format: {}".format(format))

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
>>> print(mem.render(role_filter=['user'], format='markdown'))

# Render as a table, including logs and reflections
>>> print(mem.render(include=('msgs', 'logs', 'refs'), format='table'))

# Filter by channel
>>> print(mem.render(channel_filter='telegram'))

# Render with a content keyword filter and max length
>>> print(mem.render(content_filter='hello', max_length=50))

# Export as LLM-optimized conversation (for prompt construction)
>>> print(mem.render(format='conversation', max_total_length=2000))

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
>>> print(mem.render(format='conversation'))

# Export all events and rehydrate
>>> all_events = mem.get_events()
>>> mem_restored = MEMORY.from_events(all_events, mem.id)

------------------------------------------------------------
For more details, see the MEMORY class docstring and method documentation.
------------------------------------------------------------
"""


class _MemoryScope:
    """
    Zero-copy scoped perspective over a shared ``MEMORY`` instance.

    Created via ``memory.scope(actor, ...)`` or nested ``scope.scope(sub, ...)``.
    Implements the ``MEMORY`` surface consumed by ``THOUGHT``, ``DECIDE``,
    ``PLAN``, ``ACTION``, ``CHAT``, and ``WORKFLOW`` while isolating message
    visibility (by room/channel) and variable namespaces (``{actor}__{key}`` vs
    shared ``public_keys`` / ``export_keys``) on a single root event log.
    """

    def __init__(
        self,
        base,
        actor,
        read_rooms=None,
        write_room=None,
        public_keys=(),
        export_keys=(),
        _ancestor_prefixes=(),
        _export_prefix="",
    ):
        """Initialize a zero-copy scoped perspective unwrapping directly to the root MEMORY."""
        if not isinstance(actor, str) or not actor.strip():
            raise ValueError("scope actor must be a non-empty string")
        sub_actor = actor.strip()

        # Unwrap nested _MemoryScope instances so self.base is always the root
        # MEMORY (avoiding wrapper-chain discrepancies in vars / is_var_deleted).
        if isinstance(base, _MemoryScope):
            parent = base
            root_base = parent.base
            full_actor = "{}__{}".format(parent.actor, sub_actor)
            ancestor_prefixes = parent._ancestor_prefixes + (parent.ns,)
            eff_read_rooms = (
                set(read_rooms)
                if read_rooms is not None
                else (set(parent.read_rooms) if parent.read_rooms is not None else None)
            )
            eff_write_room = parent.write_room if write_room is None else write_room
            eff_export_prefix = parent.ns
            parent_root_exports = parent._root_export_keys
        else:
            root_base = base
            full_actor = sub_actor
            ancestor_prefixes = tuple(_ancestor_prefixes or ())
            eff_read_rooms = set(read_rooms) if read_rooms is not None else None
            eff_write_room = write_room
            eff_export_prefix = _export_prefix
            parent_root_exports = None

        self.base = root_base
        self.actor = full_actor
        self.ns = self.actor + "__"
        self._ancestor_prefixes = ancestor_prefixes
        self._export_prefix = eff_export_prefix
        self.read_rooms = eff_read_rooms
        self.write_room = eff_write_room
        self.public_keys = set(public_keys or ()) | set(export_keys or ())
        self.export_keys = set(export_keys or ())
        if parent_root_exports is None:
            self._root_export_keys = set(self.export_keys)
        else:
            self._root_export_keys = self.export_keys & parent_root_exports

        rooms_to_register = set()
        if self.write_room:
            rooms_to_register.add(self.write_room)
        if self.read_rooms:
            rooms_to_register.update(self.read_rooms)
        _register_valid_channels(self.base, rooms_to_register)

    def scope(
        self,
        actor,
        read_rooms=None,
        write_room=None,
        public_keys=None,
        export_keys=(),
    ):
        """
        Create a child scope nested under this scope against the same root ``MEMORY``.

        Variables reside under ``{parent}__{child}__{key}``. When ``public_keys``
        is omitted, the child inherits the parent's ``public_keys``; keys in
        ``export_keys`` write back to the parent scope's namespace (or to the
        root ``MEMORY`` if also exported by the parent scope).
        """
        inherited_public = self.public_keys if public_keys is None else public_keys
        return _MemoryScope(
            base=self,
            actor=actor,
            read_rooms=read_rooms,
            write_room=write_room,
            public_keys=inherited_public,
            export_keys=export_keys,
        )

    @property
    def id(self):
        """Return a composite scope identifier ``'{root_id}:{actor}'``."""
        return "{}:{}".format(self.base.id, self.actor)

    def _var_key_visible(self, raw_key):
        """Return True when ``raw_key`` belongs to this scope or its readable public keys."""
        if raw_key.startswith(self.ns):
            return True
        for key in self.public_keys:
            if raw_key == key:
                return True
            for prefix in self._ancestor_prefixes:
                if raw_key == prefix + key:
                    return True
        return False

    def _event_visible(self, event):
        """Return True when ``event`` is epistemically visible to this actor scope."""
        etype = event.get('type', 'msg')
        if etype == 'msg':
            return self._msg_in_read_rooms(event)
        if etype == 'var':
            return self._var_key_visible(event.get('var_name', ''))
        if etype == 'emit':
            actor_tag = str((event.get('payload') or {}).get('actor', ''))
            return actor_tag == self.actor or actor_tag.startswith(self.ns)
        if etype in ('log', 'ref'):
            if self.read_rooms is None:
                return True
            content = str(event.get('content', ''))
            return content.startswith("[{}] ".format(self.actor)) or content.startswith("[{}__".format(self.actor))
        return True

    @property
    def events(self):
        """Return a filtered dict of events visible to this scope."""
        return {
            stamp: ev
            for stamp, ev in self.base.events.items()
            if self._event_visible(ev)
        }

    @property
    def objects(self):
        """Expose the underlying compressed object store for stamp resolution."""
        return self.base.objects

    @property
    def valid_roles(self):
        """Return the set of valid message roles on the root MEMORY."""
        return self.base.valid_roles

    @property
    def valid_modes(self):
        """Return the set of valid communication modes on the root MEMORY."""
        return self.base.valid_modes

    @property
    def valid_channels(self):
        """Return the set of registered channels/rooms on the root MEMORY."""
        return self.base.valid_channels

    @property
    def vars(self):
        """
        Expose only visible logical variable names mapped to their raw history
        lists so ``THOUGHT.get_context`` never touches or decompresses foreign
        actor variables or unrelated large objects on ``self.base``.
        """
        visible = {}
        for key in self.public_keys:
            if key in self.base.vars and not self.base.is_var_deleted(key):
                visible[key] = self.base.vars[key]
            for prefix in self._ancestor_prefixes:
                cand = prefix + key
                if cand in self.base.vars and not self.base.is_var_deleted(cand):
                    visible[key] = self.base.vars[cand]
        for raw_key, history in self.base.vars.items():
            if raw_key.startswith(self.ns) and not self.base.is_var_deleted(raw_key):
                logical = raw_key[len(self.ns):]
                visible[logical] = history
        return visible

    def _resolve_read_key(self, key):
        scoped = self.ns + key
        if scoped in self.base.vars and not self.base.is_var_deleted(scoped):
            return scoped
        if key in self.public_keys:
            for prefix in reversed(self._ancestor_prefixes):
                cand = prefix + key
                if cand in self.base.vars and not self.base.is_var_deleted(cand):
                    return cand
            if key in self.base.vars and not self.base.is_var_deleted(key):
                return key
        return None

    def _resolve_write_key(self, key):
        if key in self.export_keys:
            if key in self._root_export_keys or not self._export_prefix:
                return key
            return self._export_prefix + key
        return self.ns + key

    def get_var(self, key, resolve_refs=True):
        """Read ``{actor}__{key}`` first, falling back to ancestor/root ``public_keys``."""
        real = self._resolve_read_key(key)
        if real is None:
            return None
        return self.base.get_var(real, resolve_refs=resolve_refs)

    def get_all_vars(self, resolve_refs=True):
        """Return a dict of all non-deleted variables visible to this scope."""
        return {
            key: self.get_var(key, resolve_refs=resolve_refs)
            for key in self.vars
        }

    def set_var(self, key, value, desc='', metadata=None, source=None):
        """Write ``key`` into ``{actor}__{key}`` (or export target when in ``export_keys``)."""
        target = self._resolve_write_key(key)
        return self.base.set_var(target, value, desc=desc, metadata=metadata, source=source)

    def upsert(self, key, value, desc='', metadata=None, source=None):
        """Upsert ``key`` on this scope's write target; no-op returning False when unchanged."""
        target = self._resolve_write_key(key)
        return self.base.upsert(target, value, desc=desc, metadata=metadata, source=source)

    def get_var_meta(self, key):
        """Return latest structured variable metadata for visible ``key``, or None."""
        real = self._resolve_read_key(key)
        if real is None:
            return None
        return self.base.get_var_meta(real)

    def find_vars(
        self,
        prefix=None,
        desc_contains=None,
        changed_since=None,
        metadata_filter=None,
        include_meta=False,
        resolve_refs=True,
    ):
        """Query visible variables in this scope using logical (unprefixed) names."""
        stamps_after = None
        if changed_since is not None:
            after_events = self.base.get_events(since=changed_since)
            stamps_after = {ev.get("stamp") for ev in after_events}

        desc_needle = desc_contains.lower() if isinstance(desc_contains, str) else None
        out = {}
        for logical_key in self.vars:
            if prefix is not None and not logical_key.startswith(prefix):
                continue
            real_key = self._resolve_read_key(logical_key)
            if real_key is None:
                continue
            history = self.base.vars.get(real_key) or []
            if not history or history[-1][1] is VAR_DELETED:
                continue
            desc = self.base._get_latest_desc(real_key)
            if desc_needle is not None and desc_needle not in (desc or "").lower():
                continue
            if stamps_after is not None:
                if not any(st in stamps_after for st, _ in history):
                    continue
            meta = self.base._get_latest_meta(real_key)
            if metadata_filter:
                meta_map = meta or {}
                src_map = meta_map.get("source") if isinstance(meta_map.get("source"), dict) else {}
                if not all(
                    (mk in meta_map and meta_map[mk] == mv) or (mk in src_map and src_map[mk] == mv)
                    for mk, mv in metadata_filter.items()
                ):
                    continue
            val = self.base.get_var(real_key, resolve_refs=resolve_refs)
            if include_meta:
                out[logical_key] = {
                    "value": val,
                    "stamp": history[-1][0],
                    "desc": desc,
                    "metadata": meta,
                }
            else:
                out[logical_key] = val
        return out

    def del_var(self, key):
        """Append a deletion tombstone on this scope's write target for ``key``."""
        target = self._resolve_write_key(key)
        if target not in self.base.vars:
            return None
        return self.base.del_var(target)

    def is_var_deleted(self, key):
        """Return True if ``key`` was tombstoned in this scope or in visible ``public_keys``."""
        scoped = self.ns + key
        if scoped in self.base.vars:
            return self.base.is_var_deleted(scoped)
        if key in self.public_keys:
            for prefix in reversed(self._ancestor_prefixes):
                cand = prefix + key
                if cand in self.base.vars:
                    return self.base.is_var_deleted(cand)
            if key in self.base.vars:
                return self.base.is_var_deleted(key)
        return False

    def _msg_in_read_rooms(self, event):
        """Return True when ``event`` belongs to one of this scope's ``read_rooms``."""
        if self.read_rooms is None:
            return True
        meta = event.get('metadata') or {}
        if meta.get('room') in self.read_rooms:
            return True
        return event.get('channel') in self.read_rooms

    def add_msg(
        self,
        role,
        content="",
        mode='text',
        channel=None,
        metadata=None,
        tool_calls=None,
        tool_call_id=None,
        name=None,
    ):
        """Append a message tagged with ``actor`` and routed to ``write_room`` by default."""
        meta = dict(metadata or {})
        meta.setdefault('actor', self.actor)
        if self.write_room:
            meta.setdefault('room', self.write_room)
        eff_channel = channel or self.write_room or 'unknown'
        _register_valid_channels(self.base, (eff_channel,))
        return self.base.add_msg(
            role,
            content,
            mode=mode,
            channel=eff_channel,
            metadata=meta,
            tool_calls=tool_calls,
            tool_call_id=tool_call_id,
            name=name,
        )

    def add_augment(
        self,
        content,
        target='last_user',
        role='system',
        mode='text',
        channel=None,
        metadata=None,
    ):
        """Append a scoped RAG/context augment message into this scope's ``write_room``."""
        meta = dict(metadata or {})
        meta['augments'] = target
        return self.add_msg(role, content, mode=mode, channel=channel, metadata=meta)

    def get_msgs(
        self,
        limit=-1,
        include=None,
        exclude=None,
        repr='list',
        channel=None,
        metadata_filter=None,
        exclude_metadata=None,
    ):
        """Return messages visible in ``read_rooms`` matching role/channel/metadata filters."""
        events = self.base.get_msgs(
            limit=-1,
            include=include,
            exclude=exclude,
            repr='list',
            channel=channel,
            metadata_filter=metadata_filter,
            exclude_metadata=exclude_metadata,
        )
        if self.read_rooms is not None:
            events = [e for e in events if self._msg_in_read_rooms(e)]
        if limit > 0:
            events = events[-limit:]
        if repr == 'list':
            return events
        if repr == 'str':
            return '\n'.join(["{}: {}".format(e['role'], e['content']) for e in events])
        if repr == 'pprint1':
            return pprint.pformat(events, indent=1)
        raise ValueError("Invalid repr option. Choose from 'list', 'str', or 'pprint1'.")

    def get_events(self, limit=-1, event_types=None, channel=None, since=None):
        """Return master-index events filtered to those epistemically visible to this scope."""
        events = [
            e
            for e in self.base.get_events(
                limit=-1, event_types=event_types, channel=channel, since=since
            )
            if self._event_visible(e)
        ]
        return events[-limit:] if limit > 0 else events

    def get_logs(self, limit=-1):
        """Return log entries visible to this scope."""
        logs = [e for e in self.base.get_logs(limit=-1) if self._event_visible(e)]
        return logs[-limit:] if limit > 0 else logs

    def get_refs(self, limit=-1):
        """Return reflection entries visible to this scope."""
        refs = [e for e in self.base.get_refs(limit=-1) if self._event_visible(e)]
        return refs[-limit:] if limit > 0 else refs

    def get_llm_msgs(
        self,
        merge_augments=False,
        include=None,
        exclude=None,
        format='raw',
        channel=None,
        metadata_filter=None,
        exclude_metadata=None,
        budget_tokens=None,
        pinned=True,
        summarizer=None,
        token_counter=None,
    ):
        """Build LLM-ready message dicts from this scope's visible room history."""
        if format not in ('raw', 'openai'):
            raise ValueError("Invalid format '{}'. Choose 'raw' or 'openai'.".format(format))
        effective_include = include
        if format == 'openai' and effective_include is None:
            effective_include = list(MEMORY.OPENAI_LLM_ROLES)
        events = self.get_msgs(
            include=effective_include,
            exclude=exclude,
            channel=channel,
            metadata_filter=metadata_filter,
            exclude_metadata=exclude_metadata,
        )
        return self.base._build_llm_view(
            events,
            merge_augments=merge_augments,
            format=format,
            budget_tokens=budget_tokens,
            pinned=pinned,
            summarizer=summarizer,
            token_counter=token_counter,
        )

    def compact(self, keep=6, summarizer=None, channel='unknown'):
        """Summarize older visible turns in this scope without deleting raw events."""
        return MEMORY.compact(self, keep=keep, summarizer=summarizer, channel=channel)

    def suspend(self, reason, pending=None, resume_at=None, suspension_id=None):
        """Record a scoped suspension marker under ``{actor}___suspension``."""
        return MEMORY.suspend(self, reason, pending, resume_at, suspension_id)

    def get_suspension(self):
        """Return this scope's current suspension record, or None."""
        return MEMORY.get_suspension(self)

    def is_suspended(self):
        """Return True while this scope holds an unresolved suspension."""
        return MEMORY.is_suspended(self)

    def resolve_suspension(self, decision=None):
        """Idempotently resolve this scope's suspension with ``decision``."""
        return MEMORY.resolve_suspension(self, decision)

    def last_user_msg(self, content_only=False):
        """Return the most recent visible ``user`` message in this scope."""
        msgs = self.get_msgs(include=['user'])
        if not msgs:
            return '' if content_only else None
        return msgs[-1]['content'] if content_only else msgs[-1]

    def last_asst_msg(self, content_only=False):
        """Return the most recent visible ``assistant`` message in this scope."""
        msgs = self.get_msgs(include=['assistant'])
        if not msgs:
            return '' if content_only else None
        return msgs[-1]['content'] if content_only else msgs[-1]

    def last_sys_msg(self, content_only=False):
        """Return the most recent visible ``system`` message in this scope."""
        msgs = self.get_msgs(include=['system'])
        if not msgs:
            return '' if content_only else None
        return msgs[-1]['content'] if content_only else msgs[-1]

    def last_result_msg(self, content_only=False):
        """Return the most recent visible ``result`` message in this scope."""
        msgs = self.get_msgs(include=['result'])
        if not msgs:
            return '' if content_only else None
        return msgs[-1]['content'] if content_only else msgs[-1]

    def last_log_msg(self, content_only=False):
        """Return the most recent visible log entry in this scope."""
        logs = self.get_logs()
        if not logs:
            return '' if content_only else None
        return logs[-1]['content'] if content_only else logs[-1]

    def last_ref(self, content_only=False):
        """Return the most recent visible reflection entry in this scope."""
        refs = self.get_refs()
        if not refs:
            return '' if content_only else None
        return refs[-1]['content'] if content_only else refs[-1]

    def add_log(self, message):
        """Append a log entry prefixed with ``[{actor}]``."""
        return self.base.add_log("[{}] {}".format(self.actor, message))

    def add_ref(self, content):
        """Append a reflection entry prefixed with ``[{actor}]``."""
        return self.base.add_ref("[{}] {}".format(self.actor, content))

    def emit(self, kind, payload, schema_version=1):
        """Emit a typed lifecycle event tagged with ``payload['actor'] = self.actor``."""
        tagged = dict(payload) if isinstance(payload, dict) else payload
        if isinstance(tagged, dict):
            tagged.setdefault('actor', self.actor)
        return self.base.emit(kind, tagged, schema_version=schema_version)

    def get_emits(self, kind=None, limit=-1):
        """Return lifecycle emits produced by this actor or its nested child scopes."""
        emits = self.base.get_emits(kind=kind, limit=-1)
        scoped = [
            e
            for e in emits
            if (e.get('payload') or {}).get('actor') == self.actor
            or str((e.get('payload') or {}).get('actor', '')).startswith(self.ns)
        ]
        return scoped[-limit:] if limit > 0 else scoped

    def set_obj(self, data, name=None, desc='', content_type='auto'):
        """Store a compressed object on the root MEMORY, scoping ``name`` when provided."""
        mapped_name = self._resolve_write_key(name) if name else None
        return self.base.set_obj(data, name=mapped_name, desc=desc, content_type=content_type)

    def get_obj(self, stamp):
        """Decompress and return an object by stamp from the root MEMORY."""
        return self.base.get_obj(stamp)

    def get_obj_info(self, stamp):
        """Return compressed object size/type metadata without decompressing."""
        return self.base.get_obj_info(stamp)

    def add_exchange(
        self,
        kind,
        key,
        service,
        model,
        request,
        response,
        usage=None,
        default_params=None,
    ):
        """Record a model/tool exchange on the root MEMORY."""
        return self.base.add_exchange(
            kind,
            key,
            service,
            model,
            request,
            response,
            usage=usage,
            default_params=default_params,
        )

    def get_exchanges(self, kind=None):
        """Retrieve recorded exchanges from the root MEMORY."""
        return self.base.get_exchanges(kind=kind)

    def copy(self):
        """Return an independent deep copy of both the root MEMORY and this scope view."""
        copied = _MemoryScope(
            base=self.base.copy(),
            actor=self.actor,
            read_rooms=self.read_rooms,
            write_room=self.write_room,
            public_keys=self.public_keys,
            export_keys=self.export_keys,
            _ancestor_prefixes=self._ancestor_prefixes,
            _export_prefix=self._export_prefix,
        )
        copied._root_export_keys = set(self._root_export_keys)
        return copied


__all__ = [
    "MEMORY",
]
