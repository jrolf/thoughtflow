"""
Unit tests for the ThoughtFlow utility module (_util.py).

This module tests the core utility functions and classes that provide
foundational functionality for ThoughtFlow:
- EventStamp: Deterministic ID generation
- construct_prompt/construct_msgs: Prompt building
- valid_extract: Schema-based parsing from LLM output
- Compression utilities: For large data storage

All utilities are pure functions with no external dependencies,
making them ideal candidates for comprehensive unit testing.
"""

from __future__ import annotations

import time
import pytest

from thoughtflow._util import (
    EventStamp,
    event_stamp,
    hashify,
    encode_num,
    decode_num,
    construct_prompt,
    construct_msgs,
    valid_extract,
    ValidExtractError,
    VAR_DELETED,
    compress_to_json,
    decompress_from_json,
    estimate_size,
    is_obj_ref,
    truncate_content,
)


# ============================================================================
# EventStamp Tests
# ============================================================================


class TestEventStamp:
    """
    Tests for the EventStamp class which generates deterministic event IDs.
    
    EventStamp is critical infrastructure - all events in MEMORY use stamps
    for identification and ordering. The key invariant is that stamps are
    chronologically sortable (alphabetical order = time order).
    """

    def test_stamp_generates_16_character_string(self):
        """
        EventStamp.stamp() must return exactly 16 characters.
        
        This fixed length ensures consistent storage and indexing.
        The format is: 8 chars time + 5 chars doc hash + 3 chars random.
        
        Remove this test if: We change the stamp format (breaking change).
        """
        stamp = EventStamp.stamp()
        assert len(stamp) == 16
        assert isinstance(stamp, str)

    def test_stamp_contains_only_base62_characters(self):
        """
        Stamps must only contain Base62 characters (0-9, A-Z, a-z).
        
        This ensures stamps are URL-safe, filesystem-safe, and sortable.
        No special characters that could cause encoding issues.
        
        Remove this test if: We change the character set (breaking change).
        """
        stamp = EventStamp.stamp()
        valid_chars = set('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz')
        assert all(c in valid_chars for c in stamp)

    def test_stamps_are_chronologically_sortable(self):
        """
        Stamps generated later must sort after stamps generated earlier.
        
        This is a CRITICAL invariant that enables efficient event ordering
        without needing to decode timestamps. Alphabetical sorting of stamps
        must equal chronological sorting.
        
        Remove this test if: We change the stamp format (breaking change).
        """
        stamps = []
        for _ in range(10):
            stamps.append(EventStamp.stamp())
            time.sleep(0.001)  # Small delay to ensure different timestamps
        
        # Stamps should already be in sorted order (chronological)
        assert stamps == sorted(stamps)

    def test_concurrent_stamps_are_unique(self):
        """
        Multiple stamps generated rapidly must all be unique.
        
        The random component (3 chars) prevents collisions even when
        stamps are generated at the same millisecond.
        
        Remove this test if: We implement a different uniqueness strategy.
        """
        stamps = [EventStamp.stamp() for _ in range(100)]
        assert len(stamps) == len(set(stamps))  # All unique

    def test_hashify_is_deterministic(self):
        """
        hashify() must return the same hash for the same input every time.
        
        This enables content-addressable storage and deduplication.
        The same input string must always produce the same hash.
        
        Remove this test if: We change the hashing algorithm.
        """
        input_string = "test input for hashing"
        hash1 = EventStamp.hashify(input_string)
        hash2 = EventStamp.hashify(input_string)
        assert hash1 == hash2

    def test_hashify_respects_length_parameter(self):
        """
        hashify() must return a hash of exactly the specified length.
        
        Different use cases need different hash lengths. The length
        parameter controls the output size.
        
        Remove this test if: We remove the length parameter.
        """
        for length in [8, 16, 32, 64]:
            hash_result = EventStamp.hashify("test", length=length)
            assert len(hash_result) == length

    def test_encode_decode_roundtrip(self):
        """
        encode_num and decode_num must be inverse operations.
        
        Any number encoded then decoded must equal the original.
        This is essential for timestamp encoding/decoding.
        
        Remove this test if: We change the encoding scheme.
        """
        for num in [0, 1, 42, 1000, 999999, 123456789]:
            encoded = encode_num(num)
            decoded = decode_num(encoded)
            assert decoded == num

    def test_decode_time_extracts_timestamp(self):
        """
        decode_time must extract an approximate Unix timestamp from a stamp.
        
        This enables debugging and auditing by revealing when events occurred.
        The decoded time should be within a reasonable range of the actual time.
        
        Remove this test if: We change the time encoding format.
        """
        before = time.time()
        stamp = EventStamp.stamp()
        after = time.time()
        
        decoded_time = EventStamp.decode_time(stamp)
        
        # Should be within the time window (with small tolerance for processing)
        assert before - 1 <= decoded_time <= after + 1


