# from 08-part-7-real-systems\chapter-17-production-readiness.md:77
tools=MCPStreamableHTTPTool(
    name="MCP tool",
    description="MCP tool description.",
    url="<your authenticated server url>",
    header_provider=lambda _: {"Authorization": f"Bearer {api_key}"},
)
