from mcp.server.mcpserver import MCPServer

mcp = MCPServer("trend-detective")


@mcp.tool()
def ping() -> str:
    """Health check. Returns 'pong' when the Trend Detective MCP server is reachable."""
    return "pong"


def main() -> None:
    # stdio transport, for Claude Desktop / Claude Code: `uv run trend-detective-mcp`
    mcp.run()
