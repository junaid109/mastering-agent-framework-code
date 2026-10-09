"""Ch 12.2 / 12.4: approval gating for a dangerous tool, and right-to-erasure for conversation history.

Note: the book says `history_provider.clear(session_id)` exists on every HistoryProvider. In 1.21.0 it exists on
the Cosmos, Redis and vector-store providers only; for the built-in providers this example shows the equivalent.
"""
import asyncio
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root, for support.fake_client

from agent_framework import Agent, AgentSession, FileHistoryProvider, Message, tool
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


@tool(approval_mode="always_require")
def delete_table(table: str) -> str:
    """Delete a database table."""
    print(f"  (deleting {table})")
    return f"deleted {table}"


async def approval_demo():
    print("--- approval_mode='always_require'")
    agent = Agent(
        client=make_client([Reply.tool_call("delete_table", {"table": "users"}), Reply.text("Table deleted.")]),
        name="ops", instructions="You are an ops assistant.", tools=delete_table,
    )
    session = agent.create_session()  # the SAME session must be passed back when resuming an approval
    first = await agent.run("Drop the users table", session=session)
    request = first.user_input_requests[0]
    print("approval requested for:", request.function_call.name, request.function_call.arguments)
    reply = Message(role="user", contents=[request.to_function_approval_response(True)])
    final = await agent.run(reply, session=session)
    print("Agent:", final.text)


async def erasure_demo():
    print("--- right to erasure (file history provider)")
    with tempfile.TemporaryDirectory() as tmp:
        provider = FileHistoryProvider(tmp)
        agent = Agent(client=make_client([Reply.text("Hi Ada."), Reply.text("I don't know your name.")]),
                      name="chat", instructions="Be brief.", context_providers=[provider])
        await agent.run("My name is Ada", session=AgentSession(session_id="user-1"))
        files = list(Path(tmp).glob("*"))
        print("persisted files:", len(files))
        for f in files:  # erasure for the file provider = delete the per-session file(s)
            f.unlink()
        print("after erasure:", len(list(Path(tmp).glob("*"))), "files")
        r = await agent.run("What is my name?", session=AgentSession(session_id="user-1"))
        print("Agent:", r.text)


async def main():
    await approval_demo()
    await erasure_demo()


if __name__ == "__main__":
    asyncio.run(main())
