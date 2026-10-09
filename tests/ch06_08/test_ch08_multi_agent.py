"""Chapter 8 - Multi-Agent Collaboration. Runs all five orchestration builders with scripted agents."""
from __future__ import annotations

import json

import pytest

from agent_framework import Agent, Message, WorkflowBuilder
from agent_framework.orchestrations import (
    ConcurrentBuilder,
    GroupChatBuilder,
    HandoffAgentUserRequest,
    HandoffBuilder,
    MagenticBuilder,
    SequentialBuilder,
)
from support.fake_client import Reply, ScriptedChatClient

from ch0608_helpers import make_agent


def J(**kw) -> Reply:
    return Reply.text(json.dumps(kw))


# ================================================================== 8.1 HandoffBuilder (chapter_08_01)
def build_support_team(triage_script, refund_script, termination=None, **kw):
    triage, ct = make_agent("triage", *triage_script)
    refund, cr = make_agent("refund", *refund_script)
    order, co = make_agent("order", Reply.text("order handled"))
    support, cs = make_agent("support", Reply.text("support handled"))
    workflow = (  # chapter_08_01 (termination_condition verbatim)
        HandoffBuilder(
            name="customer_support_handoff",
            participants=[triage, refund, order, support],
            termination_condition=termination
            or (lambda conversation: len(conversation) > 0 and "welcome" in conversation[-1].text.lower()),
        )
        .with_start_agent(triage)
        .build()
    )
    return workflow, dict(triage=ct, refund=cr, order=co, support=cs)


async def test_ch08_01_handoff_triage_routes_to_refund_via_auto_registered_tool():
    wf, c = build_support_team(
        [Reply.tool_call("handoff_to_refund")],
        [Reply.text("Welcome! Your refund has been issued.")],
    )
    assert wf.name == "customer_support_handoff"
    result = await wf.run("I want a refund for order 7")
    handoffs = [e.data for e in result if e.type == "handoff_sent"]
    assert [(h.source, h.target) for h in handoffs] == [("triage", "refund")]
    # specialist answered, other specialists never ran
    assert len(c["refund"].requests) == 1 and c["order"].requests == [] and c["support"].requests == []
    # the specialist received the user's original message through the shared conversation
    assert "I want a refund for order 7" in [m.text for m in c["refund"].requests[0]]


async def test_ch08_01_handoff_tool_registered_for_every_participant():
    """'HandoffBuilder auto-registers a handoff tool for every participant'."""
    seen_tools: dict[str, set[str]] = {}

    def spy(name):
        client = ScriptedChatClient([Reply.text("ok")])
        orig = client._inner_get_response

        def wrapped(*, messages, stream, options, **kwargs):
            seen_tools.setdefault(name, set()).update(
                getattr(t, "name", str(t)) for t in (options.get("tools") or [])
            )
            return orig(messages=messages, stream=stream, options=options, **kwargs)

        client._inner_get_response = wrapped
        return Agent(client=client, name=name, id=name, instructions=name, require_per_service_call_history_persistence=True)

    triage, refund, order = spy("triage"), spy("refund"), spy("order")
    wf = HandoffBuilder(participants=[triage, refund, order]).with_start_agent(triage).build()
    await wf.run("hello")
    assert {"handoff_to_refund", "handoff_to_order"} <= seen_tools["triage"]
    assert "handoff_to_triage" not in seen_tools["triage"]


async def test_ch08_01_handoff_termination_condition_ends_conversation_without_asking_user():
    wf, _ = build_support_team([Reply.tool_call("handoff_to_refund")], [Reply.text("Welcome! Refund issued.")])
    result = await wf.run("refund please")
    assert result.get_request_info_events() == []
    assert str(result.get_final_state()) == "WorkflowRunState.IDLE"


async def test_ch08_04_handoff_without_termination_keeps_requesting_user_input():
    """Book: 'without one, the default behavior keeps requesting user input'. (Its follow-up claim, '...until a
    configured max_turns is hit', has no counterpart in 1.21.0: see test_ch08_04_MISMATCH_no_max_turns.)"""
    triage, _ = make_agent("triage", Reply.tool_call("handoff_to_refund"))
    refund, _ = make_agent("refund", Reply.text("Welcome! Refund issued."), Reply.text("Anything else?"), Reply.text("And now?"))
    wf = HandoffBuilder(participants=[triage, refund]).with_start_agent(triage).build()
    result = await wf.run("refund")
    for turn in range(2):
        reqs = result.get_request_info_events()
        assert len(reqs) == 1 and isinstance(reqs[0].data, HandoffAgentUserRequest)
        assert str(result.get_final_state()) == "WorkflowRunState.IDLE_WITH_PENDING_REQUESTS"
        result = await wf.run(responses={reqs[0].request_id: HandoffAgentUserRequest.create_response("thanks")})
    assert len(result.get_request_info_events()) == 1  # still asking after 3 agent turns: no built-in cap


