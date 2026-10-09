"""Shared helpers for the ch06_08 tests (kept local: support/fake_client.py is shared and read-only)."""
from __future__ import annotations

from agent_framework import Agent
from support.fake_client import Reply, ScriptedChatClient


def make_agent(name: str, *replies: Reply, **kwargs):
    """Agent backed by a ScriptedChatClient. Returns (agent, client)."""
    client = ScriptedChatClient(list(replies))
    agent = Agent(
        client=client,
        name=name,
        id=name,
        instructions=f"You are {name}.",
        # HandoffBuilder.build() insists on this flag (the book never mentions it)
        require_per_service_call_history_persistence=kwargs.pop("require_per_service_call_history_persistence", True),
        **kwargs,
    )
    return agent, client


def interesting(events, types=("output", "intermediate", "request_info", "handoff_sent")):
    return [e for e in events if e.type in types]
