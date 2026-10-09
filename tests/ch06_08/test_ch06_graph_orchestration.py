"""Chapter 6 - Graph-Based Orchestration. Executes every snippet (chapter_06_01 .. 06) offline."""
from __future__ import annotations

import warnings
from typing import Any

import pytest
from pydantic import BaseModel
from typing_extensions import Never

from agent_framework import (
    AgentExecutorRequest,
    AgentExecutorResponse,
    AgentResponseUpdate,
    Case,
    Default,
    Executor,
    Message,
    WorkflowBuilder,
    WorkflowContext,
    WorkflowExecutor,
    WorkflowViz,
    executor,
    handler,
)
from support.fake_client import Reply

from ch0608_helpers import make_agent


# --------------------------------------------------------------------------- 6.2 chapter_06_01..03
class UpperCase(Executor):  # chapter_06_01 verbatim
    @handler
    async def to_upper_case(self, text: str, ctx: WorkflowContext[str]) -> None:
        await ctx.send_message(text.upper())


@executor(id="reverse_text_executor")  # chapter_06_02 verbatim
async def reverse_text(text: str, ctx: WorkflowContext[Never, str]) -> None:
    await ctx.yield_output(text[::-1])


async def test_ch06_02_executors_and_edges_chapter_06_03():
    upper_case = UpperCase(id="upper_case_executor")
    workflow = WorkflowBuilder(start_executor=upper_case).add_edge(upper_case, reverse_text).build()  # chapter_06_03
    result = await workflow.run("hello world")
    assert result.get_outputs() == ["DLROW OLLEH"]  # the book's inline comment


def test_executor_requires_explicit_id():
    """Book snippet 06_01 never shows how UpperCase is instantiated. Executor.__init__ needs an id."""
    with pytest.raises(TypeError, match="id"):
        UpperCase()  # type: ignore[call-arg]


def test_function_executor_keeps_decorator_id():
    assert reverse_text.id == "reverse_text_executor"


def test_context_generics_declare_data_flow():
    """'Reading a workflow's node signatures tells you its data flow' -> introspect declared types."""
    upper = UpperCase(id="u")
    assert upper.output_types == [str]  # WorkflowContext[str]: forwards str downstream
    assert upper.workflow_output_types == []  # ...and yields nothing
    assert reverse_text.output_types == []  # WorkflowContext[Never, str]: forwards nothing
    assert reverse_text.workflow_output_types == [str]  # ...but yields str as workflow output


async def test_factory_function_gives_fresh_state_per_run():
    """'Wrapping construction in create_workflow() ... each run gets fresh executor instances'."""

    class Counter(Executor):
        def __init__(self) -> None:
            super().__init__(id="counter")
            self.calls = 0

        @handler
        async def go(self, text: str, ctx: WorkflowContext[Never, int]) -> None:
            self.calls += 1
            await ctx.yield_output(self.calls)

    def create_workflow():
        c = Counter()
        return WorkflowBuilder(start_executor=c).build()

    shared = create_workflow()
    assert (await shared.run("a")).get_outputs() == [1]
    assert (await shared.run("b")).get_outputs() == [2]  # module-level singleton leaks state
    assert (await create_workflow().run("c")).get_outputs() == [1]  # factory does not


# --------------------------------------------------------------------------- 6.3 chapter_06_04
async def test_ch06_04_streaming_agents_in_workflow():
    writer_agent, _ = make_agent("writer", Reply.text("Drive the future."))
    reviewer_agent, rc = make_agent("reviewer", Reply.text("Approved."))
    workflow = WorkflowBuilder(start_executor=writer_agent).add_edge(writer_agent, reviewer_agent).build()

    printed: list[tuple[str, str]] = []
    types_seen: list[str] = []
    async for event in workflow.run(  # chapter_06_04
        Message("user", ["Create a slogan for a new electric SUV."]),
        stream=True,
    ):
        types_seen.append(event.type)
        if event.type == "output" and isinstance(event.data, AgentResponseUpdate):
            update = event.data
            printed.append((update.author_name, update.text))

    assert printed == [("writer", "Drive the future."), ("reviewer", "Approved.")]  # author_name identifies node
    assert {"started", "output", "executor_invoked", "executor_completed"} <= set(types_seen)
    # the reviewer actually saw the writer's output (shared conversation along the edge)
    seen = [m.text for m in rc.requests[0]]
    assert "Drive the future." in seen


