"""
Unit tests for ThoughtFlow's record/replay system.

Record/replay is the deterministic-testing story of the library: LLM/EMBED
exchanges are captured as MEMORY events, and Replay variants serve those
recorded responses by content-hash lookup — offline and byte-identical.
"""

from __future__ import annotations

import pytest

from thoughtflow import LLM, EMBED, MEMORY, THOUGHT, ReplayLLM, ReplayEMBED, ReplayMissError


MSGS = [{"role": "user", "content": "What is the meaning of life?"}]


def make_recorded_memory(responses=("Forty-two.",), msgs=MSGS, params=None):
    """Build a MEMORY containing recorded exchanges for the given request."""
    live = LLM("openai:gpt-4o", key="test-key")
    memory = MEMORY()
    for response in responses:
        key, request = live._request_signature(msgs, params or {}, None)
        memory.add_exchange(
            kind="chat", key=key, service="openai", model="gpt-4o",
            request=request, response=[response],
        )
    return memory


class TestRecording:
    """Tests for LLM.record() capturing exchanges into MEMORY."""

    def test_record_captures_exchange(self, monkeypatch):
        """A recorded LLM call must append an exchange event to memory."""
        llm = LLM("openai:gpt-4o", key="test-key")
        monkeypatch.setattr(LLM, "_call_openai", lambda self, m, p, transport=None: ["Recorded!"])

        memory = MEMORY()
        llm.record(memory)
        choices = llm.call(MSGS)

        assert choices == ["Recorded!"]
        exchanges = memory.get_exchanges(kind="chat")
        assert len(exchanges) == 1
        assert exchanges[0]["service"] == "openai"
        assert exchanges[0]["model"] == "gpt-4o"
        assert exchanges[0]["response"] == ["Recorded!"]

    def test_record_via_constructor_kwarg(self, monkeypatch):
        """LLM(record=memory) must enable recording at construction."""
        memory = MEMORY()
        llm = LLM("openai:gpt-4o", key="test-key", record=memory)
        monkeypatch.setattr(LLM, "_call_openai", lambda self, m, p, transport=None: ["Hi"])

        llm.call(MSGS)

        assert len(memory.get_exchanges()) == 1

    def test_record_none_stops_recording(self, monkeypatch):
        """record(None) must stop capturing exchanges."""
        memory = MEMORY()
        llm = LLM("openai:gpt-4o", key="test-key", record=memory)
        monkeypatch.setattr(LLM, "_call_openai", lambda self, m, p, transport=None: ["Hi"])

        llm.call(MSGS)
        llm.record(None)
        llm.call(MSGS)

        assert len(memory.get_exchanges()) == 1

    def test_record_key_excludes_transport_params(self):
        """Exchange keys must ignore transport params (base_url etc.)."""
        llm = LLM("openai:gpt-4o", key="test-key")

        key_cloud, _ = llm._request_signature(MSGS, {}, None)
        key_local, _ = llm._request_signature(
            MSGS, {"base_url": "http://localhost:8000/v1"}, None
        )

        assert key_cloud == key_local

    def test_record_key_depends_on_content(self):
        """Different messages or params must produce different keys."""
        llm = LLM("openai:gpt-4o", key="test-key")

        key_a, _ = llm._request_signature(MSGS, {}, None)
        key_b, _ = llm._request_signature(
            [{"role": "user", "content": "Different"}], {}, None
        )
        key_c, _ = llm._request_signature(MSGS, {"temperature": 0.9}, None)

        assert key_a != key_b
        assert key_a != key_c


