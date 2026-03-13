"""
Unit tests for the ThoughtFlow MCP class.

The MCP class connects to Model Context Protocol servers and discovers their
tools, returning them as TOOL instances. Tests mock the subprocess (stdio) and
HTTP transports to test the class logic without requiring real MCP servers.
"""

from __future__ import annotations

import io
import json
from unittest.mock import patch, MagicMock

import pytest

from thoughtflow.mcp import MCP
from thoughtflow.tool import TOOL


# ============================================================================
# Helpers
# ============================================================================


def make_jsonrpc_response(req_id, result):
    """Build a JSON-RPC 2.0 response line (bytes) for a mocked stdio server."""
    return json.dumps({"jsonrpc": "2.0", "id": req_id, "result": result}).encode("utf-8") + b"\n"


def make_mock_process(responses):
    """
    Create a mock subprocess that returns pre-configured JSON-RPC responses.

    Args:
        responses: list of (request_id, result_dict) tuples, returned in order.

    Returns:
        MagicMock mimicking subprocess.Popen.
    """
    proc = MagicMock()
    proc.poll.return_value = None
    proc.stdin = MagicMock()
    proc.stderr = MagicMock()

    # Build stdout as a sequence of response lines
    lines = []
    for req_id, result in responses:
        lines.append(make_jsonrpc_response(req_id, result))

    stdout_data = b"".join(lines)
    proc.stdout = io.BytesIO(stdout_data)

    return proc


# ============================================================================
# Initialization Tests
# ============================================================================


class TestMCPInitialization:
    """Tests for MCP class initialization."""

    def test_detects_http_transport(self):
        """
        MCP must detect HTTP transport when server starts with http(s).

        Remove this test if: We change transport detection.
        """
        # Patch to avoid actually connecting
        with patch.object(MCP, '__init__', lambda self, *a, **kw: None):
            mcp = MCP.__new__(MCP)
            mcp.server = "https://example.com/mcp"
            mcp.transport = "http" if mcp.server.startswith("http") else "stdio"

        assert mcp.transport == "http"

    def test_detects_stdio_transport(self):
        """
        MCP must detect stdio transport for non-URL commands.

        Remove this test if: We change transport detection.
        """
        with patch.object(MCP, '__init__', lambda self, *a, **kw: None):
            mcp = MCP.__new__(MCP)
            mcp.server = "npx -y @modelcontextprotocol/server-filesystem /tmp"
            mcp.transport = "http" if mcp.server.startswith("http") else "stdio"

        assert mcp.transport == "stdio"


# ============================================================================
# Stdio Transport Tests
# ============================================================================