# --------------------------------------------------------------------------- 6.4 chapter_06_05
class DetectionResult(BaseModel):
    is_spam: bool
    reason: str


def get_condition(expected_result: bool):  # chapter_06_05 verbatim
    def condition(message: Any) -> bool:
        if not isinstance(message, AgentExecutorResponse):
            return True
        try:
            detection = DetectionResult.model_validate_json(message.agent_response.text)
            return detection.is_spam == expected_result
        except Exception:
            return False  # fail closed: don't route on a parse error

    return condition


def build_spam_workflow(detector_reply: str):
    spam_detection_agent, _ = make_agent(
        "spam_detector", Reply.text(detector_reply), default_options={"response_format": DetectionResult}
    )
    email_agent, email_client = make_agent("email_assistant", Reply.text("Dear sender, thanks."))

    @executor(id="to_email_assistant_request")
    async def to_email_assistant_request(
        response: AgentExecutorResponse, ctx: WorkflowContext[AgentExecutorRequest]
    ) -> None:
        await ctx.send_message(AgentExecutorRequest(messages=[Message("user", ["Draft a reply"])], should_respond=True))

    @executor(id="handle_spam_classifier_response")
    async def handle_spam_classifier_response(
        response: AgentExecutorResponse, ctx: WorkflowContext[Never, str]
    ) -> None:
        await ctx.yield_output("SPAM BLOCKED")

    @executor(id="finalize")
    async def finalize(response: AgentExecutorResponse, ctx: WorkflowContext[Never, str]) -> None:
        await ctx.yield_output(f"EMAIL SENT: {response.agent_response.text}")

    workflow = (
        # output_from keeps agent nodes' own AgentResponse out of the caller-facing output (see 6.6)
        WorkflowBuilder(start_executor=spam_detection_agent, output_from=[finalize, handle_spam_classifier_response])
        .add_edge(spam_detection_agent, to_email_assistant_request, condition=get_condition(False))
        .add_edge(spam_detection_agent, handle_spam_classifier_response, condition=get_condition(True))
        .add_edge(to_email_assistant_request, email_agent)
        .add_edge(email_agent, finalize)
        .build()
    )
    return workflow, email_client


async def test_ch06_05_condition_routes_non_spam_to_email_branch():
    wf, email_client = build_spam_workflow('{"is_spam": false, "reason": "normal mail"}')
    result = await wf.run("Hi, lunch tomorrow?")
    assert result.get_outputs() == ["EMAIL SENT: Dear sender, thanks."]
    assert len(email_client.requests) == 1


async def test_ch06_05_condition_routes_spam_to_spam_branch():
    wf, email_client = build_spam_workflow('{"is_spam": true, "reason": "lottery"}')
    result = await wf.run("You won a million dollars")
    assert result.get_outputs() == ["SPAM BLOCKED"]
    assert email_client.requests == []  # the other branch never ran


async def test_ch06_05_condition_fails_closed_on_parse_error():
    """'fail closed on a parse error (return False, don't route)': neither branch fires."""
    wf, email_client = build_spam_workflow("this is not json at all")
    result = await wf.run("??")
    assert result.get_outputs() == []
    assert email_client.requests == []


def test_ch06_05_condition_passes_non_agent_messages():
    assert get_condition(True)("plain string") is True
    assert get_condition(False)("plain string") is True


async def test_ch06_05_response_format_gives_structured_value():
    """Book: spam_detection_agent returns a DetectionResult via response_format (parsed .value)."""
    agent, _ = make_agent(
        "spam_detector",
        Reply.text('{"is_spam": true, "reason": "x"}'),
        default_options={"response_format": DetectionResult},
    )
    resp = await agent.run("hello")
    assert isinstance(resp.value, DetectionResult) and resp.value.is_spam is True


