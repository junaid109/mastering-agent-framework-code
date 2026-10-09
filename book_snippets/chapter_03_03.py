# from 03-part-2-core-architecture\chapter-03-anatomy-of-an-agent.md:49
# Anthropic — python/samples/02-agents/providers/anthropic/anthropic_basic.py
from agent_framework.anthropic import AnthropicClient

agent = Agent(
    client=AnthropicClient(model="claude-sonnet-4-5-20250929"),
    name="WeatherAgent",
    instructions="You are a helpful weather agent.",
    tools=get_weather,
)

# Google Gemini — python/samples/02-agents/providers/gemini/gemini_basic.py
from agent_framework.gemini import GeminiChatClient

agent = Agent(
    client=GeminiChatClient(),
    name="WeatherAgent",
    instructions="You are a helpful weather agent.",
    tools=[get_weather],
)
