# from 09-back-matter\appendix-a-migration-guides.md:9
# Semantic Kernel
from semantic_kernel.agents import ChatCompletionAgent
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion

agent = ChatCompletionAgent(
    service=OpenAIChatCompletion(),
    name="Support",
    instructions="Answer in one sentence.",
)
response = await agent.get_response(messages="How do I reset my bike tire?")
print(response.message.content)

# Agent Framework
from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient

chat_agent = Agent(
    client=OpenAIChatClient(),
    name="Support",
    instructions="Answer in one sentence.",
)
reply = await chat_agent.run("How do I reset my bike tire?")
print(reply.text)