async def test_ch06_04_switch_case_and_multi_selection():
    """Prose: switch_case / multi_selection extend the same idea (dispatch to one / a subset of targets)."""

    @executor(id="router")
    async def router(text: str, ctx: WorkflowContext[str]) -> None:
        await ctx.send_message(text)

    def sink(name: str):
        @executor(id=name)
        async def _s(text: str, ctx: WorkflowContext[Never, str]) -> None:
            await ctx.yield_output(f"{name}:{text}")

        return _s

    small, big, other = sink("small"), sink("big"), sink("other")
    wf = (
        WorkflowBuilder(start_executor=router)
        .add_switch_case_edge_group(
            router,
            [
                Case(condition=lambda m: len(m) < 3, target=small),
                Case(condition=lambda m: len(m) < 6, target=big),
                Default(target=other),
            ],
        )
        .build()
    )
    assert (await wf.run("ab")).get_outputs() == ["small:ab"]
    assert (await wf.run("abcd")).get_outputs() == ["big:abcd"]
    assert (await wf.run("abcdefgh")).get_outputs() == ["other:abcdefgh"]

    a, b, c = sink("a"), sink("b"), sink("c")
    wf2 = (
        WorkflowBuilder(start_executor=router)
        .add_multi_selection_edge_group(
            router,
            [a, b, c],
            selection_func=lambda msg, targets: [t for t in targets if t in ("a", "c")] if msg == "ac" else targets[:1],
        )
        .build()
    )
    assert sorted((await wf2.run("ac")).get_outputs()) == ["a:ac", "c:ac"]
    assert (await wf2.run("zz")).get_outputs() == ["a:zz"]


# --------------------------------------------------------------------------- 6.5 chapter_06_06
async def test_ch06_06_fan_out_fan_in_is_a_join_not_a_race():
    @executor(id="dispatcher")
    async def dispatcher(prompt: str, ctx: WorkflowContext[AgentExecutorRequest]) -> None:
        await ctx.send_message(AgentExecutorRequest(messages=[Message("user", [prompt])], should_respond=True))

    researcher, rcl = make_agent("researcher", Reply.text("research view"), Reply.text("research view"))
    marketer, mcl = make_agent("marketer", Reply.text("marketing view"), Reply.text("marketing view"))
    legal, lcl = make_agent("legal", Reply.text("legal view"), Reply.text("legal view"))

    calls: list[list[str]] = []

    @executor(id="aggregator")
    async def aggregator(results: list[AgentExecutorResponse], ctx: WorkflowContext[Never, str]) -> None:
        calls.append(sorted(r.executor_id for r in results))
        await ctx.yield_output(" | ".join(sorted(r.agent_response.text for r in results)))

    workflow = (  # chapter_06_06
        WorkflowBuilder(start_executor=dispatcher, output_from=[aggregator])
        .add_fan_out_edges(dispatcher, [researcher, marketer, legal])  # parallel branches
        .add_fan_in_edges([researcher, marketer, legal], aggregator)  # join point
        .build()
    )
    result = await workflow.run("Launch an electric SUV")
    assert result.get_outputs() == ["legal view | marketing view | research view"]
    assert calls == [["legal", "marketer", "researcher"]]  # fires exactly once, after all three
    # every branch received the same prompt independently
    for c in (rcl, mcl, lcl):
        assert [m.text for m in c.requests[0]][-1] == "Launch an electric SUV"
    # ordering evidence: aggregator invoked only after all three agents completed
    events = [e for e in await workflow.run("again") if e.type in ("executor_completed", "executor_invoked")]
    agg_idx = next(i for i, e in enumerate(events) if e.executor_id == "aggregator" and e.type == "executor_invoked")
    done_before = {e.executor_id for e in events[:agg_idx] if e.type == "executor_completed"}
    assert {"researcher", "marketer", "legal"} <= done_before


