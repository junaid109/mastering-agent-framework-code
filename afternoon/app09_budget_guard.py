"""Afternoon agent 9: a hard stop on model calls, so a looping agent cannot run up a bill."""
import asyncio
from collections.abc import Awaitable, Callable

from agent_framework import Agent, ChatContext, ChatResponse, Message, chat_middleware, tool

from afternoon.common import make_client


def budget(max_calls: int):
    """Chat middleware sees every model call inside a tool loop (agent middleware sees only the run)."""
    state = {"calls": 0}

    @chat_middleware
    async def guard(context: ChatContext, call_next: Callable[[], Awaitable[None]]) -> None:
        if state["calls"] >= max_calls:
            context.result = ChatResponse(messages=[Message("assistant", [f"Stopped: the {max_calls}-call budget is used up."])])
            return  # no model call is made; with no tool call in the reply, the loop ends
        state["calls"] += 1
        await call_next()

    guard.state = state
    return guard


@tool(approval_mode="never_require")
def poll_status() -> str:
    """Check the job status."""
    return "still running"


async def main():
    from support.fake_client import Reply

    guard = budget(max_calls=3)
    stuck_model = lambda messages: Reply.tool_call("poll_status")  # a model stuck in a loop
    agent = Agent(client=make_client(stuck_model), instructions="Poll until the job is done.", tools=poll_status, middleware=[guard])
    print((await agent.run("Wait for the job.")).text)
    print("model calls made:", guard.state["calls"])


if __name__ == "__main__":
    asyncio.run(main())