def test_ch08_04_MISMATCH_no_max_turns_setting_exists():
    """Book 8.4: 'the default behavior keeps requesting user input until a configured max_turns is hit'.
    HandoffBuilder in agent-framework-orchestrations 1.3.1 has no max_turns parameter or method."""
    import inspect

    assert "max_turns" not in inspect.signature(HandoffBuilder.__init__).parameters
    assert not any("max_turn" in m for m in dir(HandoffBuilder))
    with pytest.raises(TypeError):
        HandoffBuilder(participants=[make_agent("a")[0]], max_turns=3)  # type: ignore[call-arg]


async def test_ch08_01_handoff_requires_per_service_call_history_persistence_flag():
    """Not in the book: build() raises unless every participant sets require_per_service_call_history_persistence."""
    t = Agent(client=ScriptedChatClient([Reply.text("x")]), name="t", id="t", instructions="x")
    r = Agent(client=ScriptedChatClient([Reply.text("x")]), name="r", id="r", instructions="x")
    with pytest.raises(ValueError, match="require_per_service_call_history_persistence"):
        HandoffBuilder(participants=[t, r]).with_start_agent(t).build()


async def test_ch08_01_handoff_autonomous_mode_specialist_iterates_until_handoff():
    triage, _ = make_agent("triage", Reply.tool_call("handoff_to_refund"), Reply.text("Welcome back, anything else?"))
    refund, cr = make_agent(
        "refund",
        Reply.text("step 1: looking up the order"),
        Reply.text("step 2: issuing refund"),
        Reply.tool_call("handoff_to_triage"),
    )
    # default turn limit is generous; the specialist keeps going without asking the user
    wf = (
        HandoffBuilder(
            participants=[triage, refund],
            termination_condition=lambda conv: len(conv) > 0 and "welcome" in conv[-1].text.lower(),
        )
        .with_start_agent(triage)
        .with_autonomous_mode(agents=[refund])
        .build()
    )
    result = await wf.run("refund")
    assert result.get_request_info_events() == []  # never returned to the user
    texts = [m.text for req in cr.requests for m in req]
    assert "User did not respond. Continue assisting autonomously." in texts
    assert len(cr.requests) >= 3  # specialist ran multiple self-directed turns before handing off


# ================================================================== 8.1 SequentialBuilder
async def test_ch08_01_sequential_runs_in_order_with_shared_growing_context():
    a, ca = make_agent("a", Reply.text("A done"))
    b, cb = make_agent("b", Reply.text("B done"))
    c, cc = make_agent("c", Reply.text("C done"))
    wf = SequentialBuilder(participants=[a, b, c]).build()
    result = await wf.run("start")
    assert [m.text for m in cb.requests[0]] == ["start", "A done"]
    assert [m.text for m in cc.requests[0]] == ["start", "A done", "B done"]  # each sees everything before it
    assert result.get_outputs()[0].text == "C done"  # the workflow output is the last stage's response


# ================================================================== 8.2 ConcurrentBuilder: independent context
async def test_ch08_02_concurrent_participants_get_same_prompt_and_cannot_see_siblings():
    a, ca = make_agent("a", Reply.text("view A"))
    b, cb = make_agent("b", Reply.text("view B"))
    c, cc = make_agent("c", Reply.text("view C"))
    wf = ConcurrentBuilder(participants=[a, b, c]).build()
    result = await wf.run("What should we do?")
    for client in (ca, cb, cc):
        assert [m.text for m in client.requests[0]] == ["What should we do?"]  # nobody saw a sibling's answer
    out = result.get_outputs()[0]
    msgs = out.messages if hasattr(out, "messages") else out
    assert {(m.author_name, m.text) for m in msgs if m.role == "assistant"} == {("a", "view A"), ("b", "view B"), ("c", "view C")}


async def test_ch08_02_concurrent_custom_aggregator():
    a, _ = make_agent("a", Reply.text("1"))
    b, _ = make_agent("b", Reply.text("2"))

    async def agg(results) -> str:
        return "+".join(sorted(r.agent_response.text for r in results))

    wf = ConcurrentBuilder(participants=[a, b]).with_aggregator(agg).build()
    assert (await wf.run("q")).get_outputs() == ["1+2"]


