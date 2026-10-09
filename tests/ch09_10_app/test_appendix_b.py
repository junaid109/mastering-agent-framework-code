"""Appendix B pitfalls: each test reproduces the pitfall AND shows the book's fix works."""
import asyncio
import json
import warnings

import pytest
from agent_framework import (
    Agent,
    SlidingWindowStrategy,
    SummarizationStrategy,
    ToolResultCompactionStrategy,
    TruncationStrategy,
    tool,
)
from agent_framework.orchestrations import HandoffBuilder, MagenticBuilder

from support.fake_client import Reply, ScriptedChatClient, flatten

warnings.filterwarnings("ignore")


def text_size(msgs):
    return sum(len(str(getattr(c, "text", None) or getattr(c, "result", None) or "")) for m in msgs for c in m.contents)


async def chat(strategy, turns=8, tools=None, script=None):
    client = ScriptedChatClient(script if script is not None else (lambda m: Reply.text("word " * 30)))
    agent = Agent(client=client, name="a", instructions="x", tools=tools, compaction_strategy=strategy)
    session = agent.create_session()
    for i in range(turns):
        await agent.run(f"question number {i} please answer", session=session)
    return client


# ---------------- B.1 token limit errors ----------------
async def test_b1_pitfall_history_grows_every_turn_without_compaction():
    client = await chat(None)
    counts = [len(r) for r in client.requests]
    assert counts == [1, 3, 5, 7, 9, 11, 13, 15]  # nothing shrinks automatically
    assert text_size(client.requests[-1]) > 4 * text_size(client.requests[1])


async def test_b1_fix_sliding_window_bounds_history():
    client = await chat(SlidingWindowStrategy(keep_last_groups=2))
    assert max(len(r) for r in client.requests) <= 2
    assert flatten(client.requests[-1])[-1][2].startswith("question number 7")  # recent turn kept


async def test_b1_fix_truncation_strategy_is_a_backstop():
    client = await chat(TruncationStrategy(max_n=6, compact_to=4))
    unbounded = await chat(None)
    assert text_size(client.requests[-1]) < text_size(unbounded.requests[-1]) / 2


async def test_b1_fix_summarization_strategy_replaces_old_turns_with_summary():
    summarizer = ScriptedChatClient(lambda m: Reply.text("SUMMARY-OF-OLD-TURNS"))
    client = await chat(SummarizationStrategy(client=summarizer, target_count=2, threshold=2))
    assert len(summarizer.requests) >= 1
    assert max(len(r) for r in client.requests) <= 3
    assert any("SUMMARY-OF-OLD-TURNS" in t for _, _, t in flatten(client.requests[-1]))


@tool
def big_payload(q: str) -> str:
    """Returns a large payload."""
    return "PAYLOAD " * 200


async def test_b1_fix_tool_result_compaction_collapses_old_tool_groups():
    script = []
    for i in range(4):
        script += [Reply.tool_call("big_payload", {"q": str(i)}), Reply.text(f"ans{i}")]
    base = await chat(None, turns=4, tools=[big_payload], script=list(script))
    comp = await chat(ToolResultCompactionStrategy(keep_last_tool_call_groups=1), turns=4, tools=[big_payload], script=list(script))

    def n_function_results(req):
        return sum(1 for _, t, _ in flatten(req) if t == "function_result")

    assert n_function_results(base.requests[-1]) == 4
    assert n_function_results(comp.requests[-1]) == 1  # only the newest tool-call group stays structured
    assert any(t.startswith("[Tool results:") for _, _, t in flatten(comp.requests[-1]))


async def test_b1_note_tool_result_compaction_keeps_payload_text_in_summary():
    """Evidence for a caveat: collapsed groups still carry the payload text, so bytes are not reduced (1.21)."""
    script = []
    for i in range(3):
        script += [Reply.tool_call("big_payload", {"q": str(i)}), Reply.text(f"ans{i}")]
    base = await chat(None, turns=3, tools=[big_payload], script=list(script))
    comp = await chat(ToolResultCompactionStrategy(keep_last_tool_call_groups=1), turns=3, tools=[big_payload], script=list(script))
    assert text_size(comp.requests[-1]) >= 0.9 * text_size(base.requests[-1])


def test_b1_strategy_can_be_set_at_client_level():
    c = ScriptedChatClient(lambda m: Reply.text("ok"), compaction_strategy=SlidingWindowStrategy(keep_last_groups=2))
    assert isinstance(c.compaction_strategy, SlidingWindowStrategy)


async def test_b1_client_level_strategy_actually_applies():
    client = ScriptedChatClient(lambda m: Reply.text("ok"), compaction_strategy=SlidingWindowStrategy(keep_last_groups=2))
    agent = Agent(client=client, name="a", instructions="x")
    s = agent.create_session()
    for i in range(6):
        await agent.run(f"q{i}", session=s)
    assert max(len(r) for r in client.requests) <= 2


