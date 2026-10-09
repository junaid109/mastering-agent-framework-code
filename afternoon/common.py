"""Shared plumbing for the afternoon agents: pick a model, and drive an approval loop."""
from __future__ import annotations

import os
from collections.abc import Callable

from agent_framework import Agent, Message

from support.fake_client import ScriptedChatClient


def make_client(script):
    """Scripted offline model by default; BOOK_CLIENT=openai-compatible uses any OpenAI-compatible server."""
    if os.environ.get("BOOK_CLIENT") == "openai-compatible":
        from agent_framework.openai import OpenAIChatCompletionClient

        return OpenAIChatCompletionClient(
            base_url=os.environ["BOOK_BASE_URL"],
            api_key=os.environ.get("BOOK_API_KEY", "not-needed"),
            model=os.environ["BOOK_MODEL"],
        )
    return ScriptedChatClient(script)


async def run_approved(agent: Agent, query: str, approve: Callable[[object], bool]):
    """Run until no approval is pending. `approve(request)` returns True to allow the tool call."""
    session = agent.create_session()  # approvals are bound to the session that issued them
    result = await agent.run(query, session=session)
    while result.user_input_requests:
        inputs = [query]
        for req in result.user_input_requests:
            inputs += [Message("assistant", [req]), Message("user", [req.to_function_approval_response(approve(req))])]
        result = await agent.run(inputs, session=session)
    return result