class TestEventStampAliases:
    """
    Tests for backward-compatible function aliases.
    
    These aliases (event_stamp, hashify, etc.) provide a simpler API
    while maintaining backward compatibility.
    """

    def test_event_stamp_alias_works(self):
        """
        The event_stamp() function alias must work identically to EventStamp.stamp().
        
        This alias provides a simpler, more Pythonic interface.
        
        Remove this test if: We deprecate the alias.
        """
        stamp = event_stamp()
        assert len(stamp) == 16

    def test_hashify_alias_works(self):
        """
        The hashify() function alias must work identically to EventStamp.hashify().
        
        This alias provides a simpler interface for hashing.
        
        Remove this test if: We deprecate the alias.
        """
        result = hashify("test")
        assert len(result) == 32  # Default length


# ============================================================================
# Prompt Construction Tests
# ============================================================================


class TestConstructPrompt:
    """
    Tests for the construct_prompt function.
    
    construct_prompt builds structured prompts from dict templates,
    adding section markers that help LLMs understand prompt structure.
    """

    def test_constructs_basic_prompt(self):
        """
        construct_prompt must combine sections into a single string.
        
        Each section should be labeled with start/end markers
        containing a unique stamp for identification.
        
        Remove this test if: We change the prompt format.
        """
        prompt_obj = {
            'instruction': 'Do something',
            'context': 'Here is context',
        }
        result = construct_prompt(prompt_obj)
        
        assert 'Do something' in result
        assert 'Here is context' in result
        assert '<start instruction' in result
        assert '</end instruction' in result

    def test_respects_section_order(self):
        """
        construct_prompt must output sections in the specified order.
        
        The order parameter controls section ordering, which can
        affect LLM behavior (important context should come first).
        
        Remove this test if: We remove order parameter.
        """
        prompt_obj = {
            'second': 'Second content',
            'first': 'First content',
        }
        result = construct_prompt(prompt_obj, order=['first', 'second'])
        
        first_pos = result.find('First content')
        second_pos = result.find('Second content')
        assert first_pos < second_pos

    def test_includes_default_header(self):
        """
        construct_prompt must include explanatory header when requested.
        
        The 'default' header explains the marker format to the LLM,
        improving comprehension of the prompt structure.
        
        Remove this test if: We change header handling.
        """
        prompt_obj = {'section': 'content'}
        result = construct_prompt(prompt_obj, header='default')
        
        assert 'Markers like' in result or 'start' in result.lower()

    def test_includes_custom_header(self):
        """
        construct_prompt must include custom headers when provided.
        
        Custom headers allow tailoring the prompt introduction
        for specific use cases.
        
        Remove this test if: We remove custom header support.
        """
        prompt_obj = {'section': 'content'}
        custom_header = "CUSTOM HEADER TEXT"
        result = construct_prompt(prompt_obj, header=custom_header)
        
        assert custom_header in result

    def test_stamps_are_consistent_within_prompt(self):
        """
        All markers within a single prompt must use the same stamp.
        
        This allows matching start/end markers and identifying
        which prompt a section belongs to.
        
        Remove this test if: We change the stamping strategy.
        """
        prompt_obj = {'a': 'content a', 'b': 'content b'}
        result = construct_prompt(prompt_obj)
        
        # Extract stamps from markers (format: <start section stamp>)
        import re
        stamps = re.findall(r'<(?:start|end) \w+ (\w+)>', result)
        # All stamps should be the same
        assert len(set(stamps)) == 1


