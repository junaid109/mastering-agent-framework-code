"""Ch 2.4: hello agent + streaming (book snippets chapter_02_01/02)."""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root, for support.fake_client

from agent_framework import Agent
from support.fake_client import Reply, ScriptedChatClient


def make_client(script):
    """Offline ScriptedChatClient by default; set BOOK_CLIENT=openai-compatible for a real endpoint."""
    if os.environ.get("BOOK_CLIENT") == "openai-compatible":
        from agent_framework.openai import OpenAIChatCompletionClient

        return OpenAIChatCompletionClient(
            base_url=os.environ["BOOK_BASE_URL"],
            api_key=os.environ.get("BOOK_API_KEY", "not-needed"),
            model=os.environ["BOOK_MODEL"],
        )
    return ScriptedChatClient(script)


async def main():
    agent = Agent(
        client=make_client([
            Reply.text("Agents wake at dawn / tools hum, graphs align / hello, framework"),
            Reply.text("Octopuses have three hearts."),
        ]),
        name="HaikuAgent",
        instructions="You are an upbeat assistant that writes beautifully.",
    )
    print(await agent.run("Write a haiku about Microsoft Agent Framework."))
    async for chunk in agent.run("Tell me a one-sentence fun fact.", stream=True):
        if chunk.text:
            print(chunk.text, end="", flush=True)
    print()


if __name__ == "__main__":
    asyncio.run(main())
