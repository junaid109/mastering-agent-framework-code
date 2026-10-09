# from 03-part-2-core-architecture\chapter-04-tools-and-skills.md:38
client = OpenAIChatClient()
agent = Agent(
    client=client,
    instructions="You are a helpful assistant that can write and execute Python code to solve problems.",
    tools=client.get_code_interpreter_tool(),
)

result = await agent.run("Use code to get the factorial of 100?")