class TestConstructMsgs:
    """
    Tests for the construct_msgs function.
    
    construct_msgs builds a message list suitable for LLM APIs,
    combining system prompts, user prompts, and conversation history.
    """

    def test_adds_system_prompt_first(self):
        """
        construct_msgs must place system prompt as the first message.
        
        LLM APIs expect system prompts at the beginning to set context.
        
        Remove this test if: We change message ordering.
        """
        result = construct_msgs(
            usr_prompt='Hello',
            sys_prompt='You are helpful',
        )
        
        assert result[0]['role'] == 'system'
        assert result[0]['content'] == 'You are helpful'

    def test_adds_user_prompt_last(self):
        """
        construct_msgs must place user prompt as the last message.
        
        The user prompt represents the current query and should
        come after all context/history.
        
        Remove this test if: We change message ordering.
        """
        result = construct_msgs(
            usr_prompt='Hello',
            sys_prompt='You are helpful',
        )
        
        assert result[-1]['role'] == 'user'
        assert result[-1]['content'] == 'Hello'

    def test_performs_variable_substitution(self):
        """
        construct_msgs must replace variable placeholders in content.
        
        Variables are replaced by matching the key string literally,
        enabling template-based prompts.
        
        Remove this test if: We change the templating system.
        """
        result = construct_msgs(
            usr_prompt='Hello {name}',
            vars={'{name}': 'Alice'},  # Key includes braces
        )
        
        assert 'Hello Alice' in result[-1]['content']

    def test_preserves_existing_messages(self):
        """
        construct_msgs must preserve messages passed in the msgs parameter.
        
        This allows building on existing conversation history.
        
        Remove this test if: We change how history is handled.
        """
        existing = [{'role': 'user', 'content': 'Previous message'}]
        result = construct_msgs(
            usr_prompt='New message',
            msgs=existing,
        )
        
        contents = [m['content'] for m in result]
        assert 'Previous message' in contents
        assert 'New message' in contents

    def test_handles_dict_prompts(self):
        """
        construct_msgs must handle dict prompts by converting via construct_prompt.
        
        When prompts are dicts, they should be converted to structured strings.
        
        Remove this test if: We remove dict prompt support.
        """
        result = construct_msgs(
            usr_prompt={'section': 'content'},
        )
        
        # Should have converted the dict to a string
        assert isinstance(result[-1]['content'], str)
        assert 'content' in result[-1]['content']


# ============================================================================
# Valid Extract Tests
# ============================================================================