# ================================================================== 8.1 GroupChatBuilder
async def test_ch08_01_groupchat_function_selector_gives_deterministic_turns_and_shared_history():
    alice, cal = make_agent("alice", Reply.text("alice 1"), Reply.text("alice 2"))
    bob, cbo = make_agent("bob", Reply.text("bob 1"), Reply.text("bob 2"))

    def round_robin(state):
        return list(state.participants)[state.current_round % len(state.participants)]

    wf = GroupChatBuilder(
        participants=[alice, bob], selection_func=round_robin, termination_condition=lambda msgs: len(msgs) >= 5
    ).build()
    result = await wf.run("debate")
    assert len(cal.requests) == 2 and len(cbo.requests) == 2  # alternating A, B, A, B
    # bob's first turn already saw alice's first message: one shared conversation
    assert [m.text for m in cbo.requests[0]] == ["debate", "alice 1"]
    assert [m.text for m in cal.requests[1]] == ["debate", "alice 1", "bob 1"]
    assert str(result.get_final_state()) == "WorkflowRunState.IDLE"


async def test_ch08_04_groupchat_max_rounds_bounds_the_process():
    alice, cal = make_agent("alice", *[Reply.text(f"a{i}") for i in range(10)])
    bob, cbo = make_agent("bob", *[Reply.text(f"b{i}") for i in range(10)])
    wf = GroupChatBuilder(
        participants=[alice, bob],
        selection_func=lambda s: list(s.participants)[s.current_round % 2],
        max_rounds=3,
    ).build()
    await wf.run("endless")
    assert len(cal.requests) + len(cbo.requests) == 3


async def test_ch08_01_groupchat_llm_manager_via_orchestrator_agent_picks_speakers_and_terminates():
    alice, cal = make_agent("alice", Reply.text("alice idea"))
    bob, cbo = make_agent("bob", Reply.text("bob critique"))
    manager, cm = make_agent(
        "manager",
        J(terminate=False, reason="open", next_speaker="alice", final_message=None),
        J(terminate=False, reason="rebut", next_speaker="bob", final_message=None),
        J(terminate=True, reason="converged", next_speaker=None, final_message="Consensus reached."),
    )
    wf = GroupChatBuilder(participants=[alice, bob], orchestrator_agent=manager).build()
    result = await wf.run("topic")
    assert [m.text for m in cbo.requests[0]] == ["topic", "alice idea"]
    assert len(cm.requests) == 3
    out = result.get_outputs()
    assert out and "Consensus reached." in out[0].text


def test_ch08_01_MISMATCH_groupchat_has_no_with_orchestrator_method():
    """Book 8.1/8.4: '.with_orchestrator(agent=manager)'. In 1.21.0 the manager is passed to the constructor:
    GroupChatBuilder(participants=[...], orchestrator_agent=manager)."""
    assert not hasattr(GroupChatBuilder, "with_orchestrator")
    assert "orchestrator_agent" in __import__("inspect").signature(GroupChatBuilder.__init__).parameters


# ================================================================== 8.1/8.4 MagenticBuilder (chapter_08_02)
def ledger(satisfied=False, speaker="researcher", instruction="do it", progress=True, loop=False):
    item = lambda a: {"reason": "r", "answer": a}  # noqa: E731
    return Reply.text(
        json.dumps(
            dict(
                is_request_satisfied=item(satisfied),
                is_in_loop=item(loop),
                is_progress_being_made=item(progress),
                next_speaker=item(speaker),
                instruction_or_question=item(instruction),
            )
        )
    )


def manager_script(**ledger_kw):
    """Scripted manager: JSON progress ledger when asked for one, otherwise prose (facts / plan / final answer)."""
    calls = {"ledger": 0, "prose": 0}

    def script(messages):
        last = messages[-1].text
        if "is_request_satisfied" in last:
            calls["ledger"] += 1
            return ledger(**ledger_kw)
        calls["prose"] += 1
        return Reply.text(f"prose#{calls['prose']}")

    return script, calls


def build_magentic(manager_client_script, participants, **limits):
    mgr = Agent(client=ScriptedChatClient(manager_client_script), name="manager", id="manager", instructions="manage")
    return MagenticBuilder(participants=participants, manager_agent=mgr, **limits).build()


async def test_ch08_01_magentic_plans_delegates_then_synthesizes_final_answer():
    researcher, rc = make_agent("researcher", Reply.text("found three facts"))
    coder, cc = make_agent("coder", Reply.text("code"))
    script = [
        Reply.text("facts"),
        Reply.text("plan"),
        ledger(speaker="researcher", instruction="collect facts"),
        ledger(satisfied=True),
        Reply.text("FINAL: here is the answer"),
    ]
    wf = build_magentic(script, [researcher, coder], max_round_count=10, max_stall_count=3, max_reset_count=2)  # chapter_08_02
    events = []
    async for ev in wf.run("investigate", stream=True):
        events.append(ev)
    kinds = [e.data.event_type.name for e in events if e.type == "magentic_orchestrator"]
    assert kinds[0] == "PLAN_CREATED" and kinds.count("PROGRESS_LEDGER_UPDATED") == 2
    assert len(rc.requests) == 1 and cc.requests == []  # only the delegated specialist ran
    assert "collect facts" in [m.text for m in rc.requests[0]]  # manager's instruction reached it
    outs = [e.data.text for e in events if e.type == "output"]
    assert outs[-1] == "FINAL: here is the answer"


