"""
MCP (Model Context Protocol) client for ThoughtFlow.

Connects to MCP servers and discovers their available tools, returning them
as TOOL instances that integrate seamlessly with the rest of ThoughtFlow.

The MCP protocol uses JSON-RPC 2.0 over two possible transports:
- Stdio: launches the server as a subprocess, communicates via stdin/stdout
- HTTP+SSE: connects to a remote server via HTTP for requests and SSE for responses

This implementation uses only the Python standard library (subprocess, urllib,
json, threading) — no third-party MCP SDK required.
"""

from __future__ import annotations

import json
import os
import subprocess
import urllib.request
import urllib.error

from thoughtflow.tool import TOOL


class MCP:
    """
    Client for connecting to MCP (Model Context Protocol) servers.

    MCP is an industry-standard protocol for discovering and invoking tools
    hosted on external servers. This client connects to an MCP server, lists
    its available tools, and returns them as TOOL instances that can be passed
    directly to an AGENT.

    Supports two transports:
    - **Stdio:** The server is a local command launched as a subprocess.
      Communication happens over stdin/stdout using JSON-RPC 2.0.
    - **HTTP+SSE:** The server is a remote URL. Requests are sent via HTTP
      POST; responses may come via Server-Sent Events.

    The transport is auto-detected from the server argument: if it starts with
    'http://' or 'https://', HTTP+SSE is used; otherwise it is treated as a
    shell command for stdio transport.

    Attributes:
        server (str): The server command or URL.
        transport (str): 'stdio' or 'http'.
        tools (list[TOOL]): Cached tools after list_tools() is called.

    Example:
        >>> # Stdio transport — local MCP server
        >>> with MCP("npx -y @modelcontextprotocol/server-filesystem /tmp") as mcp:
        ...     tools = mcp.list_tools()
        ...     result = mcp.call_tool("read_file", {"path": "/tmp/notes.txt"})

        >>> # HTTP transport — remote MCP server
        >>> with MCP("https://my-mcp-server.example.com/mcp") as mcp:
        ...     tools = mcp.list_tools()
    """

    def __init__(self, server, env=None):
        """
        Initialize an MCP client and connect to the server.

        Args:
            server (str): Either a shell command to launch a local MCP server
                (stdio transport) or an HTTP(S) URL for a remote server.
            env (dict, optional): Additional environment variables to set when
                launching a stdio subprocess. Merged with the current env.
        """
        self.server = server
        self.tools = []
        self._request_id = 0
        self._env = env

        # Auto-detect transport
        if server.startswith("http://") or server.startswith("https://"):
            self.transport = "http"
            self._base_url = server.rstrip("/")
            self._process = None
        else:
            self.transport = "stdio"
            self._base_url = None
            self._process = None
            self._connect_stdio()

    def _connect_stdio(self):
        """
        Launch the MCP server as a subprocess and establish JSON-RPC communication.

        The server is launched with the command from self.server. Communication
        happens via stdin (requests) and stdout (responses). Stderr is captured
        separately to avoid polluting the JSON-RPC stream.
        """
        env = dict(os.environ)
        if self._env:
            env.update(self._env)

        self._process = subprocess.Popen(
            self.server,
            shell=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

        # Send the initialize handshake
        self._jsonrpc_call("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "thoughtflow", "version": "0.1.2"},
        })

        # Send initialized notification (no response expected)
        self._jsonrpc_notify("notifications/initialized", {})

    def _next_id(self):
        """Generate the next JSON-RPC request ID."""
        self._request_id += 1
        return self._request_id

    def _jsonrpc_call(self, method, params=None):
        """
        Send a JSON-RPC 2.0 request and wait for the response.

        Args:
            method (str): The JSON-RPC method name.
            params (dict, optional): Method parameters.

        Returns:
            dict: The 'result' field from the JSON-RPC response.

        Raises:
            RuntimeError: If the response contains an error.
        """
        if self.transport == "stdio":
            return self._stdio_call(method, params)
        else:
            return self._http_call(method, params)

    def _jsonrpc_notify(self, method, params=None):
        """
        Send a JSON-RPC 2.0 notification (no response expected).

        Args:
            method (str): The notification method name.
            params (dict, optional): Notification parameters.
        """
        msg = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if params is not None:
            msg["params"] = params

        if self.transport == "stdio" and self._process and self._process.stdin:
            line = json.dumps(msg) + "\n"
            self._process.stdin.write(line.encode("utf-8"))
            self._process.stdin.flush()

    def _stdio_call(self, method, params=None):
        """
        Send a JSON-RPC call over the stdio transport.

        Writes a JSON-RPC request to the subprocess's stdin, then reads
        lines from stdout until a matching response is found.

        Args:
            method (str): The JSON-RPC method name.
            params (dict, optional): Method parameters.

        Returns:
            dict: The 'result' field from the response.

        Raises:
            RuntimeError: If the server returns an error or the process is dead.
        """
        if not self._process or self._process.poll() is not None:
            raise RuntimeError("MCP stdio process is not running.")

        req_id = self._next_id()
        msg = {
            "jsonrpc": "2.0",
            "method": method,
            "id": req_id,
        }
        if params is not None:
            msg["params"] = params

        line = json.dumps(msg) + "\n"
        self._process.stdin.write(line.encode("utf-8"))
        self._process.stdin.flush()

        # Read lines until we get our response
        while True:
            raw_line = self._process.stdout.readline()
            if not raw_line:
                raise RuntimeError("MCP server closed stdout unexpectedly.")

            raw_line = raw_line.decode("utf-8").strip()
            if not raw_line:
                continue

            try:
                response = json.loads(raw_line)
            except json.JSONDecodeError:
                continue

            # Skip notifications (no 'id' field)
            if "id" not in response:
                continue

            if response.get("id") == req_id:
                if "error" in response:
                    err = response["error"]
                    raise RuntimeError("MCP error: {} ({})".format(
                        err.get("message", "Unknown"), err.get("code", "?")
                    ))
                return response.get("result", {})

    def _http_call(self, method, params=None):
        """
        Send a JSON-RPC call over the HTTP transport.

        Posts a JSON-RPC request to the server's HTTP endpoint and parses
        the JSON response.

        Args:
            method (str): The JSON-RPC method name.
            params (dict, optional): Method parameters.

        Returns:
            dict: The 'result' field from the response.

        Raises:
            RuntimeError: If the server returns an error.
        """
        req_id = self._next_id()
        msg = {
            "jsonrpc": "2.0",
            "method": method,
            "id": req_id,
        }
        if params is not None:
            msg["params"] = params

        data = json.dumps(msg).encode("utf-8")
        headers = {"Content-Type": "application/json"}

        req = urllib.request.Request(self._base_url, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req) as resp:
                body = resp.read().decode("utf-8")
                response = json.loads(body)
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            raise RuntimeError("MCP HTTP error {}: {}".format(e.code, error_body))
        except Exception as e:
            raise RuntimeError("MCP HTTP request failed: {}".format(e))

        if "error" in response:
            err = response["error"]
            raise RuntimeError("MCP error: {} ({})".format(
                err.get("message", "Unknown"), err.get("code", "?")
            ))
        return response.get("result", {})

    def list_tools(self):
        """
        Discover available tools from the MCP server.

        Sends a 'tools/list' JSON-RPC call and converts each tool definition
        into a ThoughtFlow TOOL instance. Results are cached in self.tools.

        Returns:
            list[TOOL]: The tools available on this MCP server.

        Example:
            >>> mcp = MCP("npx -y @modelcontextprotocol/server-filesystem /tmp")
            >>> tools = mcp.list_tools()
            >>> for t in tools:
            ...     print(t.name, t.description)
        """
        result = self._jsonrpc_call("tools/list", {})
        raw_tools = result.get("tools", [])

        self.tools = []
        for raw in raw_tools:
            name = raw.get("name", "")
            description = raw.get("description", "")
            input_schema = raw.get("inputSchema", {"type": "object", "properties": {}})

            # Create a TOOL whose fn calls back to this MCP server
            tool = TOOL(
                name=name,
                description=description,
                parameters=input_schema,
                fn=self._make_tool_caller(name),
            )
            self.tools.append(tool)

        return list(self.tools)

    def _make_tool_caller(self, tool_name):
        """
        Create a callable that invokes a tool on this MCP server.

        Returns a function that, when called with keyword arguments, sends
        a 'tools/call' JSON-RPC request to the server.

        Args:
            tool_name (str): The name of the tool to invoke.

        Returns:
            callable: A function(**kwargs) that calls the MCP tool.
        """
        def call_tool(**kwargs):
            """Call an MCP tool with the given arguments."""
            return self.call_tool(tool_name, kwargs)

        call_tool.__name__ = tool_name
        call_tool.__qualname__ = "MCP.{}".format(tool_name)
        return call_tool

    def call_tool(self, name, arguments=None):
        """
        Invoke a specific tool on the MCP server by name.

        Args:
            name (str): The tool name to call.
            arguments (dict, optional): Arguments to pass to the tool.

        Returns:
            The tool's result. For text content, returns the text string.
            For other content types, returns the raw content list.

        Example:
            >>> result = mcp.call_tool("read_file", {"path": "/tmp/test.txt"})
        """
        result = self._jsonrpc_call("tools/call", {
            "name": name,
            "arguments": arguments or {},
        })

        # MCP tool results come as {"content": [{"type": "text", "text": "..."}]}
        content = result.get("content", [])
        if len(content) == 1 and content[0].get("type") == "text":
            return content[0].get("text", "")
        return content

    def list_resources(self):
        """
        List available resources from the MCP server.

        Returns:
            list[dict]: Resource definitions from the server, each containing
                'uri', 'name', and optionally 'description' and 'mimeType'.
        """
        result = self._jsonrpc_call("resources/list", {})
        return result.get("resources", [])

    def read_resource(self, uri):
        """
        Read a specific resource from the MCP server.

        Args:
            uri (str): The URI of the resource to read.

        Returns:
            str or bytes: The resource content. Text resources return a string;
                binary resources return bytes.
        """
        result = self._jsonrpc_call("resources/read", {"uri": uri})
        contents = result.get("contents", [])
        if contents:
            first = contents[0]
            if "text" in first:
                return first["text"]
            if "blob" in first:
                import base64
                return base64.b64decode(first["blob"])
        return ""

    def close(self):
        """
        Shut down the MCP connection.

        For stdio transport, terminates the subprocess. For HTTP transport,
        this is a no-op (HTTP is stateless).
        """
        if self._process:
            try:
                self._process.stdin.close()
            except Exception:
                pass
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
            self._process = None

    def __enter__(self):
        """Support context manager usage: with MCP(...) as mcp:"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up on context manager exit."""
        self.close()
        return False

    def __str__(self):
        """Return a concise string representation."""
        tool_count = len(self.tools)
        return "MCP({}, transport={}, tools={})".format(
            self.server[:40], self.transport, tool_count
        )

    def __repr__(self):
        """Return a detailed string representation."""
        return "MCP(server='{}', transport='{}', tools={})".format(
            self.server, self.transport, len(self.tools)
        )