class TestValidExtract:
    """
    Tests for the valid_extract function.
    
    valid_extract is critical for parsing structured data from LLM output.
    LLMs often wrap requested output in prose, code fences, or other noise.
    This function must reliably extract the target structure.
    """

    def test_extracts_list_from_code_fence(self):
        """
        valid_extract must extract a list from within code fences.
        
        LLMs frequently wrap output in ```python or ```json fences.
        The function must look inside these fences for the data.
        
        Remove this test if: We implement a different parsing strategy.
        """
        text = "Here is your list:\n```python\n[1, 2, 3]\n```\nHope this helps!"
        rules = {'kind': 'python', 'format': []}
        
        result = valid_extract(text, rules)
        assert result == [1, 2, 3]

    def test_extracts_dict_from_prose(self):
        """
        valid_extract must extract a dict even when wrapped in prose.
        
        LLMs often explain their output. The function must find the
        actual data structure within explanatory text.
        
        Remove this test if: We implement a different parsing strategy.
        """
        text = "Based on your request, the answer is {'name': 'Alice', 'age': 30}. Let me know if you need more."
        rules = {'kind': 'python', 'format': {}}
        
        result = valid_extract(text, rules)
        assert result == {'name': 'Alice', 'age': 30}

    def test_validates_against_schema(self):
        """
        valid_extract must validate extracted data against the schema.
        
        The format parameter defines the expected structure. Extracted
        data that doesn't match should raise ValidExtractError.
        
        Remove this test if: We remove schema validation.
        """
        text = "{'name': 'Alice'}"
        rules = {'kind': 'python', 'format': {'name': '', 'age': 0}}
        
        # Should fail because 'age' is missing
        with pytest.raises(ValidExtractError):
            valid_extract(text, rules)

    def test_handles_optional_keys(self):
        """
        valid_extract must allow optional keys (suffixed with ?).
        
        Optional keys can be missing without causing validation failure.
        This supports flexible schemas.
        
        Remove this test if: We change optional key syntax.
        """
        text = "{'name': 'Alice'}"
        rules = {'kind': 'python', 'format': {'name': '', 'age?': 0}}
        
        result = valid_extract(text, rules)
        assert result == {'name': 'Alice'}

    def test_validates_nested_structures(self):
        """
        valid_extract must validate nested dicts and lists.
        
        Complex schemas with nested structures should be fully validated.
        
        Remove this test if: We remove nested validation.
        """
        text = "{'user': {'name': 'Alice'}, 'scores': [1, 2, 3]}"
        rules = {'kind': 'python', 'format': {'user': {'name': ''}, 'scores': []}}
        
        result = valid_extract(text, rules)
        assert result['user']['name'] == 'Alice'
        assert result['scores'] == [1, 2, 3]

    def test_validates_list_element_types(self):
        """
        valid_extract must validate types of list elements when specified.
        
        The schema [int] means "list of integers". Each element should
        match the specified type.
        
        Remove this test if: We remove typed list validation.
        """
        text = "[1, 2, 3]"
        rules = {'kind': 'python', 'format': [int]}
        
        result = valid_extract(text, rules)
        assert result == [1, 2, 3]

    def test_raises_on_invalid_parsing_rules(self):
        """
        valid_extract must raise ValidExtractError for invalid rules.
        
        The parsing_rules parameter must be a mapping with 'format' key.
        Invalid rules should be rejected early.
        
        Remove this test if: We change the rules format.
        """
        with pytest.raises(ValidExtractError):
            valid_extract("text", "not a dict")

    def test_raises_when_no_valid_candidate_found(self):
        """
        valid_extract must raise ValidExtractError when extraction fails.
        
        If the text contains no parseable structure matching the schema,
        a clear error should be raised.
        
        Remove this test if: We change error handling strategy.
        """
        text = "This text contains no list at all."
        rules = {'kind': 'python', 'format': []}
        
        with pytest.raises(ValidExtractError):
            valid_extract(text, rules)

    def test_handles_json_kind(self):
        """
        valid_extract must support JSON parsing via kind='json'.
        
        JSON is common in LLM output. The function should handle
        both Python literal and JSON parsing.
        
        Remove this test if: We remove JSON support.
        """
        text = '{"name": "Alice", "active": true}'
        rules = {'kind': 'json', 'format': {'name': '', 'active': bool}}
        
        result = valid_extract(text, rules)
        assert result['name'] == 'Alice'
        assert result['active'] is True

    def test_prefers_code_fences_over_raw_text(self):
        """
        valid_extract should prefer content inside code fences.
        
        When both fenced and unfenced candidates exist, fenced content
        is more likely to be the intended output.
        
        Remove this test if: We change candidate prioritization.
        """
        text = "Wrong: [0, 0, 0]\n```python\n[1, 2, 3]\n```"
        rules = {'kind': 'python', 'format': []}
        
        result = valid_extract(text, rules)
        # Should prefer the fenced version
        assert result == [1, 2, 3]

    def test_handles_inline_code_fences(self):
        """
        valid_extract must handle inline code fences (no newlines).
        
        Some LLM outputs use inline fences like ```[1,2,3]```.
        
        Remove this test if: We change fence parsing.
        """
        text = "The answer is ```[1, 2, 3]``` as requested."
        rules = {'kind': 'python', 'format': []}
        
        result = valid_extract(text, rules)
        assert result == [1, 2, 3]

    def test_validates_string_type(self):
        """
        valid_extract must validate string types in schema.
        
        Schema '' or str means the value should be a string.
        
        Remove this test if: We change type indicators.
        """
        text = "{'name': 'Alice'}"
        rules = {'kind': 'python', 'format': {'name': ''}}
        
        result = valid_extract(text, rules)
        assert result['name'] == 'Alice'

    def test_validates_int_type(self):
        """
        valid_extract must validate integer types in schema.
        
        Schema 0 or int means the value should be an integer.
        
        Remove this test if: We change type indicators.
        """
        text = "{'count': 42}"
        rules = {'kind': 'python', 'format': {'count': 0}}
        
        result = valid_extract(text, rules)
        assert result['count'] == 42

    def test_validates_float_type(self):
        """
        valid_extract must validate float types in schema.
        
        Schema 0.0 or float means the value should be a float.
        
        Remove this test if: We change type indicators.
        """
        text = "{'value': 3.14}"
        rules = {'kind': 'python', 'format': {'value': 0.0}}
        
        result = valid_extract(text, rules)
        assert result['value'] == 3.14

    def test_validates_bool_type(self):
        """
        valid_extract must validate boolean types in schema.
        
        Schema True/False or bool means the value should be boolean.
        
        Remove this test if: We change type indicators.
        """
        text = "{'active': True}"
        rules = {'kind': 'python', 'format': {'active': bool}}
        
        result = valid_extract(text, rules)
        assert result['active'] is True


