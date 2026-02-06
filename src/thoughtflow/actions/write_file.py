"""
WRITE action - write content to a file.

Supports multiple output modes: text, json, yaml, append, bytes.
"""

from __future__ import annotations

import json
import os

from thoughtflow.action import ACTION
from thoughtflow.actions._substitution import substitute


class WRITE(ACTION):
    """
    An action that writes content to a file.
    
    WRITE supports multiple output modes and can create parent directories.
    
    Args:
        name (str): Unique identifier for this action.
        path (str|callable): File path to write. Supports:
            - str: Static path with {variable} placeholders
            - callable: Function (memory) -> str for dynamic paths
        content (any|callable): Content to write. Can be:
            - str: Written as-is
            - dict/list: Serialized based on mode
            - callable: Function (memory) -> content
        mode (str): Write mode:
            - "text": Write as plain text (default)
            - "json": Serialize to JSON
            - "yaml": Serialize to YAML (requires PyYAML)
            - "append": Append to existing file
            - "bytes": Write raw bytes
        encoding (str): Text encoding (default: "utf-8").
        mkdir (bool): Create parent directories if needed (default: True).
        overwrite (bool): Overwrite if file exists (default: True).
        indent (int): JSON indentation (default: 2).
    
    Example:
        >>> from thoughtflow.actions import WRITE
        >>> from thoughtflow import MEMORY
        
        # Write text file
        >>> write = WRITE(
        ...     path="output.txt",
        ...     content="Hello, world!"
        ... )
        >>> memory = write(MEMORY())
        
        # Write JSON from memory variable
        >>> write = WRITE(
        ...     path="results.json",
        ...     content=lambda m: m.get_var("results"),
        ...     mode="json"
        ... )
        
        # Append to log file
        >>> write = WRITE(
        ...     path="agent.log",
        ...     content="{timestamp}: {message}\\n",
        ...     mode="append"
        ... )
        
        # Dynamic path
        >>> write = WRITE(
        ...     path="output_{run_id}.txt",
        ...     content=lambda m: m.get_var("output")
        ... )
    """
    
    def __init__(
        self,
        name=None,
        path=None,
        content=None,
        mode="text",
        encoding="utf-8",
        mkdir=True,
        overwrite=True,
        indent=2,
    ):
        """
        Initialize a WRITE action.
        
        Args:
            name: Optional name (defaults to "write").
            path: File path to write.
            content: Content to write.
            mode: Write mode.
            encoding: Text encoding.
            mkdir: Create parent directories.
            overwrite: Overwrite existing files.
            indent: JSON indentation.
        """
        if path is None:
            raise ValueError("WRITE requires 'path' parameter")
        
        self.path = path
        self.content = content
        self.mode = mode
        self.encoding = encoding
        self.mkdir = mkdir
        self.overwrite = overwrite
        self.indent = indent
        
        super().__init__(
            name=name or "write",
            fn=self._execute,
            description="WRITE: Write content to file"
        )
    
    def _execute(self, memory, **kwargs):
        """
        Execute the WRITE action.
        
        Args:
            memory: MEMORY instance.
            **kwargs: Can override any parameter.
        
        Returns:
            dict: {path: str, bytes_written: int, status: "written"}
        
        Raises:
            FileExistsError: If file exists and overwrite=False.
        """
        # Get parameters
        path = kwargs.get('path', self.path)
        content = kwargs.get('content', self.content)
        mode = kwargs.get('mode', self.mode)
        encoding = kwargs.get('encoding', self.encoding)
        mkdir = kwargs.get('mkdir', self.mkdir)
        overwrite = kwargs.get('overwrite', self.overwrite)
        indent = kwargs.get('indent', self.indent)
        
        # Resolve path
        path = substitute(path, memory)
        if path is None:
            raise ValueError("WRITE path cannot be None")
        path = str(path)
        path = os.path.expanduser(path)
        
        # Resolve content
        content = substitute(content, memory)
        
        # Check if file exists
        if os.path.exists(path) and not overwrite and mode != "append":
            raise FileExistsError("File exists and overwrite=False: {}".format(path))
        
        # Create parent directories
        if mkdir:
            parent = os.path.dirname(path)
            if parent and not os.path.exists(parent):
                os.makedirs(parent, exist_ok=True)
        
        # Prepare content
        write_content, write_mode = self._prepare_content(content, mode, encoding, indent)
        
        # Write file
        if write_mode == "append":
            with open(path, 'a', encoding=encoding) as f:
                f.write(write_content)
                bytes_written = len(write_content.encode(encoding))
        elif write_mode == "bytes":
            with open(path, 'wb') as f:
                f.write(write_content)
                bytes_written = len(write_content)
        else:
            with open(path, 'w', encoding=encoding) as f:
                f.write(write_content)
                bytes_written = len(write_content.encode(encoding))
        
        return {
            "status": "written",
            "path": path,
            "bytes_written": bytes_written,
            "mode": mode
        }
    
    def _prepare_content(self, content, mode, encoding, indent):
        """
        Prepare content for writing based on mode.
        
        Args:
            content: Raw content.
            mode: Write mode.
            encoding: Text encoding.
            indent: JSON indentation.
        
        Returns:
            tuple: (prepared_content, actual_write_mode)
        """
        if mode == "bytes":
            if isinstance(content, bytes):
                return content, "bytes"
            return str(content).encode(encoding), "bytes"
        
        if mode == "json":
            return json.dumps(content, indent=indent, ensure_ascii=False), "text"
        
        if mode == "yaml":
            try:
                import yaml
                return yaml.dump(content, default_flow_style=False, allow_unicode=True), "text"
            except ImportError:
                raise ImportError("YAML writing requires PyYAML: pip install pyyaml")
        
        if mode == "append":
            return str(content) if content is not None else "", "append"
        
        # Default: text
        return str(content) if content is not None else "", "text"
    
    def to_dict(self):
        """
        Serialize WRITE to dictionary.
        
        Returns:
            dict: Serializable representation.
        """
        base = super().to_dict()
        base["_class"] = "WRITE"
        base["mode"] = self.mode
        base["encoding"] = self.encoding
        base["mkdir"] = self.mkdir
        base["overwrite"] = self.overwrite
        base["indent"] = self.indent
        if not callable(self.path):
            base["path"] = self.path
        if not callable(self.content):
            base["content"] = self.content
        return base
    
    @classmethod
    def from_dict(cls, data, **kwargs):
        """
        Reconstruct WRITE from dictionary.
        
        Args:
            data: Dictionary representation.
            **kwargs: Ignored.
        
        Returns:
            WRITE: Reconstructed instance.
        """
        write = cls(
            name=data.get("name"),
            path=data.get("path"),
            content=data.get("content"),
            mode=data.get("mode", "text"),
            encoding=data.get("encoding", "utf-8"),
            mkdir=data.get("mkdir", True),
            overwrite=data.get("overwrite", True),
            indent=data.get("indent", 2)
        )
        if data.get("id"):
            write.id = data["id"]
        return write
    
    def __repr__(self):
        path = "<callable>" if callable(self.path) else repr(self.path)
        return "WRITE(name='{}', path={}, mode='{}')".format(
            self.name, path, self.mode
        )
    
    def __str__(self):
        if callable(self.path):
            return "WRITE <dynamic path>"
        return "WRITE: {}".format(self.path)
