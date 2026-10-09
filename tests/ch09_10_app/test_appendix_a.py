"""Appendix A: only the Agent Framework 'after' halves are executed.

'Before' halves (semantic_kernel / autogen / langchain) are SKIPPED_PLACEHOLDER: those libraries are not installed.
"""
import json
import warnings

import pytest
from agent_framework import Agent, Executor, WorkflowBuilder, WorkflowContext, handler, tool
from agent_framework.orchestrations import GroupChatBuilder, HandoffBuilder, MagenticBuilder, SequentialBuilder

from support.fake_client import Reply, ScriptedChatClient, flatten

warnings.filterwarnings("ignore")


def _agent(name, text, **kw):
    return Agent(client=ScriptedChatClient(lambda m, t=text: Reply.text(t)), name=name, instructions=name, **kw)


# ---- A.1 snippet appendix_a_01 : AF half ----
async def test_a1_agent_framework_half_single_agent_mapping():
    client = ScriptedChatClient([Reply.text("Remove the wheel, pry the tire off, and replace the tube.")])
    chat_agent = Agent(client=client, name="Support", instructions="Answer in one sentence.")  # service= -> client=
    reply = await chat_agent.run("How do I reset my bike tire?")  # get_response(messages=) -> run(...)
    assert reply.text.startswith("Remove the wheel")  # response.message.content -> reply.text
    assert ("user", "text", "How do I reset my bike tire?") in flatten(client.requests[0])


def test_a1_openai_client_zero_arg_constructor_reads_env(monkeypatch):
    from agent_framework.openai import OpenAIChatClient

    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("OPENAI_MODEL", "m")
    Agent(client=OpenAIChatClient(), name="Support", instructions="Answer in one sentence.")


def test_a1_sk_half_is_not_executed():
    pytest.skip("SKIPPED_PLACEHOLDER: semantic_kernel not installed (before-half)")


async def test_a1_sk_team_mappings_sequential_builder():
    wf = SequentialBuilder(participants=[_agent("a", "A"), _agent("b", "B")]).build()
    res = await wf.run("task")
    assert res.get_outputs()[0].text == "B"


async def test_a1_fan_out_fan_in_workflow_and_subworkflow():
    from agent_framework import WorkflowExecutor

    class Start(Executor):
        @handler
        async def go(self, text: str, ctx: WorkflowContext[str]) -> None:
            await ctx.send_message(text)

    class Worker(Executor):
        @handler
        async def go(self, text: str, ctx: WorkflowContext[str]) -> None:
            await ctx.send_message(f"{self.id}:{text}")

    class Join(Executor):
        @handler
        async def go(self, items: list[str], ctx: WorkflowContext[None, str]) -> None:
            await ctx.yield_output(",".join(sorted(items)))

    s, w1, w2, j = Start(id="s"), Worker(id="w1"), Worker(id="w2"), Join(id="j")
    wf = WorkflowBuilder(start_executor=s).add_fan_out_edges(s, [w1, w2]).add_fan_in_edges([w1, w2], j).build()
    assert (await wf.run("x")).get_outputs() == ["w1:x,w2:x"]

    # sub-workflow composition (6.6)
    sub = WorkflowExecutor(wf, id="sub")
    assert sub is not None


# ---- A.2 AutoGen table: AF side ----
async def test_a2_assistant_agent_maps_to_agent():
    assert (await _agent("assistant", "hi").run("x")).text == "hi"


async def test_a2_round_robin_group_chat_via_groupchatbuilder_selection_func():
    order = ["a", "b"]
    picked = []

    def round_robin(state):
        picked.append(order[state.current_round % len(order)])
        return picked[-1]

    ca = ScriptedChatClient(lambda m: Reply.text("from a"))
    cb = ScriptedChatClient(lambda m: Reply.text("from b"))
    a = Agent(client=ca, name="a", instructions="a")
    b = Agent(client=cb, name="b", instructions="b")
    wf = GroupChatBuilder(participants=[a, b], selection_func=round_robin, max_rounds=4).build()
    res = await wf.run("start")
    assert res.get_outputs()
    assert picked[:4] == ["a", "b", "a", "b"]
    assert len(ca.requests) == 2 and len(cb.requests) == 2


