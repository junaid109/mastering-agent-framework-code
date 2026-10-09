"""Chapter 10.2: multi-agent concurrency with plain asyncio (fan-out/fan-in and a sequential branching pipeline)."""
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


from agent_framework import Agent  # noqa: E402


async def main() -> None:
    names = ["optimist", "pessimist", "realist"]
    agents = [
        Agent(client=make_client([Reply.text(f"{n} view")]), name=n, instructions=f"Give the {n} view in one line.")
        for n in names
    ]
    # fan-out / fan-in: asyncio.gather instead of a WorkflowBuilder graph
    results = await asyncio.gather(*[a.run("Will the launch succeed?") for a in agents])
    for n, r in zip(names, results):
        print(f"{n}: {r.text}")

    # sequential pipeline: native if/loop control flow instead of edges
    writer = Agent(client=make_client([Reply.text("rough draft"), Reply.text("polished draft")]), name="w", instructions="Write.")
    reviewer = Agent(client=make_client([Reply.text("REJECT"), Reply.text("APPROVE")]), name="r", instructions="Reply APPROVE or REJECT.")
    text = (await writer.run("Draft a tagline")).text
    for _ in range(3):
        if "APPROVE" in (await reviewer.run(text)).text:
            break
        text = (await writer.run(f"Improve: {text}")).text
    print("final:", text)


if __name__ == "__main__":
    asyncio.run(main())
