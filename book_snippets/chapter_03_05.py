# from 03-part-2-core-architecture\chapter-03-anatomy-of-an-agent.md:120
agent = Agent(
    client=OpenAIChatClient(),
    instructions="You are a helpful weather agent.",
    tools=get_weather,
)

session = agent.create_session()

result1 = await agent.run("What's the weather like in Tokyo?", session=session)
result2 = await agent.run("How about London?", session=session)
result3 = await agent.run(
    "Which of the cities I asked about has better weather?", session=session
)
