"""Ch 3.4: client < agent < run compaction override hierarchy (chapter_03_07)."""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_framework import Agent, SlidingWindowStrategy, TruncationStrategy
from support.fake_client import Reply, ScriptedChatClient


def make_client(script, **client_kwargs):
    """Offline ScriptedChatClient by default; set BOOK_CLIENT=openai-compatible for a real endpoint."""
    if os.environ.get("BOOK_CLIENT") == "openai-compatible":
        from agent_framework.openai import OpenAIChatCompletionClient

        return OpenAIChatCompletionClient(
            base_url=os.environ["BOOK_BASE_URL"],
            api_key=os.environ.get("BOOK_API_KEY", "not-needed"),
            model=os.environ["BOOK_MODEL"],
            **client_kwargs,
        )
    return ScriptedChatClient(script, **client_kwargs)


class FixedTokenizer:
    """The book uses this without defining it; it is a sample-local helper, not a framework export."""

    def __init__(self, n: int) -> None:
        self.n = n

    def count_tokens(self, text: str) -> int:
        return self.n


async def main():
    shared_client = make_client(
        lambda m: Reply.text("ok"),
        compaction_strategy=TruncationStrategy(max_n=3, compact_to=2),
        tokenizer=FixedTokenizer(7),
    )
    default_agent = Agent(client=shared_client, name="ClientDefaultAgent")
    session = default_agent.create_session()
    for i in range(4):
        await default_agent.run(f"message {i}", session=session)
        if isinstance(shared_client, ScriptedChatClient):
            print(f"turn {i}: model received {len(shared_client.requests[-1])} messages")

    override_agent = Agent(
        client=shared_client,
        name="AgentOverrideAgent",
        compaction_strategy=SlidingWindowStrategy(keep_last_groups=3),
        tokenizer=FixedTokenizer(11),
    )
    await override_agent.run(
        "hi", compaction_strategy=TruncationStrategy(max_n=2, compact_to=1), tokenizer=FixedTokenizer(23)
    )
    print("agent-level and per-run overrides ran OK")


if __name__ == "__main__":
    asyncio.run(main())
