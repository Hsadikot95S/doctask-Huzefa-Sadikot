from mcp.server.fastmcp import FastMCP

from apps.mcp.tools import register_tools


mcp = FastMCP(
    name="SuperDocs",
    instructions=(
        "Machine interface for the SuperDocs durable "
        "document-analysis workflow."
    ),
)


register_tools(mcp)


if __name__ == "__main__":
    mcp.run()
