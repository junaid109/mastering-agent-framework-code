"""Ch 4.1 / 4.8: schema from signature, progressive tool exposure, call caps, error recovery."""
import asyncio
import os
import sys
import warnings
from pathlib import Path
from typing import Annotated

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_framework import Agent, FunctionInvocationContext, tool
from pydantic import Field
from support.fake_client import Reply, ScriptedChatClient

warnings.filterwarnings("ignore")


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
def get_weather(location: Annotated[str, Field(description="The location to get the weather for.")]) -> str:
    """Get the weather for a given location."""
    return f"Sunny in {location}"


@tool(approval_mode="never_require")
def double(x: int) -> int:
    """Double a number."""
    return x * 2


@tool(approval_mode="never_require")
def load_math_tools(ctx: FunctionInvocationContext) -> str:
    """Load the math tools into this conversation."""
    ctx.add_tools(double)
    return "math tools loaded"


@tool(approval_mode="never_require", max_invocations=1)
def once_only(x: str) -> str:
    """Can only be called once."""
    return "ok"


@tool(approval_mode="never_require")
def flaky(x: str) -> str:
    """Always fails; the error is returned to the model instead of crashing."""
    raise ValueError("no such record")


async def main():
    print("schema:", get_weather.name, "|", get_weather.description, "|", get_weather.parameters()["properties"])

    agent = Agent(
        client=make_client([Reply.tool_call("load_math_tools"), Reply.tool_call("double", {"x": 21}),
                            Reply.text("The answer is 42.")]),
        instructions="x", tools=[load_math_tools],
    )
    print("progressive:", (await agent.run("double 21")).text)

    agent = Agent(
        client=make_client([Reply.tool_call("once_only", {"x": "1"}), Reply.tool_call("once_only", {"x": "2"}),
                            Reply.text("done")]),
        instructions="x", tools=[once_only],
    )
    await agent.run("go")
    print("once_only invocation_count:", once_only.invocation_count)

    agent = Agent(
        client=make_client([Reply.tool_call("flaky", {"x": "1"}), Reply.text("I could not find that record.")]),
        instructions="x", tools=[flaky],
    )
    print("recovered:", (await agent.run("lookup")).text)


if __name__ == "__main__":
    asyncio.run(main())