# ============================================================================
# Compression Tests
# ============================================================================


class TestCompression:
    """
    Tests for the compression utility functions.
    
    These functions handle compressing and decompressing data for
    efficient storage of large objects in MEMORY.
    """

    def test_compress_decompress_roundtrip_bytes(self):
        """
        compress_to_json and decompress_from_json must roundtrip bytes.
        
        Binary data should survive compression and decompression intact.
        
        Remove this test if: We change the compression format.
        """
        original = b"Hello, this is binary data! " * 100
        compressed = compress_to_json(original, content_type='bytes')
        recovered = decompress_from_json(compressed)
        
        assert recovered == original

    def test_compress_decompress_roundtrip_text(self):
        """
        compress_to_json and decompress_from_json must roundtrip text.
        
        String data should survive compression and decompression intact.
        
        Remove this test if: We change the compression format.
        """
        original = "Hello, this is text data! " * 100
        compressed = compress_to_json(original, content_type='text')
        recovered = decompress_from_json(compressed)
        
        assert recovered == original

    def test_compress_decompress_roundtrip_json(self):
        """
        compress_to_json and decompress_from_json must roundtrip JSON data.
        
        JSON-serializable data structures should survive intact.
        
        Remove this test if: We change the compression format.
        """
        original = {'name': 'Alice', 'scores': [1, 2, 3], 'active': True}
        compressed = compress_to_json(original, content_type='json')
        recovered = decompress_from_json(compressed)
        
        assert recovered == original

    def test_compression_reduces_size(self):
        """
        Compression should reduce the size of repetitive data.
        
        While not guaranteed for all inputs, repetitive data should
        compress significantly.
        
        Remove this test if: We change compression algorithm.
        """
        original = "x" * 10000
        compressed = compress_to_json(original)
        
        assert compressed['size_compressed'] < compressed['size_original']

    def test_compressed_output_is_json_serializable(self):
        """
        compress_to_json output must be JSON-serializable.
        
        The compressed data needs to be storable in JSON format
        for persistence and transmission.
        
        Remove this test if: We change storage format.
        """
        import json
        
        original = b"Binary data here"
        compressed = compress_to_json(original)
        
        # Should not raise
        json_str = json.dumps(compressed)
        assert isinstance(json_str, str)

    def test_auto_content_type_detection(self):
        """
        compress_to_json should auto-detect content type.
        
        When content_type='auto', the function should detect whether
        the input is bytes, string, or other data.
        
        Remove this test if: We remove auto-detection.
        """
        # Bytes
        compressed = compress_to_json(b"bytes")
        assert compressed['content_type'] == 'bytes'
        
        # String
        compressed = compress_to_json("string")
        assert compressed['content_type'] == 'text'
        
        # JSON-able
        compressed = compress_to_json({'key': 'value'})
        assert compressed['content_type'] == 'json'