async def test_a2_selector_group_chat_via_selection_func_picks_by_content():
    picked = []

    def selector(state):
        nxt = "b" if state.current_round == 0 else "a"
        picked.append(nxt)
        return nxt

    wf = GroupChatBuilder(participants=[_agent("a", "A"), _agent("b", "B")], selection_func=selector, max_rounds=2).build()
    await wf.run("go")
    assert picked[:2] == ["b", "a"]


async def test_a2_swarm_maps_to_handoff_builder():
    triage = Agent(
        client=ScriptedChatClient([Reply.tool_call("handoff_to_billing", {}), Reply.text("(unused)")]),
        name="triage", instructions="t", description="triage", require_per_service_call_history_persistence=True,
    )
    billing = _agent("billing", "Refund issued.", description="billing", require_per_service_call_history_persistence=True)
    wf = HandoffBuilder(participants=[triage, billing]).with_start_agent(triage).add_handoff(triage, [billing]).build()
    texts = []
    async for ev in wf.run("refund please", stream=True):
        if ev.type == "handoff_sent":
            texts.append((ev.data.source, ev.data.target))
    assert texts == [("triage", "billing")]


def test_a2_magentic_one_maps_to_magentic_builder():
    mgr = _agent("mgr", "x")
    MagenticBuilder(participants=[_agent("worker", "w", description="d")], manager_agent=mgr).build()


async def test_a2_agent_as_tool():
    """single_agent/04_agent_as_tool.py equivalent: expose one Agent as a callable tool of another."""
    researcher = _agent("researcher", "Found: 42", description="Researches facts")
    tool_obj = researcher.as_tool(name="research", arg_name="task")
    boss_client = ScriptedChatClient([Reply.tool_call("research", {"task": "meaning of life"}), Reply.text("The answer is 42.")])
    boss = Agent(client=boss_client, name="boss", instructions="delegate", tools=[tool_obj])
    r = await boss.run("what is the answer?")
    assert r.text == "The answer is 42."
    assert ("tool", "function_result", "Found: 42") in flatten(boss_client.requests[1])


def test_a2_autogen_half_is_not_executed():
    pytest.skip("SKIPPED_PLACEHOLDER: autogen not installed (before-half)")


# ---- A.3 LangChain conceptual mappings ----
def test_a3_tool_schema_derived_from_signature():
    @tool
    def get_weather(city: str, units: str = "c") -> str:
        """Get weather for a city."""
        return "sunny"

    schema = get_weather.parameters()
    assert set(schema["properties"]) == {"city", "units"}
    assert schema["required"] == ["city"]


async def test_a3_lcel_style_chain_maps_to_workflowbuilder_add_chain_or_sequential():
    class Up(Executor):
        @handler
        async def go(self, t: str, ctx: WorkflowContext[str]) -> None:
            await ctx.send_message(t.upper())

    class Excl(Executor):
        @handler
        async def go(self, t: str, ctx: WorkflowContext[None, str]) -> None:
            await ctx.yield_output(t + "!")

    u, e = Up(id="up"), Excl(id="ex")
    wf = WorkflowBuilder(start_executor=u).add_edge(u, e).build()
    assert (await wf.run("hi")).get_outputs() == ["HI!"]
    wf2 = WorkflowBuilder(start_executor=u).add_chain([u, e]).build()
    assert (await wf2.run("yo")).get_outputs() == ["YO!"]


def test_a3_memory_equivalents_exist():
    import agent_framework as af

    for n in ("HistoryProvider", "InMemoryHistoryProvider", "SlidingWindowStrategy", "SummarizationStrategy", "TruncationStrategy"):
        assert hasattr(af, n)


def test_a3_langchain_half_is_not_executed():
    pytest.skip("SKIPPED_PLACEHOLDER: conceptual mapping, no LangChain code in book")
