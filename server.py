"""Local MCP tool server (stdio). Nothing hosted, nothing kept after the session ends."""
from mcp.server.mcpserver import MCPServer
from env import Env

server, env = MCPServer("figures"), Env()

@server.tool()
def clean(text: str = "", file: str = "", clipboard: bool = False, as_at: str = "") -> dict:
    """Clean a flowsheet. Text must be provably synthetic; real data via a local file or the clipboard. Real data returns counts, units and reject reasons only."""
    return env.clean(text=text or None, file=file or None, clipboard=clipboard, as_at=as_at or None)

@server.tool()
def rejects(handle: str) -> dict:
    """Rejected lines for a handle: line number, field and reason only."""
    return env.rejects(handle)

@server.tool()
def render(handle: str) -> dict:
    """Render a synthetic handle to figure files and separate legends. Real data is display-only on the ward machine."""
    return env.render(handle)

if __name__ == "__main__":
    server.run()
