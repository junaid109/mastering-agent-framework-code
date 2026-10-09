# from 03-part-2-core-architecture\chapter-04-tools-and-skills.md:93
github_mcp_tool = client.get_mcp_tool(
    name="GitHub",
    url="https://api.githubcopilot.com/mcp/",
    headers={"Authorization": f"Bearer {github_pat}"},
    approval_mode="never_require",
)
