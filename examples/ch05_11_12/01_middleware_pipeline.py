"""Ch 5.1-5.2, 5.5, 5.7: agent + function + chat middleware in one list (book snippets chapter_05_01/04/06).

Differences from the book that make it work on agent-framework 1.21.0:
  * a middleware that stops the run must set `context.result` (there is no `context.terminate` flag);
    otherwise `agent.run()` returns None.
"""
import asyncio
import os
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root, for support.fake_client

from agent_framework import (
    Agent,
    AgentContext,
    AgentResponse,
    ChatContext,
    FunctionInvocationContext,
    Message,
    chat_middleware,
    tool,
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


@tool
def get_weather(city: str) -> str:
    """Get the weather for a city."""
    return f"Sunny in {city}"


async def security_agent_middleware(context: AgentContext, call_next: Callable[[], Awaitable[None]]) -> None:
    last_message = context.messages[-1] if context.messages else None
    if last_message and last_message.text and "password" in last_message.text.lower():
        print("Security Warning: blocking request.")
        # Not calling call_next() stops execution; set a result so callers get a response, not None.
        context.result = AgentResponse(messages=[Message(role="assistant", contents=["Request blocked by policy."])])
        return
    await call_next()


async def logging_function_middleware(context: FunctionInvocationContext, call_next: Callable[[], Awaitable[None]]) -> None:
    print(f"About to call function: {context.function.name}.")
    await call_next()
    print(f"Function {context.function.name} completed.")


@chat_middleware
async def count_model_calls(context: ChatContext, call_next: Callable[[], Awaitable[None]]) -> None:
    # Chat middleware sees every model call in a tool loop, agent middleware only sees one run().
    count_model_calls.n += 1
    await call_next()


count_model_calls.n = 0


async def main():
    agent = Agent(
        client=make_client([
            Reply.tool_call("get_weather", {"city": "Seattle"}),
            Reply.text("It is sunny in Seattle."),
        ]),
        name="WeatherAgent",
        instructions="You are a helpful weather assistant.",
        tools=get_weather,
        middleware=[security_agent_middleware, logging_function_middleware, count_model_calls],
    )
    result = await agent.run("What's the weather in Seattle?")
    print("Agent:", result.text)
    print("Model calls seen by chat middleware:", count_model_calls.n)

    blocked = await agent.run("My password is hunter2, what's the weather?")
    print("Blocked reply:", blocked.text)


if __name__ == "__main__":
    asyncio.run(main())
