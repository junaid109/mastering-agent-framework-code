# from 03-part-2-core-architecture\chapter-03-anatomy-of-an-agent.md:140
from agent_framework import Agent, AgentSession, HistoryProvider, Message

class CustomHistoryProvider(HistoryProvider):
    def __init__(self) -> None:
        super().__init__("custom-history")
        self._storage: dict[str, list[Message]] = {}

    async def get_messages(self, session_id, *, state=None, **kwargs) -> list[Message]:
        return list(self._storage.get(session_id or "default", []))

    async def save_messages(self, session_id, messages, *, state=None, **kwargs) -> None:
        key = session_id or "default"
        self._storage.setdefault(key, []).extend(messages)

agent = Agent(
    client=OpenAIChatClient(),
    instructions="You are a helpful assistant that remembers our conversation.",
    context_providers=[CustomHistoryProvider()],
)