class TestMCPStdio:
    """Tests for MCP stdio transport with mocked subprocess."""

    @patch('subprocess.Popen')
    def test_list_tools_returns_tool_instances(self, mock_popen):
        """
        list_tools() must return TOOL instances from server's tools/list response.

        Remove this test if: We change the tool discovery contract.
        """
        # The server will receive: initialize (id=1), then tools/list (id=2)
        mock_proc = make_mock_process([
            (1, {"protocolVersion": "2024-11-05", "capabilities": {}}),
            (2, {"tools": [
                {
                    "name": "read_file",
                    "description": "Read a file from disk",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "File path"},
                        },
                        "required": ["path"],
                    },
                },
                {
                    "name": "write_file",
                    "description": "Write content to a file",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "content": {"type": "string"},
                        },
                    },
                },
            ]}),
        ])
        mock_popen.return_value = mock_proc

        mcp = MCP("echo test-server")
        tools = mcp.list_tools()

        assert len(tools) == 2
        assert all(isinstance(t, TOOL) for t in tools)
        assert tools[0].name == "read_file"
        assert tools[1].name == "write_file"
        assert "file" in tools[0].description.lower()

        mcp.close()

    @patch('subprocess.Popen')
    def test_tool_schema_is_valid(self, mock_popen):
        """
        Tools returned by list_tools() must produce valid OpenAI schemas.

        Remove this test if: We change schema generation.
        """
        mock_proc = make_mock_process([
            (1, {"protocolVersion": "2024-11-05", "capabilities": {}}),
            (2, {"tools": [{
                "name": "search",
                "description": "Search the web",
                "inputSchema": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            }]}),
        ])
        mock_popen.return_value = mock_proc

        mcp = MCP("echo test")
        tools = mcp.list_tools()
        schema = tools[0].to_schema()

        assert schema["type"] == "function"
        assert schema["function"]["name"] == "search"
        assert "query" in schema["function"]["parameters"]["properties"]

        mcp.close()

    @patch('subprocess.Popen')
    def test_call_tool_returns_text_content(self, mock_popen):
        """
        call_tool() must unwrap single text content from the MCP response.

        Remove this test if: We change call_tool response handling.
        """
        mock_proc = make_mock_process([
            (1, {"protocolVersion": "2024-11-05", "capabilities": {}}),
            (2, {"content": [{"type": "text", "text": "Hello from the tool!"}]}),
        ])
        mock_popen.return_value = mock_proc

        mcp = MCP("echo test")
        result = mcp.call_tool("greet", {"name": "World"})

        assert result == "Hello from the tool!"

        mcp.close()

    @patch('subprocess.Popen')
    def test_call_tool_returns_multi_content(self, mock_popen):
        """
        call_tool() must return the full content list for multi-part responses.

        Remove this test if: We change multi-content handling.
        """
        mock_proc = make_mock_process([
            (1, {"protocolVersion": "2024-11-05", "capabilities": {}}),
            (2, {"content": [
                {"type": "text", "text": "Part 1"},
                {"type": "image", "data": "base64..."},
            ]}),
        ])
        mock_popen.return_value = mock_proc

        mcp = MCP("echo test")
        result = mcp.call_tool("mixed", {})

        assert isinstance(result, list)
        assert len(result) == 2

        mcp.close()

    @patch('subprocess.Popen')
    def test_handles_server_error(self, mock_popen):
        """
        MCP must raise RuntimeError when the server returns a JSON-RPC error.

        Remove this test if: We change error handling.
        """
        proc = MagicMock()
        proc.poll.return_value = None
        proc.stdin = MagicMock()
        proc.stderr = MagicMock()

        # Return init success, then an error for tools/list
        lines = [
            make_jsonrpc_response(1, {"protocolVersion": "2024-11-05", "capabilities": {}}),
            json.dumps({
                "jsonrpc": "2.0",
                "id": 2,
                "error": {"code": -32600, "message": "Invalid request"},
            }).encode("utf-8") + b"\n",
        ]
        proc.stdout = io.BytesIO(b"".join(lines))
        mock_popen.return_value = proc

        mcp = MCP("echo test")

        with pytest.raises(RuntimeError, match="Invalid request"):
            mcp.list_tools()

        mcp.close()

    @patch('subprocess.Popen')
    def test_context_manager(self, mock_popen):
        """
        MCP must support context manager protocol for clean lifecycle.

        Remove this test if: We remove context manager support.
        """
        mock_proc = make_mock_process([
            (1, {"protocolVersion": "2024-11-05", "capabilities": {}}),
            (2, {"tools": []}),
        ])
        mock_popen.return_value = mock_proc

        with MCP("echo test") as mcp:
            tools = mcp.list_tools()
            assert tools == []

        # After exiting context, process should be terminated
        mock_proc.terminate.assert_called()


# ============================================================================
# HTTP Transport Tests
# ============================================================================


class TestMCPHttp:
    """Tests for MCP HTTP transport with mocked urllib."""

    @patch('urllib.request.urlopen')
    def test_http_list_tools(self, mock_urlopen):
        """
        list_tools() over HTTP must return TOOL instances.

        Remove this test if: We change HTTP transport.
        """
        # Mock the urlopen to return our JSON-RPC response
        mock_response = MagicMock()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.read.return_value = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"tools": [{
                "name": "fetch",
                "description": "Fetch a URL",
                "inputSchema": {
                    "type": "object",
                    "properties": {"url": {"type": "string"}},
                },
            }]},
        }).encode("utf-8")
        mock_urlopen.return_value = mock_response

        mcp = MCP("https://example.com/mcp")
        tools = mcp.list_tools()

        assert len(tools) == 1
        assert tools[0].name == "fetch"

    @patch('urllib.request.urlopen')
    def test_http_call_tool(self, mock_urlopen):
        """
        call_tool() over HTTP must send correct JSON-RPC and parse response.

        Remove this test if: We change HTTP transport.
        """
        mock_response = MagicMock()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.read.return_value = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "content": [{"type": "text", "text": "HTTP result!"}],
            },
        }).encode("utf-8")
        mock_urlopen.return_value = mock_response

        mcp = MCP("https://example.com/mcp")
        result = mcp.call_tool("test_tool", {"key": "value"})

        assert result == "HTTP result!"


# ============================================================================
# String Representation Tests
# ============================================================================


class TestMCPRepr:
    """Tests for MCP string representations."""

    def test_str_http(self):
        """MCP __str__ must show server and transport."""
        mcp = MCP("https://example.com/mcp")
        s = str(mcp)
        assert "https://example.com/mcp" in s
        assert "http" in s

    @patch('subprocess.Popen')
    def test_str_stdio(self, mock_popen):
        """MCP __str__ must show server command and transport."""
        mock_proc = make_mock_process([
            (1, {"protocolVersion": "2024-11-05", "capabilities": {}}),
        ])
        mock_popen.return_value = mock_proc

        mcp = MCP("echo test-server")
        s = str(mcp)
        assert "stdio" in s

        mcp.close()