class TestReplayLLM:
    """Tests for ReplayLLM serving recorded responses."""

    def test_replay_serves_recorded_response(self):
        """A replayed request must return the recorded response."""
        memory = make_recorded_memory()
        replay = LLM.replay(memory)

        assert replay.call(MSGS) == ["Forty-two."]

    def test_replay_is_llm_compatible(self):
        """ReplayLLM must expose service/model like a live LLM."""
        replay = LLM.replay(make_recorded_memory())

        assert isinstance(replay, LLM)
        assert replay.service == "openai"
        assert replay.model == "gpt-4o"

    def test_replay_miss_raises(self):
        """An unrecorded request must raise ReplayMissError by default."""
        replay = LLM.replay(make_recorded_memory())

        with pytest.raises(ReplayMissError):
            replay.call([{"role": "user", "content": "Never recorded"}])

    def test_replay_miss_falls_back_to_live_llm(self, monkeypatch):
        """on_miss=<live LLM> must delegate unrecorded requests."""
        fallback = LLM("openai:gpt-4o", key="test-key")
        monkeypatch.setattr(LLM, "_call_openai", lambda self, m, p, transport=None: ["Live answer"])

        replay = ReplayLLM(make_recorded_memory(), on_miss=fallback)
        result = replay.call([{"role": "user", "content": "Never recorded"}])

        assert result == ["Live answer"]

    def test_replay_repeated_requests_serve_in_order(self):
        """Identical requests must replay in recorded order, then repeat last."""
        memory = make_recorded_memory(responses=("First", "Second"))
        replay = LLM.replay(memory)

        assert replay.call(MSGS) == ["First"]
        assert replay.call(MSGS) == ["Second"]
        assert replay.call(MSGS) == ["Second"]

    def test_replay_survives_json_round_trip(self, monkeypatch):
        """Recordings must replay after MEMORY to_json/from_json."""
        llm = LLM("openai:gpt-4o", key="test-key")
        memory = MEMORY()
        llm.record(memory)
        monkeypatch.setattr(LLM, "_call_openai", lambda self, m, p, transport=None: ["Persisted"])
        llm.call(MSGS)

        restored = MEMORY.from_json(memory.to_json())
        replay = LLM.replay(restored)

        assert replay.call(MSGS) == ["Persisted"]

    def test_replay_multiple_models_requires_model_id(self):
        """Memory with multiple recorded models must require model_id."""
        memory = make_recorded_memory()
        live = LLM("anthropic:claude-3", key="test-key")
        key, request = live._request_signature(MSGS, {}, None)
        memory.add_exchange(
            kind="chat", key=key, service="anthropic", model="claude-3",
            request=request, response=["From Claude"],
        )

        with pytest.raises(ValueError, match="multiple models"):
            LLM.replay(memory)

        replay = LLM.replay(memory, model_id="anthropic:claude-3")
        assert replay.call(MSGS) == ["From Claude"]

    def test_replay_stream_yields_single_chunk(self):
        """stream=True on a ReplayLLM must yield the recorded text."""
        replay = LLM.replay(make_recorded_memory())

        chunks = list(replay.call(MSGS, stream=True))

        assert "".join(chunks) == "Forty-two."

    def test_end_to_end_flow_replays_deterministically(self, monkeypatch):
        """A THOUGHT flow recorded once must replay without the 'network'."""
        calls = {"count": 0}

        def fake_openai(self, msg_list, params, transport=None):
            calls["count"] += 1
            return ["The answer is 42."]

        monkeypatch.setattr(LLM, "_call_openai", fake_openai)

        def flow(memory, llm):
            thought = THOUGHT(name="respond", llm=llm,
                              prompt="Answer: {last_user_msg}")
            return thought(memory)

        # Record
        live = LLM("openai:gpt-4o", key="test-key")
        recording = MEMORY()
        live.record(recording)
        mem1 = MEMORY()
        mem1.add_msg("user", "What is the answer?")
        mem1 = flow(mem1, live)
        assert calls["count"] == 1

        # Replay — no further "network" calls
        replay = LLM.replay(recording)
        mem2 = MEMORY()
        mem2.add_msg("user", "What is the answer?")
        mem2 = flow(mem2, replay)

        assert calls["count"] == 1
        assert mem2.get_var("respond_result") == mem1.get_var("respond_result")

    def test_replay_adopts_recorded_default_params_automatically(self, monkeypatch):
        """Issue #34: ReplayLLM must adopt recorded sampling params without manual default_params.update."""
        monkeypatch.setattr(LLM, "_call_openai", lambda self, m, p, transport=None: ["ParamHit"])

        # Live LLM configured with constructor sampling defaults AND one per-call override
        live = LLM("openai:gpt-4o", key="test-key", temperature=0.2, max_tokens=256)
        recording = MEMORY()
        live.record(recording)
        live.call(MSGS)
        live.call([{"role": "user", "content": "Override"}], params={"max_tokens": 512})

        replay = LLM.replay(recording)
        assert replay.default_params == {"temperature": 0.2, "max_tokens": 256}
        assert replay.call(MSGS) == ["ParamHit"]
        assert replay.call([{"role": "user", "content": "Override"}], params={"max_tokens": 512}) == ["ParamHit"]

    def test_replay_adopts_legacy_shared_params_and_tracks_misses(self):
        """Issue #34: Legacy recordings without default_params adopt shared request params; misses are recorded."""
        memory = make_recorded_memory(params={"temperature": 0.7})
        replay = LLM.replay(memory)

        assert replay.default_params == {"temperature": 0.7}
        assert replay.call(MSGS) == ["Forty-two."]
        assert replay.misses == []

        unrecorded_msgs = [{"role": "user", "content": "Unrecorded question"}]
        with pytest.raises(ReplayMissError):
            replay.call(unrecorded_msgs)

        assert len(replay.misses) == 1
        assert replay.misses[0]["kind"] == "call"
        assert replay.misses[0]["request"]["messages"] == unrecorded_msgs

    def test_cassette_records_when_missing_then_replays_when_present(self, tmp_path, monkeypatch):
        """Issue #34: LLM.cassette records atomically on first run and replays offline on second run."""
        calls = {"count": 0}

        def fake_openai(self, msg_list, params, transport=None):
            calls["count"] += 1
            return ["CassetteAnswer"]

        monkeypatch.setattr(LLM, "_call_openai", fake_openai)
        cassette_file = tmp_path / "nested" / "greeting.json"

        # First run: file missing -> calls live factory, records, and flushes to disk
        llm1 = LLM.cassette(
            cassette_file,
            live=lambda: LLM("openai:gpt-4o", key="test-key", temperature=0.1),
        )
        assert llm1.cassette_mode == "record"
        assert llm1.call(MSGS) == ["CassetteAnswer"]
        assert cassette_file.is_file()
        assert calls["count"] == 1

        # Second run: file exists -> live factory is NOT called, replays offline with adopted params
        def should_not_be_called():
            raise AssertionError("live factory must not run when cassette exists")

        with LLM.cassette(cassette_file, live=should_not_be_called) as llm2:
            assert llm2.cassette_mode == "replay"
            assert llm2.call(MSGS) == ["CassetteAnswer"]
        assert calls["count"] == 1

    def test_usage_ledger_exchange_storage_emits_and_replay_total_usage(self, monkeypatch):
        """Issue #42: llm.usage accumulates calls/tokens/cost, stores usage in exchanges, emits on memory, and replays."""
        responses = [
            {
                "choices": [{"message": {"content": "One"}, "finish_reason": "stop"}],
                "usage": {
                    "prompt_tokens": 12,
                    "completion_tokens": 8,
                    "prompt_tokens_details": {"cached_tokens": 4},
                    "completion_tokens_details": {"reasoning_tokens": 3},
                    "cost": 0.0015,
                },
            },
            {
                "choices": [{"message": {"content": "Two"}, "finish_reason": "stop"}],
                "usage": {
                    "prompt_tokens": 20,
                    "completion_tokens": 10,
                    "cost": 0.0025,
                },
            },
        ]
        idx = {"i": 0}

        class FakeResp:
            def __init__(self, payload):
                self._raw = payload

            def read(self):
                import json as _json
                return _json.dumps(self._raw).encode("utf-8")

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        def fake_urlopen(req, **kwargs):
            payload = responses[idx["i"]]
            idx["i"] += 1
            return FakeResp(payload)

        import urllib.request
        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

        rec_mem = MEMORY()
        live = LLM("openrouter:deepseek/deepseek-chat", key="test-key").record(rec_mem)
        assert live.call(MSGS) == ["One"]
        assert live.call([{"role": "user", "content": "Second"}]) == ["Two"]

        assert live.usage == {
            "calls": 2,
            "prompt_tokens": 32,
            "completion_tokens": 18,
            "total_tokens": 50,
            "reasoning_tokens": 3,
            "cached_tokens": 4,
            "cost": 0.004,
        }

        usage_emits = rec_mem.get_emits("usage")
        assert len(usage_emits) == 2
        assert usage_emits[0]["payload"]["prompt_tokens"] == 12
        assert rec_mem.get_exchanges()[0]["usage"]["cost"] == 0.0015

        # Offline total_usage() and replayed live ledger after JSON round-trip
        restored = MEMORY.from_json(rec_mem.to_json())
        replay = LLM.replay(restored)
        assert replay.total_usage() == live.usage
        assert replay.usage["calls"] == 0

        assert replay.call(MSGS) == ["One"]
        assert replay.last_usage["prompt_tokens"] == 12
        assert replay.usage["calls"] == 1
        assert replay.usage["total_tokens"] == 20

        live.reset_usage()
        assert live.usage["calls"] == 0
        assert live.usage["cost"] == 0.0


