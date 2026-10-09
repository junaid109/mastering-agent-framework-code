"""Appendix B: bound context (compaction) and bound orchestration (termination_condition)."""
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


from agent_framework import Agent, SlidingWindowStrategy  # noqa: E402
from agent_framework.orchestrations import HandoffBuilder  # noqa: E402


async def compaction_demo() -> None:
    for strategy in (None, SlidingWindowStrategy(keep_last_groups=2)):
        client = make_client(lambda m: Reply.text("noted"))
        agent = Agent(client=client, name="a", instructions="x", compaction_strategy=strategy)
        session = agent.create_session()
        for i in range(6):
            await agent.run(f"turn {i}", session=session)
        label = "no compaction" if strategy is None else "SlidingWindow(2)"
        print(f"{label:>18}: messages sent on last request = {len(client.requests[-1]) if hasattr(client, 'requests') else 'n/a'}")


async def handoff_demo() -> None:
    def mk(name, target):
        return Agent(
            client=make_client(lambda m: Reply.tool_call(f"handoff_to_{target}", {})),
            name=name, instructions=name, description=name, require_per_service_call_history_persistence=True,
        )

    a, b = mk("A", "B"), mk("B", "A")
    wf = (
        HandoffBuilder(participants=[a, b], termination_condition=lambda conv: len(conv) >= 6)
        .with_start_agent(a).add_handoff(a, [b]).add_handoff(b, [a]).build()
    )
    n = 0
    async for ev in wf.run("hi", stream=True):
        n += ev.type == "handoff_sent"
    print(f"ping-pong stopped by termination_condition after {n} handoffs")


async def main() -> None:
    await compaction_demo()
    await handoff_demo()


if __name__ == "__main__":
    asyncio.run(main())
