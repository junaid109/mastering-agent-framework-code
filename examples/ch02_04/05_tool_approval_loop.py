"""Ch 4.7: human-in-the-loop approval. The book's loop needs a session to work in 1.21.0 (chapter_04_06)."""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_framework import Agent, Message, tool
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
def send_email(to: str) -> str:
    """Send an email."""
    print(f"   [tool executed: email sent to {to}]")
    return f"sent to {to}"


async def main():
    agent = Agent(
        client=make_client([Reply.tool_call("send_email", {"to": "ada@example.com"}),
                            Reply.text("Email sent to Ada.")]),
        instructions="You send emails when asked.",
        tools=send_email,
    )
    session = agent.create_session()  # REQUIRED: approvals are bound to the session that issued them
    query = "Email ada@example.com"
    result = await agent.run(query, session=session)
    while len(result.user_input_requests) > 0:
        new_inputs = [query]
        for req in result.user_input_requests:
            print(f"Function: {req.function_call.name}  Arguments: {req.function_call.arguments}")
            new_inputs.append(Message("assistant", [req]))
            approved = os.environ.get("APPROVE", "y").lower() == "y"  # non-interactive for the demo
            new_inputs.append(Message("user", [req.to_function_approval_response(approved)]))
        result = await agent.run(new_inputs, session=session)
    print(result.text)


if __name__ == "__main__":
    asyncio.run(main())
