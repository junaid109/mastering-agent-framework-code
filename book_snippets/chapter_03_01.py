# from 03-part-2-core-architecture\chapter-03-anatomy-of-an-agent.md:11
from agent_framework import Agent, tool
from agent_framework.openai import OpenAIChatClient

agent = Agent(
    client=OpenAIChatClient(
        model="gpt-5.4-nano",
        api_key=os.getenv("OPENAI_API_KEY"),
    ),
    name="WeatherAgent",
    instructions="You are a helpful weather agent.",
    tools=get_weather,
)
