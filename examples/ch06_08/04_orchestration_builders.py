"""Ch 8: Sequential, Concurrent, GroupChat, Handoff and Magentic builders with scripted agents."""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root, for support.fake_client

from agent_framework import Agent
from agent_framework.orchestrations import (
    ConcurrentBuilder,
    GroupChatBuilder,
    HandoffBuilder,
    MagenticBuilder,
    SequentialBuilder,
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


def agent(name: str, *replies: Reply) -> Agent:
    return Agent(
        client=make_client(list(replies)),
        name=name,
        id=name,
        instructions=f"You are the {name}.",
        require_per_service_call_history_persistence=True,  # required by HandoffBuilder (not mentioned in the book)
    )


def ledger(satisfied: bool, speaker: str = "researcher", instruction: str = "") -> Reply:
    item = lambda a: {"reason": "-", "answer": a}  # noqa: E731
    return Reply.text(json.dumps(dict(
        is_request_satisfied=item(satisfied), is_in_loop=item(False), is_progress_being_made=item(True),
        next_speaker=item(speaker), instruction_or_question=item(instruction),
    )))


async def main():
    # Sequential: fixed pipeline, shared growing conversation; output is the last stage's response
    wf = SequentialBuilder(participants=[agent("drafter", Reply.text("Draft v1")), agent("editor", Reply.text("Draft v1, edited"))]).build()
    print("sequential ->", (await wf.run("Write a tagline")).get_outputs()[0].text)

    # Concurrent: same prompt, independent answers, aggregated
    wf = ConcurrentBuilder(participants=[agent("optimist", Reply.text("Ship it!")), agent("skeptic", Reply.text("Test more."))]).build()
    out = (await wf.run("Should we launch?")).get_outputs()[0]
    print("concurrent ->", [(m.author_name, m.text) for m in out.messages if m.role == "assistant"])

    # GroupChat with a plain function selector (deterministic turn-taking) and a termination condition
    alice, bob = agent("alice", Reply.text("Cats."), Reply.text("Still cats.")), agent("bob", Reply.text("Dogs."), Reply.text("Fine, dogs."))
    wf = GroupChatBuilder(
        participants=[alice, bob],
        selection_func=lambda s: list(s.participants)[s.current_round % 2],
        termination_condition=lambda msgs: len(msgs) >= 5,
        output_from="all",  # also surface each participant's turns, not only the orchestrator's closing message
        # an LLM-driven manager is passed the same way: GroupChatBuilder(participants=[...], orchestrator_agent=manager)
    ).build()
    async for ev in wf.run("Best pet?", stream=True):
        if ev.type == "output":
            print(f"groupchat [{ev.data.author_name}] {ev.data.text}")

    # Handoff: triage hands off to refund via the auto-registered handoff_to_refund tool
    triage = agent("triage", Reply.tool_call("handoff_to_refund"))
    refund = agent("refund", Reply.text("Welcome! Your refund is on its way."))
    wf = HandoffBuilder(
        name="customer_support_handoff",
        participants=[triage, refund],
        termination_condition=lambda conv: len(conv) > 0 and "welcome" in conv[-1].text.lower(),
    ).with_start_agent(triage).build()
    result = await wf.run("I want a refund")
    print("handoff ->", [(e.data.source, e.data.target) for e in result if e.type == "handoff_sent"],
          "| ended:", result.get_final_state().name)

    # Magentic: manager plans, delegates, declares success; bounded by round / stall / reset limits
    manager = agent("manager", Reply.text("facts"), Reply.text("plan"), ledger(False, "researcher", "collect facts"),
                    ledger(True), Reply.text("FINAL: three facts found."))
    researcher = agent("researcher", Reply.text("fact 1, fact 2, fact 3"))
    wf = MagenticBuilder(participants=[researcher, agent("coder", Reply.text("n/a"))], manager_agent=manager,
                         max_round_count=10, max_stall_count=3, max_reset_count=2).build()
    print("magentic ->", (await wf.run("Research topic X")).get_outputs()[-1].text)


if __name__ == "__main__":
    asyncio.run(main())
