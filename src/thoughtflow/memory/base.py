"""
MEMORY class for ThoughtFlow.

The MEMORY class serves as an event-sourced state container for managing events, 
logs, messages, reflections, and variables within the Thoughtflow framework.
"""

from __future__ import annotations

import json
import copy
import pickle
import pprint
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
