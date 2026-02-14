"""
Unit tests for the CHAT class.

Uses a simple mock agent (a plain function that adds an assistant message
to memory) so no LLM calls are needed.
"""

from __future__ import annotations

from thoughtflow.memory import MEMORY
from thoughtflow.chat import CHAT


# ---------------------------------------------------------------------------
# Mock agent: any callable(memory) -> memory
# ---------------------------------------------------------------------------

def echo_agent(memory):
    """Echoes the last user message back as an assistant reply."""
    user_msg = memory.last_user_msg(content_only=True)
    memory.add_msg("assistant", "Echo: " + (user_msg or ""), channel="cli")
    return memory


def broken_agent(memory):
    """Always raises an exception — used to test error resilience."""
    raise RuntimeError("something went wrong")


# ---------------------------------------------------------------------------
# turn() tests
# ---------------------------------------------------------------------------

def test_turn_returns_response():
    """turn() should return the agent's response as a string."""
    chat = CHAT(echo_agent)
    response = chat.turn("hello")
    assert response == "Echo: hello"


def test_turn_updates_memory():
    """turn() should add both user and assistant messages to memory."""
    chat = CHAT(echo_agent)
    chat.turn("ping")

    user_msgs = chat.memory.get_msgs(include=["user"])
    asst_msgs = chat.memory.get_msgs(include=["assistant"])
    assert len(user_msgs) == 1
    assert user_msgs[0]["content"] == "ping"
    assert len(asst_msgs) == 1
    assert asst_msgs[0]["content"] == "Echo: ping"


def test_turn_appends_history():
    """Each turn() call should append a (user, agent) tuple to history."""
    chat = CHAT(echo_agent)
    chat.turn("one")
    chat.turn("two")

    assert len(chat.history) == 2
    assert chat.history[0] == ("one", "Echo: one")
    assert chat.history[1] == ("two", "Echo: two")


def test_turn_channel_tag():
    """User messages added by turn() should carry the configured channel."""
    chat = CHAT(echo_agent, channel="webapp")
    chat.turn("hi")

    user_msgs = chat.memory.get_msgs(include=["user"])
    assert user_msgs[-1]["channel"] == "webapp"


# ---------------------------------------------------------------------------
# Response extractor override
# ---------------------------------------------------------------------------

def test_custom_response_extractor():
    """A custom response_extractor should replace the default."""
    def custom(memory):
        return "custom: " + (memory.last_asst_msg(content_only=True) or "")

    chat = CHAT(echo_agent, response_extractor=custom)
    response = chat.turn("hello")
    assert response == "custom: Echo: hello"


# ---------------------------------------------------------------------------
# Memory ownership
# ---------------------------------------------------------------------------

def test_default_memory_created():
    """A fresh MEMORY is created when none is provided."""
    chat = CHAT(echo_agent)
    assert isinstance(chat.memory, MEMORY)


def test_existing_memory_reused():
    """An explicitly passed MEMORY is used, not replaced."""
    mem = MEMORY()
    mem.set_var("seed", 42)
    chat = CHAT(echo_agent, memory=mem)
    assert chat.memory.get_var("seed") == 42
    assert chat.memory is mem


# ---------------------------------------------------------------------------
# Exit commands
# ---------------------------------------------------------------------------

def test_builtin_exit_commands_present():
    """'q' and 'quit' should always be in exit_commands."""
    chat = CHAT(echo_agent)
    assert "q" in chat.exit_commands
    assert "quit" in chat.exit_commands


def test_additional_exit_commands_merged():
    """User-supplied exit commands should be merged with built-ins."""
    chat = CHAT(echo_agent, exit_commands={"bye", "stop"})
    assert "q" in chat.exit_commands
    assert "quit" in chat.exit_commands
    assert "bye" in chat.exit_commands
    assert "stop" in chat.exit_commands


# ---------------------------------------------------------------------------
# run() loop tests (using monkeypatch to control get_input)
# ---------------------------------------------------------------------------

