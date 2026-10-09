"""Ch 3.3: sessions, serialization round-trip, custom HistoryProvider (chapter_03_05/06)."""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_framework import Agent, AgentSession, HistoryProvider, Message, tool
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


@tool(approval_mode="never_require")
def get_weather(location: str) -> str:
    """Get the weather for a given location."""
    return f"Sunny in {location}"


class CustomHistoryProvider(HistoryProvider):
    def __init__(self) -> None:
        super().__init__("custom-history")
        self._storage: dict[str, list[Message]] = {}

    async def get_messages(self, session_id, *, state=None, **kwargs) -> list[Message]:
        return list(self._storage.get(session_id or "default", []))

    async def save_messages(self, session_id, messages, *, state=None, **kwargs) -> None:
        self._storage.setdefault(session_id or "default", []).extend(messages)


async def main():
    provider = CustomHistoryProvider()
    agent = Agent(
        client=make_client([
            Reply.tool_call("get_weather", {"location": "Tokyo"}), Reply.text("Tokyo is sunny."),
            Reply.tool_call("get_weather", {"location": "London"}), Reply.text("London is sunny."),
            Reply.text("Both are sunny; it is a tie."),
        ]),
        instructions="You are a helpful weather agent.",
        tools=get_weather,
        context_providers=[provider],
    )
    session = agent.create_session()
    for q in ["What's the weather like in Tokyo?", "How about London?",
              "Which of the cities I asked about has better weather?"]:
        print(q, "->", (await agent.run(q, session=session)).text)

    # persist the session itself and resume it
    saved = json.dumps(session.to_dict())
    restored = AgentSession.from_dict(json.loads(saved))
    print("restored same session:", restored.session_id == session.session_id)
    print("messages stored by provider:", len(provider._storage[session.session_id]))


if __name__ == "__main__":
    asyncio.run(main())
