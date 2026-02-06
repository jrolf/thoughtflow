"""
READ action - read file contents from filesystem.

Supports multiple parsing modes: text, json, yaml, lines, bytes.
"""

from __future__ import annotations

import json
import os

from thoughtflow.action import ACTION
from thoughtflow.actions._substitution import substitute


class READ(ACTION):
    """
    An action that reads file contents from the filesystem.
    
    READ supports multiple parsing modes and handles missing files gracefully.
    
    Args:
        name (str): Unique identifier for this action.
        path (str|callable): File path to read. Supports:
            - str: Static path with {variable} placeholders
            - callable: Function (memory) -> str for dynamic paths
        parse (str|callable): How to parse the content:
            - "text": Return as string (default)
            - "json": Parse as JSON
            - "yaml": Parse as YAML (requires PyYAML)
            - "lines": Split into list of lines
            - "bytes": Return raw bytes
            - callable: Custom parser (content, path) -> parsed
        encoding (str): Text encoding (default: "utf-8").
        on_missing (str): Behavior when file doesn't exist:
            - "raise": Raise FileNotFoundError (default)
            - "empty": Return empty string/list/dict
            - "default": Return the 'default' value
        default: Value to return if file missing and on_missing="default".
        store_as (str): Memory variable to store result (default: "{name}_content").
    
    Example:
        >>> from thoughtflow.actions import READ
        >>> from thoughtflow import MEMORY
        
        # Read text file
        >>> read = READ(path="/path/to/file.txt")
        >>> memory = read(MEMORY())
        
        # Read JSON config
        >>> read = READ(
        ...     path="config.json",
        ...     parse="json",
        ...     store_as="config"
        ... )
        
        # Handle missing file gracefully
        >>> read = READ(
        ...     path="optional.txt",
        ...     on_missing="default",
        ...     default=""
        ... )
        
        # Dynamic path from memory
        >>> read = READ(
        ...     path=lambda m: m.get_var("file_path"),
        ...     parse="json"
        ... )
    """
    
    def __init__(
        self,
        name=None,
        path=None,
        parse="text",
        encoding="utf-8",
        on_missing="raise",
        default=None,
        store_as=None,
    ):
        """
        Initialize a READ action.
        
        Args:
            name: Optional name (defaults to "read").
            path: File path to read.
            parse: Parse mode or custom parser.
            encoding: Text encoding.
            on_missing: Behavior for missing files.
            default: Default value for missing files.
            store_as: Memory variable name for result.
        """
        if path is None:
            raise ValueError("READ requires 'path' parameter")
        
        self.path = path
        self.parse = parse
        self.encoding = encoding
        self.on_missing = on_missing
        self.default = default
        
        name = name or "read"
        
        super().__init__(
            name=name,
            fn=self._execute,
            result_key=store_as or "{}_content".format(name),
            description="READ: Read file contents"
        )
    
    def _execute(self, memory, **kwargs):
        """
        Execute the READ action.
        
        Args:
            memory: MEMORY instance.
            **kwargs: Can override 'path', 'parse', 'encoding'.
        
        Returns:
            Parsed file contents.
        
        Raises:
            FileNotFoundError: If file missing and on_missing="raise".
        """
        # Get parameters
        path = kwargs.get('path', self.path)
        parse = kwargs.get('parse', self.parse)
        encoding = kwargs.get('encoding', self.encoding)
        on_missing = kwargs.get('on_missing', self.on_missing)
        default = kwargs.get('default', self.default)
        
        # Resolve path
        path = substitute(path, memory)
        if path is None:
            raise ValueError("READ path cannot be None")
        path = str(path)
        
        # Expand user home directory
        path = os.path.expanduser(path)
        
        # Check if file exists
        if not os.path.exists(path):
            return self._handle_missing(path, on_missing, default, parse)
        
        # Read file
        try:
            if parse == "bytes":
                with open(path, 'rb') as f:
                    content = f.read()
            else:
                with open(path, 'r', encoding=encoding) as f:
                    content = f.read()
        except Exception as e:
            if on_missing in ("empty", "default"):
                return self._handle_missing(path, on_missing, default, parse)
            raise
        
        # Parse content
        return self._parse_content(content, path, parse)
    
    def _handle_missing(self, path, on_missing, default, parse):
        """
        Handle missing file according to on_missing setting.
        
        Args:
            path: The missing file path.
            on_missing: Behavior setting.
            default: Default value.
            parse: Parse mode (for empty value type).
        
        Returns:
            Default/empty value.
        
        Raises:
            FileNotFoundError: If on_missing="raise".
        """
        if on_missing == "raise":
            raise FileNotFoundError("File not found: {}".format(path))
        
        if on_missing == "default":
            return default
        
        # on_missing == "empty"
        if parse == "json":
            return {}
        if parse == "lines":
            return []
        if parse == "bytes":
            return b""
        return ""
    
    def _parse_content(self, content, path, parse):
        """
        Parse file content according to parse mode.
        
        Args:
            content: Raw file content.
            path: File path (for error messages).
            parse: Parse mode.
        
        Returns:
            Parsed content.
        """
        if callable(parse):
            return parse(content, path)
        
        if parse == "text":
            return content
        
        if parse == "bytes":
            return content
        
        if parse == "json":
            return json.loads(content)
        
        if parse == "yaml":
            try:
                import yaml
                return yaml.safe_load(content)
            except ImportError:
                raise ImportError("YAML parsing requires PyYAML: pip install pyyaml")
        
        if parse == "lines":
            return content.splitlines()
        
        # Unknown parse mode, return as-is
        return content
    
    def to_dict(self):
        """
        Serialize READ to dictionary.
        
        Returns:
            dict: Serializable representation.
        """
        base = super().to_dict()
        base["_class"] = "READ"
        base["encoding"] = self.encoding
        base["on_missing"] = self.on_missing
        base["default"] = self.default
        if not callable(self.path):
            base["path"] = self.path
        if not callable(self.parse):
            base["parse"] = self.parse
        return base
    
    @classmethod
    def from_dict(cls, data, **kwargs):
        """
        Reconstruct READ from dictionary.
        
        Args:
            data: Dictionary representation.
            **kwargs: Ignored.
        
        Returns:
            READ: Reconstructed instance.
        """
        read = cls(
            name=data.get("name"),
            path=data.get("path"),
            parse=data.get("parse", "text"),
            encoding=data.get("encoding", "utf-8"),
            on_missing=data.get("on_missing", "raise"),
            default=data.get("default"),
            store_as=data.get("result_key")
        )
        if data.get("id"):
            read.id = data["id"]
        return read
    
    def __repr__(self):
        path = "<callable>" if callable(self.path) else repr(self.path)
        return "READ(name='{}', path={}, parse='{}')".format(
            self.name, path, self.parse if not callable(self.parse) else "<callable>"
        )
    
    def __str__(self):
        if callable(self.path):
            return "READ <dynamic path>"
        return "READ: {}".format(self.path)
