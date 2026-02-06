"""
SAY action - output text to the user.

The primary action for agent-to-user communication.
"""

from __future__ import annotations

from thoughtflow.action import ACTION
from thoughtflow.actions._substitution import substitute


class SAY(ACTION):
    """
    An action that outputs text to the user.
    
    SAY is the primary action for agent-to-user communication. It supports:
    - Console output (print)
    - Memory storage (as assistant message)
    - Custom output handlers
    - Variable substitution in messages
    
    Args:
        name (str): Unique identifier for this action.
        message (str|callable): Text to output. Can be:
            - str: Static text with {variable} placeholders
            - callable: Function (memory) -> str for dynamic content
        channel (str|callable): Output destination:
            - "console": Print to stdout (default)
            - "memory": Add as assistant message to memory
            - callable: Custom handler (text, memory) -> None
        style (str): Optional styling hint ("info", "warning", "error", "success").
    
    Example:
        >>> from thoughtflow.actions import SAY
        >>> from thoughtflow import MEMORY
        
        # Simple output
        >>> say = SAY(message="Hello, world!")
        >>> memory = say(MEMORY())
        Hello, world!
        
        # With variable substitution
        >>> memory = MEMORY()
        >>> memory.set_var("name", "Alice")
        >>> say = SAY(message="Hello, {name}!")
        >>> memory = say(memory)
        Hello, Alice!
        
        # Store in memory instead of printing
        >>> say = SAY(
        ...     message="Task completed successfully",
        ...     channel="memory"
        ... )
        
        # Custom output handler
        >>> say = SAY(
        ...     message="Status update",
        ...     channel=lambda text, mem: websocket.send(text)
        ... )
    """
    
    # Style prefixes for console output
    STYLES = {
        "info": "[INFO] ",
        "warning": "[WARNING] ",
        "error": "[ERROR] ",
        "success": "[SUCCESS] ",
    }
    
    def __init__(self, name=None, message="", channel="console", style=None):
        """
        Initialize a SAY action.
        
        Args:
            name: Optional name (defaults to "say").
            message: Text to output (str or callable).
            channel: Output destination.
            style: Optional style hint.
        """
        self.message = message
        self.channel = channel
        self.style = style
        
        super().__init__(
            name=name or "say",
            fn=self._execute,
            description="SAY: Output message to user"
        )
    
    def _execute(self, memory, **kwargs):
        """
        Execute the SAY action.
        
        Args:
            memory: MEMORY instance.
            **kwargs: Can override 'message', 'channel', 'style'.
        
        Returns:
            dict: {message: str, channel: str, status: "said"}
        """
        # Get parameters (kwargs can override)
        message = kwargs.get('message', self.message)
        channel = kwargs.get('channel', self.channel)
        style = kwargs.get('style', self.style)
        
        # Resolve message
        text = substitute(message, memory)
        if text is None:
            text = ""
        text = str(text)
        
        # Apply style prefix
        if style and style in self.STYLES:
            styled_text = self.STYLES[style] + text
        else:
            styled_text = text
        
        # Output to channel
        channel_name = self._output_to_channel(styled_text, text, channel, memory)
        
        return {
            "status": "said",
            "message": text,
            "channel": channel_name,
            "style": style
        }
    
    def _output_to_channel(self, styled_text, raw_text, channel, memory):
        """
        Output text to the specified channel.
        
        Args:
            styled_text: Text with style prefix.
            raw_text: Raw text without prefix.
            channel: Channel specification.
            memory: MEMORY instance.
        
        Returns:
            str: Channel name for logging.
        """
        if callable(channel):
            # Custom handler
            channel(raw_text, memory)
            return "custom"
        
        if channel == "console":
            print(styled_text)
            return "console"
        
        if channel == "memory":
            # Add as assistant message
            if hasattr(memory, 'add_msg') and callable(getattr(memory, 'add_msg', None)):
                memory.add_msg("assistant", raw_text, channel="api")
            return "memory"
        
        # Unknown channel, default to console
        print(styled_text)
        return "console"
    
    def to_dict(self):
        """
        Serialize SAY to dictionary.
        
        Returns:
            dict: Serializable representation.
        """
        base = super().to_dict()
        base["_class"] = "SAY"
        base["style"] = self.style
        # Only serialize if not callable
        if not callable(self.message):
            base["message"] = self.message
        if not callable(self.channel):
            base["channel"] = self.channel
        return base
    
    @classmethod
    def from_dict(cls, data, **kwargs):
        """
        Reconstruct SAY from dictionary.
        
        Args:
            data: Dictionary representation.
            **kwargs: Ignored.
        
        Returns:
            SAY: Reconstructed instance.
        """
        say = cls(
            name=data.get("name"),
            message=data.get("message", ""),
            channel=data.get("channel", "console"),
            style=data.get("style")
        )
        if data.get("id"):
            say.id = data["id"]
        return say
    
    def __repr__(self):
        msg = "<callable>" if callable(self.message) else repr(self.message[:50] + "..." if len(str(self.message)) > 50 else self.message)
        return "SAY(name='{}', message={}, channel='{}')".format(
            self.name, msg, self.channel if not callable(self.channel) else "<callable>"
        )
    
    def __str__(self):
        if callable(self.message):
            return "SAY <dynamic message>"
        preview = str(self.message)[:50]
        if len(str(self.message)) > 50:
            preview += "..."
        return "SAY: {}".format(preview)
