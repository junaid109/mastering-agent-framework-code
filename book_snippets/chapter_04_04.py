# from 03-part-2-core-architecture\chapter-04-tools-and-skills.md:76
web_search_tool = client.get_web_search_tool(
    user_location={"city": "Seattle", "country": "US"},
)
agent = Agent(
    client=client,
    instructions="You are a helpful assistant that can search the web for current information.",
    tools=[web_search_tool],
)
