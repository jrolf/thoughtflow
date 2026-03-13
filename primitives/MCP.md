# MCP

> Model Context Protocol client for tool discovery and invocation.

## Philosophy

MCP exists because tool discovery and invocation should not be tied to a single implementation. The Model Context Protocol is an industry-standard way for clients to connect to servers that expose tools, resources, and prompts. By implementing an MCP client, ThoughtFlow can consume any MCP-compliant server without custom adapters. A filesystem server, a database server, or a custom API server all expose the same interface: list tools, call tools, list resources, read resources.

The design choice to return TOOL instances is deliberate. MCP tools are not a different kind of thing; they are TOOLs whose execution function happens to call back to the MCP server. This keeps the agent loop uniform: it receives a list of TOOLs from various sources (hand-built, from_action, from MCP) and treats them identically. Zero dependencies (subprocess, urllib, json) keeps the implementation lightweight and deployable in constrained environments.

## How It Works

MCP auto-detects transport from the server argument. URLs starting with `http://` or `https://` use HTTP transport: JSON-RPC requests are sent via POST to the base URL. Everything else is treated as a stdio command: the server is launched as a subprocess, and JSON-RPC flows over stdin/stdout. For stdio, the client sends an `initialize` handshake, then `notifications/initialized`, before any other calls.

`list_tools()` sends `tools/list` and converts each returned tool into a TOOL. Each TOOL's `fn` is a closure that calls `call_tool(name, kwargs)` on this MCP instance. When the agent invokes the tool, the closure triggers a `tools/call` JSON-RPC request. The response is unwrapped: a single text content item returns the text string; otherwise the raw content list is returned.

`list_resources()` and `read_resource(uri)` support the resources protocol. Context manager support (`with MCP(...) as mcp`) ensures the stdio subprocess is terminated on exit. The `env` parameter merges additional environment variables into the subprocess environment for stdio transport.

## Inputs & Configuration

| Parameter | Description |
|-----------|-------------|
| server | Shell command for stdio transport (e.g., `npx -y @modelcontextprotocol/server-filesystem /tmp`) or HTTP(S) URL for remote server. |
| env | Optional dict of environment variables to merge when launching stdio subprocess. |

## Usage

```python
from thoughtflow import MCP

# Stdio transport — local MCP server
with MCP("npx -y @modelcontextprotocol/server-filesystem /tmp") as mcp:
    tools = mcp.list_tools()
    for t in tools:
        print(t.name, t.description)
    result = mcp.call_tool("read_file", {"path": "/tmp/notes.txt"})
```

```python
# HTTP transport — remote MCP server
with MCP("https://my-mcp-server.example.com/mcp") as mcp:
    tools = mcp.list_tools()
    result = mcp.call_tool("query_database", {"sql": "SELECT 1"})
```

## Relationship to Other Primitives

MCP produces TOOL instances. AGENT accepts a list of tools; MCP tools can be merged with hand-built tools or tools from `from_action()`. The agent loop does not distinguish between them. MCP depends on TOOL for the schema and callable interface. It does not depend on LLM, MEMORY, THOUGHT, or ACTION. WORKFLOW and CHAT may pass MCP tools to an AGENT when the workflow needs access to external capabilities (filesystem, database, APIs) exposed via MCP servers.

## Considerations for Future Development

- Add HTTP+SSE transport if the MCP spec evolves to require it for long-running or streaming responses.
- Support `prompts/list` and `prompts/get` for prompt templates if the protocol standardizes them.
- Consider connection pooling or keep-alive for HTTP transport when making many calls.
- Document recommended patterns for running MCP servers in production (process supervision, timeouts, health checks).