def test_ch06_workflow_viz_mermaid_export():
    """'framework's workflow-diagram export': mermaid works without graphviz installed."""
    a, b = UpperCase(id="a"), reverse_text
    wf = WorkflowBuilder(start_executor=a).add_edge(a, b).build()
    text = WorkflowViz(wf).to_mermaid()
    assert "reverse_text_executor" in text and "-->" in text


# --------------------------------------------------------------------------- 6.6 composition + output selection
async def test_sub_workflow_is_a_single_node_in_parent():
    inner_up = UpperCase(id="inner_upper")

    @executor(id="inner_out")
    async def inner_out(t: str, ctx: WorkflowContext[Never, str]) -> None:
        await ctx.yield_output(t + "!")

    inner = WorkflowBuilder(start_executor=inner_up).add_edge(inner_up, inner_out).build()
    sub = WorkflowExecutor(inner, id="sub")

    @executor(id="after")
    async def after(t: str, ctx: WorkflowContext[Never, str]) -> None:
        await ctx.yield_output(f"parent got {t}")

    @executor(id="entry")
    async def entry(t: str, ctx: WorkflowContext[str]) -> None:
        await ctx.send_message(t)

    parent = WorkflowBuilder(start_executor=entry).add_edge(entry, sub).add_edge(sub, after).build()
    result = await parent.run("hey")
    assert result.get_outputs() == ["parent got HEY!"]
    assert {e.executor_id for e in result if e.type == "executor_invoked"} == {"entry", "sub", "after"}


def _two_step():
    @executor(id="step_a")
    async def step_a(t: str, ctx: WorkflowContext[str, str]) -> None:
        await ctx.yield_output("A:" + t)
        await ctx.send_message(t + "1")

    @executor(id="step_b")
    async def step_b(t: str, ctx: WorkflowContext[Never, str]) -> None:
        await ctx.yield_output("B:" + t)

    return step_a, step_b


async def test_default_every_yield_output_is_workflow_output():
    a, b = _two_step()
    wf = WorkflowBuilder(start_executor=a).add_edge(a, b).build()
    assert (await wf.run("x")).get_outputs() == ["A:x", "B:x1"]


async def test_output_from_is_an_allow_list_and_others_are_hidden():
    a, b = _two_step()
    wf = WorkflowBuilder(start_executor=a, output_from=[b]).add_edge(a, b).build()
    result = await wf.run("x")
    assert result.get_outputs() == ["B:x1"]
    assert [e for e in result if e.type == "intermediate"] == []  # hidden entirely, not intermediate


async def test_intermediate_output_from_exposes_progress_events():
    a, b = _two_step()
    wf = WorkflowBuilder(start_executor=a, output_from=[b], intermediate_output_from=[a]).add_edge(a, b).build()
    result = await wf.run("x")
    assert result.get_outputs() == ["B:x1"]
    inter = [e for e in result if e.type == "intermediate"]
    assert [(e.executor_id, e.data) for e in inter] == [("step_a", "A:x")]


async def test_omitting_both_selections_does_NOT_warn_in_1_21_0():
    """MISMATCH vs book 6.6: 'Omitting both selections ... emits a deprecation warning'.
    In agent-framework 1.21.0 omitting both is the documented default ('every yield_output emits output')
    and no warning is raised at build or run time."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        a, b = _two_step()
        wf = WorkflowBuilder(start_executor=a).add_edge(a, b).build()
        await wf.run("x")
    assert [w for w in caught if "output" in str(w.message).lower() or "deprecat" in str(w.message).lower()] == []


async def test_agent_nodes_also_emit_output_by_default():
    """Observed in 1.21.0: with no output selection, an Agent node's AgentResponse is workflow output too,
    so 6.6's 'every output is visible by default' applies to agent nodes as well as yield_output executors."""
    a, _ = make_agent("a", Reply.text("hi"))
    wf = WorkflowBuilder(start_executor=a).build()
    outs = (await wf.run("x")).get_outputs()
    assert len(outs) == 1 and outs[0].text == "hi"
    with pytest.raises(Exception, match="at least one output or intermediate executor"):
        WorkflowBuilder(start_executor=a, output_from=[]).build()  # an empty allow-list is rejected at build()