class TestReplayEMBED:
    """Tests for EMBED record/replay."""

    def test_embed_record_and_replay(self, monkeypatch):
        """Recorded embeddings must replay identically."""
        vec = [0.1, 0.2, 0.3]
        monkeypatch.setattr(EMBED, "_call_openai", lambda self, t, p: [vec])

        embed = EMBED("openai:text-embedding-3-small", key="test-key")
        memory = MEMORY()
        embed.record(memory)
        live_result = embed.call("Hello world")

        replay = EMBED.replay(memory)
        assert replay.call("Hello world") == live_result == vec

    def test_embed_replay_handles_list_input(self, monkeypatch):
        """List inputs must round-trip through record/replay."""
        vecs = [[0.1], [0.2]]
        monkeypatch.setattr(EMBED, "_call_openai", lambda self, t, p: vecs)

        embed = EMBED("openai:text-embedding-3-small", key="test-key")
        memory = MEMORY()
        embed.record(memory)
        embed.call(["a", "b"])

        replay = EMBED.replay(memory)
        assert replay.call(["a", "b"]) == vecs

    def test_embed_replay_miss_raises(self):
        """An unrecorded embed request must raise ReplayMissError."""
        replay = ReplayEMBED(MEMORY())

        with pytest.raises(ReplayMissError):
            replay.call("never recorded")