async def test_ch08_04_magentic_max_round_count_is_a_hard_cap():
    researcher, rc = make_agent("researcher", *[Reply.text(f"r{i}") for i in range(20)])
    script, calls = manager_script(satisfied=False, speaker="researcher", progress=True)
    wf = build_magentic(script, [researcher], max_round_count=2, max_stall_count=5, max_reset_count=5)
    result = await wf.run("never ends")
    assert len(rc.requests) == 2
    assert result.get_outputs()[-1].text == "Workflow terminated due to reaching maximum round count."


async def test_ch08_04_magentic_stall_detection_triggers_replan_and_reset_cap_gives_up():
    researcher, rc = make_agent("researcher", *[Reply.text(f"r{i}") for i in range(20)])
    script, calls = manager_script(satisfied=False, speaker="researcher", progress=False)  # never progresses
    wf = build_magentic(script, [researcher], max_round_count=50, max_stall_count=1, max_reset_count=1)
    events = [e async for e in wf.run("stuck", stream=True)]
    kinds = [e.data.event_type.name for e in events if e.type == "magentic_orchestrator"]
    assert "REPLANNED" in kinds  # stall -> reset & replan
    final = [e.data.text for e in events if e.type == "output"][-1]
    assert final == "Workflow terminated due to reaching maximum reset count."
    assert len(rc.requests) < 50  # bounded by stall/reset caps, not by the 50-round cap


# ================================================================== 8.1 'five builders, one underlying idea'
async def test_ch08_01_builders_produce_plain_workflows_and_as_agent_works():
    a, _ = make_agent("a", Reply.text("A"))
    b, _ = make_agent("b", Reply.text("B"))
    wf = SequentialBuilder(participants=[a, b]).build()
    assert type(wf).__name__ == "Workflow"  # a regular Workflow: checkpoints/streaming/HITL all apply
    agent = wf.as_agent(name="pipeline")  # the workflow_as_agent variant
    resp = await agent.run("hello")
    assert resp.text.endswith("B")


async def test_ch08_01_builders_accept_checkpoint_storage():
    from agent_framework import InMemoryCheckpointStorage

    st = InMemoryCheckpointStorage()
    a, _ = make_agent("a", Reply.text("A"))
    b, _ = make_agent("b", Reply.text("B"))
    wf = SequentialBuilder(participants=[a, b], name="seq", checkpoint_storage=st).build()
    await wf.run("x")
    assert len(await st.list_checkpoints(workflow_name="seq")) >= 2


# ================================================================== 8.3 agent as MCP server
def test_ch08_03_agent_can_be_exposed_as_mcp_server():
    a, _ = make_agent("a", Reply.text("A"))
    server = a.as_mcp_server()
    assert type(server).__module__.startswith("mcp")


def test_ch08_05_MISMATCH_magentic_has_no_with_request_info_use_plan_review():
    """Book 8.5 (line 63) says a human can be inserted via 'with_request_info()' on the Magentic team.
    MagenticBuilder has no such method; the equivalent is enable_plan_review / .with_plan_review()."""
    assert not hasattr(MagenticBuilder, "with_request_info")
    assert hasattr(MagenticBuilder, "with_plan_review")


async def test_ch08_05_magentic_plan_review_pauses_for_human_before_acting():
    from agent_framework.orchestrations import MagenticPlanReviewRequest

    researcher, rc = make_agent("researcher", Reply.text("found it"))
    mgr = Agent(
        client=ScriptedChatClient([Reply.text("facts"), Reply.text("plan"), ledger(True), Reply.text("FINAL")]),
        name="manager", id="manager", instructions="manage",
    )
    wf = MagenticBuilder(participants=[researcher], manager_agent=mgr, enable_plan_review=True).build()
    first = await wf.run("task")
    reqs = first.get_request_info_events()
    assert len(reqs) == 1 and isinstance(reqs[0].data, MagenticPlanReviewRequest)
    assert rc.requests == []  # nothing executed before the human signs off
    final = await wf.run(responses={reqs[0].request_id: reqs[0].data.approve()})
    assert final.get_outputs()[-1].text == "FINAL"