class TestEstimateSize:
    """
    Tests for the estimate_size utility function.
    """

    def test_estimates_string_size(self):
        """
        estimate_size should return UTF-8 byte length for strings.
        
        Remove this test if: We change size estimation.
        """
        text = "Hello"
        size = estimate_size(text)
        assert size == len(text.encode('utf-8'))

    def test_estimates_bytes_size(self):
        """
        estimate_size should return length for bytes.
        
        Remove this test if: We change size estimation.
        """
        data = b"Hello"
        size = estimate_size(data)
        assert size == len(data)

    def test_estimates_dict_size(self):
        """
        estimate_size should return JSON-encoded size for dicts.
        
        Remove this test if: We change size estimation.
        """
        import json
        data = {'key': 'value'}
        size = estimate_size(data)
        assert size == len(json.dumps(data).encode('utf-8'))


class TestIsObjRef:
    """
    Tests for the is_obj_ref utility function.
    """

    def test_detects_object_reference(self):
        """
        is_obj_ref should return True for object reference dicts.
        
        Object references have the format {'_obj_ref': stamp}.
        
        Remove this test if: We change object reference format.
        """
        ref = {'_obj_ref': 'ABC123'}
        assert is_obj_ref(ref) is True

    def test_rejects_non_reference_dict(self):
        """
        is_obj_ref should return False for regular dicts.
        
        Remove this test if: We change object reference format.
        """
        regular = {'name': 'Alice'}
        assert is_obj_ref(regular) is False

    def test_rejects_non_dict(self):
        """
        is_obj_ref should return False for non-dict values.
        
        Remove this test if: We change object reference format.
        """
        assert is_obj_ref("string") is False
        assert is_obj_ref([1, 2, 3]) is False
        assert is_obj_ref(42) is False
        assert is_obj_ref(None) is False


class TestTruncateContent:
    """
    Tests for the truncate_content utility function.
    """

    def test_short_content_unchanged(self):
        """
        truncate_content should return short content unchanged.
        
        Content below the threshold should pass through unmodified.
        
        Remove this test if: We change truncation behavior.
        """
        content = "Short content"
        result = truncate_content(content, "STAMP123", threshold=500)
        assert result == content

    def test_long_content_truncated(self):
        """
        truncate_content should truncate long content with markers.
        
        Content above threshold should be truncated with header + marker + footer.
        
        Remove this test if: We change truncation format.
        """
        content = "x" * 1000
        result = truncate_content(content, "STAMP123", threshold=500)
        
        assert len(result) < len(content)
        assert "TRUNCATED" in result
        assert "STAMP123" in result

    def test_preserves_header_and_footer(self):
        """
        truncate_content should preserve beginning and end of content.
        
        The truncation should keep a header and footer portion visible.
        
        Remove this test if: We change truncation format.
        """
        content = "HEADER_MARKER" + ("x" * 1000) + "FOOTER_MARKER"
        result = truncate_content(content, "STAMP", threshold=500, header_len=200, footer_len=200)
        
        assert "HEADER_MARKER" in result
        assert "FOOTER_MARKER" in result


# ============================================================================
# VAR_DELETED Sentinel Tests
# ============================================================================


class TestVarDeleted:
    """
    Tests for the VAR_DELETED sentinel value.
    """

    def test_var_deleted_is_singleton(self):
        """
        VAR_DELETED must be a singleton (same instance every time).
        
        This enables identity comparison (is VAR_DELETED) rather than
        equality comparison, which is more reliable.
        
        Remove this test if: We change deletion marking strategy.
        """
        from thoughtflow._util import VAR_DELETED as VAR1
        from thoughtflow._util import VAR_DELETED as VAR2
        
        assert VAR1 is VAR2

    def test_var_deleted_has_meaningful_repr(self):
        """
        VAR_DELETED should have a meaningful string representation.
        
        This aids debugging when the sentinel appears in logs or output.
        
        Remove this test if: We change the sentinel implementation.
        """
        assert '<DELETED>' in repr(VAR_DELETED)
        assert '<DELETED>' in str(VAR_DELETED)
