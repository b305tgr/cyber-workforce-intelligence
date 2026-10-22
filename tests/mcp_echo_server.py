from mcp.server import MCPServer

server = MCPServer("Echo test server")


@server.tool()
def echo_text(text: str) -> str:
    """Return the supplied text for MCP integration tests."""
    return f"echo: {text}"


if __name__ == "__main__":
    server.run()