def test_run_exits_on_q(monkeypatch, capsys):
    """run() should exit cleanly when the user types 'q'."""
    inputs = iter(["hello", "q"])
    chat = CHAT(echo_agent)
    monkeypatch.setattr(chat, "get_input", lambda: next(inputs))

    chat.run()

    captured = capsys.readouterr().out
    assert "Echo: hello" in captured
    assert "Goodbye!" in captured


def test_run_exits_on_quit(monkeypatch, capsys):
    """run() should exit cleanly when the user types 'quit'."""
    inputs = iter(["quit"])
    chat = CHAT(echo_agent)
    monkeypatch.setattr(chat, "get_input", lambda: next(inputs))

    chat.run()

    captured = capsys.readouterr().out
    assert "Goodbye!" in captured


def test_run_exits_on_custom_command(monkeypatch, capsys):
    """run() should recognise additional exit commands."""
    inputs = iter(["bye"])
    chat = CHAT(echo_agent, exit_commands={"bye"})
    monkeypatch.setattr(chat, "get_input", lambda: next(inputs))

    chat.run()

    captured = capsys.readouterr().out
    assert "Goodbye!" in captured


def test_run_exit_case_insensitive(monkeypatch, capsys):
    """Exit command matching should be case-insensitive."""
    inputs = iter(["QUIT"])
    chat = CHAT(echo_agent)
    monkeypatch.setattr(chat, "get_input", lambda: next(inputs))

    chat.run()

    captured = capsys.readouterr().out
    assert "Goodbye!" in captured


# ---------------------------------------------------------------------------
# Greeting
# ---------------------------------------------------------------------------

def test_greeting_displayed(monkeypatch, capsys):
    """on_start() should display the greeting when one is configured."""
    inputs = iter(["q"])
    chat = CHAT(echo_agent, greeting="Welcome!")
    monkeypatch.setattr(chat, "get_input", lambda: next(inputs))

    chat.run()

    captured = capsys.readouterr().out
    assert "Welcome!" in captured


def test_no_greeting_by_default(monkeypatch, capsys):
    """When no greeting is set, on_start() should not print anything extra."""
    inputs = iter(["q"])
    chat = CHAT(echo_agent)
    monkeypatch.setattr(chat, "get_input", lambda: next(inputs))

    chat.run()

    captured = capsys.readouterr().out
    # Only the goodbye message should be present
    lines = [l.strip() for l in captured.strip().splitlines() if l.strip()]
    assert lines == ["System: Goodbye!"]


# ---------------------------------------------------------------------------
# Error resilience
# ---------------------------------------------------------------------------

def test_run_continues_after_agent_error(monkeypatch, capsys):
    """If the agent raises, run() should display the error and continue."""
    inputs = iter(["boom", "q"])
    chat = CHAT(broken_agent)
    monkeypatch.setattr(chat, "get_input", lambda: next(inputs))

    chat.run()

    captured = capsys.readouterr().out
    assert "Error: something went wrong" in captured
    assert "Goodbye!" in captured


# ---------------------------------------------------------------------------
# KeyboardInterrupt / EOFError handling
# ---------------------------------------------------------------------------

def test_run_handles_keyboard_interrupt(monkeypatch, capsys):
    """run() should exit gracefully on KeyboardInterrupt."""
    def raise_interrupt():
        raise KeyboardInterrupt

    chat = CHAT(echo_agent)
    monkeypatch.setattr(chat, "get_input", raise_interrupt)

    chat.run()

    captured = capsys.readouterr().out
    assert "Goodbye!" in captured


def test_run_handles_eof(monkeypatch, capsys):
    """run() should exit gracefully on EOFError."""
    def raise_eof():
        raise EOFError

    chat = CHAT(echo_agent)
    monkeypatch.setattr(chat, "get_input", raise_eof)

    chat.run()

    captured = capsys.readouterr().out
    assert "Goodbye!" in captured