# ---------------- B.2 infinite agent loops ----------------
def _ledger(satisfied=False, progress=False):
    it = lambda a: {"reason": "r", "answer": a}  # noqa: E731
    return json.dumps({
        "is_request_satisfied": it(satisfied), "is_in_loop": it(True), "is_progress_being_made": it(progress),
        "next_speaker": it("worker"), "instruction_or_question": it("keep going"),
    })


def _magentic(**limits):
    def mgr_script(msgs):
        return Reply.text(_ledger()) if "is_request_satisfied" in (msgs[-1].text or "") else Reply.text("some text")

    mc = ScriptedChatClient(mgr_script)
    wc = ScriptedChatClient(lambda m: Reply.text("working"))
    mgr = Agent(client=mc, name="mgr", instructions="m")
    worker = Agent(client=wc, name="worker", description="does work", instructions="w")
    return MagenticBuilder(participants=[worker], manager_agent=mgr, **limits).build(), wc


async def _drain(wf, msg="do the task"):
    err = None
    try:
        async for _ in wf.run(msg, stream=True):
            pass
    except Exception as exc:  # noqa: BLE001
        err = exc
    return err


async def test_b2_pitfall_magentic_without_limits_never_converges():
    wf, worker_client = _magentic()
    err = await _drain(wf)
    assert err is not None and "did not converge" in str(err)  # only the runner's 100-superstep guard stops it
    assert len(worker_client.requests) >= 40


async def test_b2_fix_max_round_count_caps_rounds():
    wf, worker_client = _magentic(max_round_count=3)
    assert await _drain(wf) is None
    assert len(worker_client.requests) == 3


async def test_b2_max_stall_count_alone_is_not_enough_needs_max_reset_count():
    """Book groups the three limits; in 1.21 a stall triggers a reset/replan, so max_stall_count alone loops."""
    wf, _ = _magentic(max_stall_count=1)
    err = await _drain(wf)
    assert err is not None and "did not converge" in str(err)


async def test_b2_fix_stall_plus_reset_cap_terminates_cleanly():
    wf, worker_client = _magentic(max_stall_count=1, max_reset_count=1)
    assert await _drain(wf) is None
    assert len(worker_client.requests) <= 3


def _pingpong_handoff(termination_condition=None):
    mk = lambda name, target: Agent(  # noqa: E731
        client=ScriptedChatClient(lambda m, t=target: Reply.tool_call(f"handoff_to_{t}", {})),
        name=name, instructions=name, description=name, require_per_service_call_history_persistence=True,
    )
    a, b = mk("A", "B"), mk("B", "A")
    builder = HandoffBuilder(participants=[a, b], termination_condition=termination_condition)
    return builder.with_start_agent(a).add_handoff(a, [b]).add_handoff(b, [a]).build()


async def _count_handoffs(wf, stop_at=1000):
    n, err = 0, None
    try:
        async for ev in wf.run("hi", stream=True):
            if ev.type == "handoff_sent":
                n += 1
                if n >= stop_at:
                    break
    except Exception as exc:  # noqa: BLE001
        err = exc
    return n, err


async def test_b2_pitfall_handoff_cycle_has_no_default_max_turns():
    n, err = await _count_handoffs(_pingpong_handoff())
    assert err is not None and "did not converge" in str(err)
    assert n >= 90  # book says a default `max_turns` bounds the mesh: no such default; only the runner guard (100 supersteps)


def test_b2_handoffbuilder_has_no_max_turns_parameter():
    import inspect

    assert "max_turns" not in inspect.signature(HandoffBuilder.__init__).parameters
    assert not hasattr(HandoffBuilder, "max_turns")


async def test_b2_fix_termination_condition_bounds_handoff_mesh():
    n, err = await _count_handoffs(_pingpong_handoff(lambda conv: len(conv) >= 6))
    assert err is None and n < 20


async def test_b2_fix_with_termination_condition_method_also_works():
    a = Agent(client=ScriptedChatClient(lambda m: Reply.tool_call("handoff_to_B", {})), name="A", instructions="a", description="a",
              require_per_service_call_history_persistence=True)
    b = Agent(client=ScriptedChatClient(lambda m: Reply.tool_call("handoff_to_A", {})), name="B", instructions="b", description="b",
              require_per_service_call_history_persistence=True)
    wf = (HandoffBuilder(participants=[a, b]).with_start_agent(a).add_handoff(a, [b]).add_handoff(b, [a])
          .with_termination_condition(lambda conv: len(conv) >= 6).build())
    n, err = await _count_handoffs(wf)
    assert err is None and n < 20


# ---------------- B.3 tool timeouts / retry loops ----------------
async def test_b3_pitfall_tool_without_limit_is_called_every_time_model_asks():
    calls = []

    @tool
    def lookup(q: str) -> str:
        """lookup"""
        calls.append(q)
        return "r"

    client = ScriptedChatClient([Reply.tool_call("lookup", {"q": "a"})] * 5 + [Reply.text("done")])
    await Agent(client=client, name="a", instructions="x", tools=[lookup]).run("go")
    assert len(calls) == 5


