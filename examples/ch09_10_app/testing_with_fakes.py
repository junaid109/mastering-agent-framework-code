"""Chapter 10.7: plain-class test doubles. Fixed vs. the book: the double needs additional_properties
to satisfy the runtime-checkable SupportsChatGetResponse protocol."""
import asyncio

import os
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from support.fake_client import Reply, ScriptedChatClient  # noqa: E402


def make_client(script):
    if os.environ.get("BOOK_CLIENT") == "openai-compatible":
        from agent_framework.openai import OpenAIChatCompletionClient

        return OpenAIChatCompletionClient(
            base_url=os.environ["BOOK_BASE_URL"],
            api_key=os.environ.get("BOOK_API_KEY", "not-needed"),
            model=os.environ["BOOK_MODEL"],
        )
    return ScriptedChatClient(script)


from agent_framework import Agent, ChatResponse, Message, SupportsChatGetResponse  # noqa: E402


class LocalSummaryClient:
    additional_properties: dict = {}

    async def get_response(self, messages: list[Message], *, stream: bool = False, **kwargs) -> ChatResponse:
        return ChatResponse(messages=[Message(role="assistant", contents=[f"Summary for {len(messages)} messages."])])


class InspectingChatClient(LocalSummaryClient):
    """Records what it received AND returns a deterministic answer."""

    def __init__(self) -> None:
        self.seen: list[list[Message]] = []

    async def get_response(self, messages, *, stream: bool = False, **kwargs) -> ChatResponse:
        self.seen.append(list(messages))
        return await super().get_response(messages, stream=stream, **kwargs)


async def main() -> None:
    assert isinstance(LocalSummaryClient(), SupportsChatGetResponse)
    inspecting = InspectingChatClient()
    agent = Agent(client=inspecting, name="t", instructions="Be terse.")
    reply = await agent.run("hello")
    assert reply.text == "Summary for 1 messages."
    assert [m.text for m in inspecting.seen[0]] == ["hello"]
    print("OK:", reply.text)


if __name__ == "__main__":
    asyncio.run(main())
