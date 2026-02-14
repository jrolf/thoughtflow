"""
CHAT class for ThoughtFlow.

Provides an interactive chat loop for testing agents and agentic flows
locally in a terminal or Jupyter notebook.

The CHAT class wraps any callable that follows the Thoughtflow contract
(takes a MEMORY, returns a MEMORY) and provides a simple text-based
input/output loop around it.

Example:
    >>> from thoughtflow import LLM, THOUGHT, CHAT, MEMORY
    >>>
    >>> llm = LLM("openai:gpt-4o", key="your-api-key")
    >>> responder = THOUGHT(
    ...     name="respond",
    ...     llm=llm,
    ...     prompt="You are a helpful assistant. Respond to: {last_user_msg}"
    ... )
    >>> chat = CHAT(responder)
    >>> chat.run()  # starts interactive loop (type 'q' or 'quit' to exit)

    # Or use turn() for programmatic / cell-by-cell interaction:
    >>> chat = CHAT(responder)
    >>> response = chat.turn("Hello!")
"""

from __future__ import annotations

from thoughtflow.memory import MEMORY


# Built-in exit commands that are always active and cannot be removed.
_BUILTIN_EXIT_COMMANDS = frozenset({"q", "quit"})


class CHAT:
    """
    Interactive chat session with a Thoughtflow agent.

    Wraps any callable that follows the Thoughtflow contract — accepts a
    MEMORY and returns a MEMORY — and provides a text-based input/output
    loop for testing agent behavior locally in a terminal or Jupyter notebook.

    The class is designed with extensibility in mind.  Subclasses can override
    ``get_input()`` and ``display()`` to swap the I/O backend (e.g. a web UI)
    while reusing all agent / memory interaction logic.

    Args:
        agent (callable): Any callable with signature ``fn(memory) -> memory``.
            A THOUGHT, ACTION, or plain function all work.
        memory (MEMORY, optional): Existing memory to continue a conversation.
            Defaults to a fresh ``MEMORY()`` instance.
        greeting (str, optional): A message displayed when ``run()`` starts.
        exit_commands (set, optional): Additional exit words beyond the
            built-in ``"q"`` and ``"quit"`` (which are always active).
        channel (str): Channel tag for user messages added to memory.
            Defaults to ``"cli"``.  Must be a channel recognised by MEMORY
            (e.g. ``"cli"``, ``"webapp"``, ``"api"``).
        user_label (str): Label shown before the user's input prompt.
            Defaults to ``"You"``.
        agent_label (str): Label shown before the agent's responses.
            Defaults to ``"Agent"``.
        response_extractor (callable, optional): A function
            ``fn(memory) -> str`` that pulls the agent's reply from memory
            after each turn.  When omitted, CHAT automatically finds the
            new assistant message added during the turn.

    Attributes:
        history (list): List of ``(user_text, agent_text)`` tuples recorded
            across all calls to ``turn()``.

    Example — interactive loop::

        from thoughtflow import LLM, THOUGHT, CHAT

        llm = LLM("openai:gpt-4o", key="...")
        responder = THOUGHT(
            name="respond",
            llm=llm,
            prompt="You are a helpful assistant. Respond to: {last_user_msg}"
        )
        chat = CHAT(responder, greeting="Hello! Type 'q' to quit.", channel="cli")
        chat.run()

    Example — programmatic / Jupyter cell-by-cell::

        chat = CHAT(my_agent)
        chat.turn("What is ThoughtFlow?")
        chat.turn("Tell me more about MEMORY.")
        print(chat.history)   # inspect past turns
        print(chat.memory)    # inspect full memory state
    """

    def __init__(
        self,
        agent,
        memory=None,
        greeting=None,
        exit_commands=None,
        channel="cli",
        user_label="You",
        agent_label="Agent",
        response_extractor=None,
    ):
        """
        Initialise a CHAT session.

        Args:
            agent: Callable with signature ``fn(memory) -> memory``.
            memory: Optional MEMORY instance.  A fresh one is created if omitted.
            greeting: Optional text displayed at the start of ``run()``.
            exit_commands: Optional set of additional exit words (case-insensitive).
                ``"q"`` and ``"quit"`` are always active regardless of this parameter.
            channel: Channel tag written to memory for user messages.
            user_label: Prompt label for the user.
            agent_label: Display label for agent responses.
            response_extractor: Optional ``fn(memory) -> str`` override.
        """
        self.agent = agent
        self.memory = memory if memory is not None else MEMORY()
        self.greeting = greeting
        self.channel = channel
        self.user_label = user_label
        self.agent_label = agent_label
        self._custom_extractor = response_extractor
        self.history = []

        # Merge user-supplied exit commands with the built-in ones.
        extra = set(exit_commands) if exit_commands else set()
        self.exit_commands = _BUILTIN_EXIT_COMMANDS | extra

    # ------------------------------------------------------------------
    # I/O methods — override these in subclasses for different backends
    # ------------------------------------------------------------------

    def get_input(self):
        """
        Prompt the user for a line of text and return it.

        Override this method in a subclass to change the input mechanism
        (e.g. read from a web socket or a Jupyter widget).

        Returns:
            str: The raw text entered by the user.
        """
        return input(self.user_label + ": ")

    def display(self, text, role="assistant"):
        """
        Display a message to the user.

        Override this method in a subclass to change the output mechanism
        (e.g. render HTML or send over a web socket).

        Args:
            text: The message string to display.
            role: Semantic role of the message (``"assistant"``, ``"system"``,
                ``"error"``).  The base implementation ignores this, but
                subclasses may use it for styling.
        """
        label = self.agent_label if role == "assistant" else role.capitalize()
        print("\n{}: {}\n".format(label, text))

    # ------------------------------------------------------------------
    # Hooks
    # ------------------------------------------------------------------

    def on_start(self):
        """
        Called at the beginning of ``run()`` before entering the loop.

        Displays the greeting if one was provided.
        """
        if self.greeting:
            self.display(self.greeting, role="system")

    def on_end(self):
        """
        Called when the interactive loop exits (exit command or interrupt).
        """
        self.display("Goodbye!", role="system")

    # ------------------------------------------------------------------
    # Core logic
    # ------------------------------------------------------------------

    def _extract_response(self, stamps_before):
        """
        Find the agent's response after a turn.

        If a custom ``response_extractor`` was provided, it is always used.
        Otherwise the method diffs the event stamps from before and after
        the agent call to reliably locate the new assistant message, even
        when multiple events share the same sub-millisecond timestamp.

        Falls back to ``memory.last_asst_msg()`` if no new assistant
        message is found via the diff (e.g. the agent stored its reply
        only as a variable).

        Args:
            stamps_before: Set of event stamps that existed before the
                agent was called.

        Returns:
            str or None: The agent's response text.
        """
        # Custom extractor always wins.
        if self._custom_extractor:
            return self._custom_extractor(self.memory)

        # Default: find new assistant messages by diffing event stamps.
        new_stamps = set(self.memory.events.keys()) - stamps_before
        for stamp in new_stamps:
            event = self.memory.events[stamp]
            if event.get("type") == "msg" and event.get("role") == "assistant":
                return event["content"]

        # Fallback if the agent didn't add an explicit assistant message.
        return self.memory.last_asst_msg(content_only=True)

    def turn(self, user_input):
        """
        Execute a single conversational turn.

        Adds the user's message to memory, invokes the agent, extracts
        the agent's response, and records the exchange in ``self.history``.

        This method can be called directly for programmatic or
        cell-by-cell Jupyter interaction without entering the ``run()`` loop.

        Args:
            user_input (str): The text the user submitted.

        Returns:
            str or None: The agent's response text.
        """
        self.memory.add_msg("user", user_input, channel=self.channel)

        # Snapshot stamps so we can reliably find new messages after the call.
        stamps_before = set(self.memory.events.keys())

        self.memory = self.agent(self.memory)

        response = self._extract_response(stamps_before)
        self.history.append((user_input, response))
        return response

    def run(self):
        """
        Run the interactive chat loop.

        Repeatedly prompts the user for input, passes it through ``turn()``,
        and displays the agent's response.  The loop exits when the user
        types an exit command (``"q"`` or ``"quit"`` by default) or sends
        a keyboard interrupt (Ctrl-C / EOFError).

        Exceptions raised by the agent are caught and displayed as errors
        so the session can continue.
        """
        self.on_start()

        while True:
            # --- get user input ---
            try:
                user_input = self.get_input()
            except (EOFError, KeyboardInterrupt):
                break

            # --- check for exit ---
            if user_input is None:
                break
            stripped = user_input.strip().lower()
            if stripped in self.exit_commands:
                break

            # --- run one turn, resilient to agent errors ---
            try:
                response = self.turn(user_input)
                if response:
                    self.display(response)
                else:
                    self.display("(no response)")
            except Exception as exc:
                self.display("Error: {}".format(exc), role="error")

        self.on_end()


__all__ = [
    "CHAT",
]