async def test_b3_fix_max_invocations_caps_calls():
    calls = []

    @tool(max_invocations=2)
    def lookup(q: str) -> str:
        """lookup"""
        calls.append(q)
        return "r"

    client = ScriptedChatClient([Reply.tool_call("lookup", {"q": "a"})] * 5 + [Reply.text("done")])
    r = await Agent(client=client, name="a", instructions="x", tools=[lookup]).run("go")
    assert len(calls) == 2  # tool body not executed beyond the cap
    assert r.text  # run still completes with a result


async def test_b3_max_invocations_is_lifetime_of_tool_object_not_per_run():
    """Book says 'within one run'. In 1.21 the counter lives on the FunctionTool and persists across runs."""
    calls = []

    @tool(max_invocations=2)
    def lookup(q: str) -> str:
        """lookup"""
        calls.append(q)
        return "r"

    for _ in range(2):
        client = ScriptedChatClient([Reply.tool_call("lookup", {"q": "a"}), Reply.tool_call("lookup", {"q": "b"}), Reply.text("done")])
        await Agent(client=client, name="a", instructions="x", tools=[lookup]).run("go")
    assert len(calls) == 2  # second run got zero real calls
    assert lookup.invocation_count == 2
    lookup.invocation_count = 0  # manual reset restores per-run behaviour
    client = ScriptedChatClient([Reply.tool_call("lookup", {"q": "c"}), Reply.text("done")])
    await Agent(client=client, name="a", instructions="x", tools=[lookup]).run("go")
    assert len(calls) == 3


async def test_b3_fix_max_invocation_exceptions_stops_failing_tool():
    calls = []

    @tool(max_invocation_exceptions=2)
    def flaky(q: str) -> str:
        """flaky"""
        calls.append(q)
        raise RuntimeError("boom")

    client = ScriptedChatClient([Reply.tool_call("flaky", {"q": "a"})] * 6 + [Reply.text("done")])
    await Agent(client=client, name="a", instructions="x", tools=[flaky]).run("go")
    assert len(calls) == 2


async def test_b3_pitfall_slow_tool_blocks_run_and_wait_for_bounds_it():
    """Pitfall: one slow tool holds the run open. Generic fix (not the book's): bound it with asyncio.timeout."""

    @tool
    async def slow(q: str) -> str:
        """slow"""
        await asyncio.sleep(1.0)
        return "late"

    client = ScriptedChatClient([Reply.tool_call("slow", {"q": "a"}), Reply.text("done")])
    agent = Agent(client=client, name="a", instructions="x", tools=[slow])
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(agent.run("go"), timeout=0.2)


def test_b3_background_responses_options_exist_on_openai_client():
    """Python analogue of AllowBackgroundResponses: `background` option + continuation_token. Structure only."""
    from agent_framework.openai import OpenAIChatOptions

    assert {"background", "continuation_token"} <= set(OpenAIChatOptions.__annotations__)


def test_b3_mcp_long_running_task_needs_server():
    pytest.skip("NEEDS_MODEL/server: MCP SEP-2663 long-running task sample (mcp_long_running_task.py) needs an MCP server")


# ---------------- B.4 context window management ----------------
async def test_b4_fix_tight_window_keeps_context_small_and_relevant_regardless_of_conversation_length():
    long = await chat(SlidingWindowStrategy(keep_last_groups=2), turns=20)
    short = await chat(SlidingWindowStrategy(keep_last_groups=2), turns=4)
    assert text_size(long.requests[-1]) == pytest.approx(text_size(short.requests[-1]), rel=0.2)


async def test_b4_pitfall_window_forgets_exact_facts_so_store_them_in_session_state():
    """Book: store what must be exact in explicit state. Compaction drops turn 0, session.state keeps it."""
    client = ScriptedChatClient(lambda m: Reply.text("ok"))
    agent = Agent(client=client, name="a", instructions="x", compaction_strategy=SlidingWindowStrategy(keep_last_groups=2))
    session = agent.create_session()
    await agent.run("My order id is A-1234", session=session)
    session.state["order_id"] = "A-1234"
    for i in range(4):
        await agent.run(f"filler {i}", session=session)
    seen = [t for _, _, t in flatten(client.requests[-1])]
    assert not any("A-1234" in t for t in seen)  # forgotten by the model's context
    assert session.state["order_id"] == "A-1234"  # but exact in explicit state
    restored = type(session).from_dict(session.to_dict())
    assert restored.state["order_id"] == "A-1234"


def test_b4_effective_attention_degradation_needs_model():
    pytest.skip("NEEDS_MODEL: quality degradation of a real model's attention over long context is not testable offline")
