# from 02-part-1-foundations\chapter-02-introduction-to-agent-framework.md:70
# pip install agent-framework
# Use `az login` to authenticate with Azure CLI
import asyncio
from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from azure.identity import AzureCliCredential


async def main():
    agent = Agent(
        client=FoundryChatClient(credential=AzureCliCredential()),
        name="HaikuAgent",
        instructions="You are an upbeat assistant that writes beautifully.",
    )
    print(await agent.run("Write a haiku about Microsoft Agent Framework."))

if __name__ == "__main__":
    asyncio.run(main())
