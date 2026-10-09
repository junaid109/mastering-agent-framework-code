"""Ch 6.3 + 6.5: streaming agent output and fan-out / fan-in with a real join (chapter_06_04, chapter_06_06)."""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root, for support.fake_client

from typing_extensions import Never

from agent_framework import (
    Agent,
    AgentExecutorRequest,
    AgentExecutorResponse,
    AgentResponseUpdate,
    Message,
    WorkflowBuilder,
    WorkflowContext,
    executor,
)
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


def agent(name: str, reply: str) -> Agent:
    return Agent(client=make_client([Reply.text(reply)]), name=name, instructions=f"You are the {name}.")


async def streaming_demo():
    writer, reviewer = agent("writer", "Silent power, loud future."), agent("reviewer", "Approved - punchy.")
    workflow = WorkflowBuilder(start_executor=writer).add_edge(writer, reviewer).build()
    async for event in workflow.run(Message("user", ["Create a slogan for a new electric SUV."]), stream=True):
        if event.type == "output" and isinstance(event.data, AgentResponseUpdate):
            update = event.data
            print(f"[{update.author_name}] {update.text}")


async def fan_out_demo():
    @executor(id="dispatcher")
    async def dispatcher(prompt: str, ctx: WorkflowContext[AgentExecutorRequest]) -> None:
        await ctx.send_message(AgentExecutorRequest(messages=[Message("user", [prompt])], should_respond=True))

    researcher = agent("researcher", "Market is growing 12% a year.")
    marketer = agent("marketer", "Target urban commuters.")
    legal = agent("legal", "Check battery-transport regulations.")

    @executor(id="aggregator")
    async def aggregator(results: list[AgentExecutorResponse], ctx: WorkflowContext[Never, str]) -> None:
        # runs exactly once, after ALL three branches finished (a join, not a race)
        lines = [f"- {r.executor_id}: {r.agent_response.text}" for r in sorted(results, key=lambda r: r.executor_id)]
        await ctx.yield_output("Consolidated report:\n" + "\n".join(lines))

    workflow = (
        WorkflowBuilder(start_executor=dispatcher, output_from=[aggregator])
        .add_fan_out_edges(dispatcher, [researcher, marketer, legal])  # parallel branches
        .add_fan_in_edges([researcher, marketer, legal], aggregator)  # join point
        .build()
    )
    result = await workflow.run("Evaluate launching an electric SUV.")
    print(result.get_outputs()[0])


async def main():
    print("== streaming ==")
    await streaming_demo()
    print("== fan-out / fan-in ==")
    await fan_out_demo()


if __name__ == "__main__":
    asyncio.run(main())
