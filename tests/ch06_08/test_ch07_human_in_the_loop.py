"""Chapter 7 - Human-in-the-Loop & Time-Travel. Executes checkpoints, request_info, resume, replay offline."""
from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any

import pytest
from typing_extensions import Never

from agent_framework import (
    AgentExecutorResponse,
    Executor,
    FileCheckpointStorage,
    InMemoryCheckpointStorage,
    Message,
    WorkflowBuilder,
    WorkflowContext,
    handler,
    response_handler,
)
from agent_framework.orchestrations import (
    AgentRequestInfoResponse,
    ConcurrentBuilder,
    GroupChatBuilder,
    HandoffBuilder,
    SequentialBuilder,
)
from support.fake_client import Reply

from ch0608_helpers import make_agent


# ---------------------------------------------------------------- 7.2 chapter_07_01 (start / worker)
class Start(Executor):
    @handler
    async def go(self, text: str, ctx: WorkflowContext[str]) -> None:
        await ctx.send_message(text + "|start")


class Worker(Executor):
    @handler
    async def go(self, text: str, ctx: WorkflowContext[Never, str]) -> None:
        await ctx.yield_output(text + "|worker")


async def test_ch07_01_checkpoint_storage_and_resume_via_run():
    start, worker = Start(id="start"), Worker(id="worker")
    checkpoint_storage = InMemoryCheckpointStorage()
    workflow = (  # chapter_07_01
        WorkflowBuilder(start_executor=start, checkpoint_storage=checkpoint_storage)
        .add_edge(start, worker)
        .build()
    )
    result = await workflow.run("hi")
    assert result.get_outputs() == ["hi|start|worker"]

    latest_checkpoint = await checkpoint_storage.get_latest(workflow_name=workflow.name)
    assert latest_checkpoint is not None
    line = f"Checkpoint {latest_checkpoint.checkpoint_id}: iter={latest_checkpoint.iteration_count}"
    assert line.startswith("Checkpoint ") and "iter=" in line
    assert latest_checkpoint.iteration_count >= 2  # start -> worker -> (final)

    # 'Resuming is nothing more exotic than passing a checkpoint_id back into the same run call'
    seen = []
    async for event in workflow.run(checkpoint_id=latest_checkpoint.checkpoint_id, stream=True):
        seen.append(event.type)
    assert "started" in seen  # the run actually executed (stream completed without error)


async def test_ch07_01_checkpoint_per_step_and_ordering():
    """'the framework captures the workflow's state at each step automatically'."""
    start, worker = Start(id="start"), Worker(id="worker")
    st = InMemoryCheckpointStorage()
    wf = WorkflowBuilder(start_executor=start, checkpoint_storage=st).add_edge(start, worker).build()
    await wf.run("x")
    cps = await st.list_checkpoints(workflow_name=wf.name)
    assert len(cps) >= 3
    its = [c.iteration_count for c in sorted(cps, key=lambda c: c.timestamp)]
    assert its == sorted(its) and its[0] < its[-1]
    # checkpoints chain through previous_checkpoint_id
    by_id = {c.checkpoint_id: c for c in cps}
    chain_roots = [c for c in cps if c.previous_checkpoint_id is None]
    assert len(chain_roots) == 1
    assert all(c.previous_checkpoint_id in by_id for c in cps if c.previous_checkpoint_id)
    assert (await st.get_latest(workflow_name=wf.name)).iteration_count == max(its)


# ---------------------------------------------------------------- 7.3 chapter_07_02 (ReviewerGateway)
@dataclass
class HumanApprovalRequest:
    prompt: str
    draft: str


class ReviewerGateway(Executor):
    """chapter_07_02 with the '...' body filled in: approve -> output, otherwise echo the edit instructions."""

    @handler
    async def on_agent_response(self, response: AgentExecutorResponse, ctx: WorkflowContext) -> None:  # chapter_07_02
        await ctx.request_info(
            request_data=HumanApprovalRequest(
                prompt="Review the draft. Reply 'approve' or provide edit instructions.",
                draft=response.agent_response.text,
            ),
            response_type=str,
        )

    @response_handler
    async def on_human_feedback(
        self, original_request: HumanApprovalRequest, feedback: str, ctx: WorkflowContext[Never, str]
    ) -> None:
        if feedback.strip().lower() == "approve":
            await ctx.yield_output(f"APPROVED: {original_request.draft}")
        else:
            await ctx.yield_output(f"EDIT REQUESTED: {feedback} (draft was: {original_request.draft})")


HITL_TYPE = f"{HumanApprovalRequest.__module__}:{HumanApprovalRequest.__qualname__}"


def build_hitl(storage: InMemoryCheckpointStorage | FileCheckpointStorage | None = None, name: str = "hitl"):
    writer, client = make_agent("writer", Reply.text("First draft of the memo."))
    gateway = ReviewerGateway(id="reviewer_gateway")
    wf = WorkflowBuilder(
        name=name, start_executor=writer, checkpoint_storage=storage, output_from=[gateway]
    ).add_edge(writer, gateway).build()
    return wf, client


async def test_ch07_02_request_info_surfaces_as_event_and_pauses():
    wf, _ = build_hitl()
    reqs, outputs = [], []
    async for ev in wf.run("write a memo", stream=True):
        if ev.type == "request_info":  # 'event.type == "request_info"' per the book
            reqs.append(ev)
        if ev.type == "output":
            outputs.append(ev.data)
    assert len(reqs) == 1 and outputs == []  # paused: nothing finished
    assert isinstance(reqs[0].data, HumanApprovalRequest)
    assert reqs[0].data.draft == "First draft of the memo."
    assert reqs[0].data.prompt.startswith("Review the draft")
    assert reqs[0].request_id
    assert wf.status if hasattr(wf, "status") else True


async def test_ch07_02_workflow_state_is_idle_with_pending_requests():
    wf, _ = build_hitl()
    r = await wf.run("write a memo")
    assert str(r.get_final_state()) == "WorkflowRunState.IDLE_WITH_PENDING_REQUESTS"
    assert len(r.get_request_info_events()) == 1


@pytest.mark.parametrize(
    "answer,expected",
    [("approve", "APPROVED: First draft of the memo."), ("shorter please", "EDIT REQUESTED: shorter please")],
)
async def test_ch07_02_response_resumes_branch_and_routes(answer, expected):
    wf, _ = build_hitl()
    first = await wf.run("write a memo")
    req = first.get_request_info_events()[0]
    final = await wf.run(responses={req.request_id: answer})
    out = final.get_outputs()
    assert len(out) == 1 and out[0].startswith(expected)
    assert str(final.get_final_state()) == "WorkflowRunState.IDLE"


async def test_ch07_02_waiting_is_checkpointed_and_survives_a_restart_in_file_storage(tmp_path):
    """'the moment a workflow is waiting on a human, it's also checkpointed' + restart survival."""
    storage = FileCheckpointStorage(tmp_path, allowed_checkpoint_types=[HITL_TYPE])
    wf, _ = build_hitl(storage)
    first = await wf.run("write a memo")
    req = first.get_request_info_events()[0]

    latest = await storage.get_latest(workflow_name="hitl")
    assert latest is not None
    assert req.request_id in latest.pending_request_info_events  # pending approval is IN the checkpoint

    # --- 'process restart': brand new storage object, brand new workflow + executor instances ---
    storage2 = FileCheckpointStorage(tmp_path, allowed_checkpoint_types=[HITL_TYPE])
    wf2, _ = build_hitl(storage2)
    latest2 = await storage2.get_latest(workflow_name="hitl")
    assert latest2.checkpoint_id == latest.checkpoint_id
    resumed = await wf2.run(checkpoint_id=latest2.checkpoint_id, responses={req.request_id: "approve"})
    assert resumed.get_outputs() == ["APPROVED: First draft of the memo."]


async def test_ch07_02_pending_requests_are_re_emitted_when_resuming_without_answer():
    st = InMemoryCheckpointStorage()
    wf, _ = build_hitl(st)
    first = await wf.run("write a memo")
    req = first.get_request_info_events()[0]
    latest = await st.get_latest(workflow_name="hitl")
    again = await wf.run(checkpoint_id=latest.checkpoint_id)
    reqs = again.get_request_info_events()
    assert [r.request_id for r in reqs] == [req.request_id]


# ---------------------------------------------------------------- 7.4 time travel
async def test_ch07_04_time_travel_resume_from_an_earlier_checkpoint():
    """list_checkpoints returns every checkpoint; resuming from an earlier one replays from that point."""

    class Counting(Executor):
        runs = 0

        @handler
        async def go(self, text: str, ctx: WorkflowContext[Never, str]) -> None:
            type(self).runs += 1
            await ctx.yield_output(f"{text}|worker#{type(self).runs}")

    Counting.runs = 0
    st = InMemoryCheckpointStorage()
    start, worker = Start(id="start"), Counting(id="worker")
    wf = WorkflowBuilder(start_executor=start, checkpoint_storage=st).add_edge(start, worker).build()
    assert (await wf.run("x")).get_outputs() == ["x|start|worker#1"]

    cps = sorted(await st.list_checkpoints(workflow_name=wf.name), key=lambda c: c.iteration_count)
    assert len(cps) >= 3
    # pick the checkpoint taken after `start` ran but before `worker` ran
    mid = next(c for c in cps if c.messages and "start" in c.messages and c.iteration_count < cps[-1].iteration_count)
    assert mid.checkpoint_id != cps[-1].checkpoint_id

    replay = await wf.run(checkpoint_id=mid.checkpoint_id)
    assert replay.get_outputs() == ["x|start|worker#2"]  # worker executed AGAIN from the older state
    assert Counting.runs == 2

    # resuming from the newest checkpoint does not re-run the worker
    latest = cps[-1]
    again = await wf.run(checkpoint_id=latest.checkpoint_id)
    assert again.get_outputs() == []
    assert Counting.runs == 2


async def test_ch07_04_checkpoint_carries_iteration_messages_and_executor_state():
    """'iteration_count, accumulated messages, and executor-level state via checkpoint hooks'."""

    class Stateful(Executor):
        def __init__(self, id: str) -> None:
            super().__init__(id=id)
            self.seen: list[str] = []

        @handler
        async def go(self, text: str, ctx: WorkflowContext[str]) -> None:
            self.seen.append(text)
            await ctx.send_message(text)

        async def on_checkpoint_save(self) -> dict[str, Any]:
            return {"seen": list(self.seen)}

        async def on_checkpoint_restore(self, state: dict[str, Any]) -> None:
            self.seen = list(state["seen"])

    st = InMemoryCheckpointStorage()
    s, w = Stateful("stateful"), Worker(id="worker")
    wf = WorkflowBuilder(start_executor=s, checkpoint_storage=st).add_edge(s, w).build()
    await wf.run("payload")
    cps = await st.list_checkpoints(workflow_name=wf.name)
    assert any(c.state.get("stateful") or any("seen" in str(v) for v in c.state.values()) for c in cps)
    assert any(c.messages for c in cps) and all(isinstance(c.iteration_count, int) for c in cps)

    # restore hook round-trips on resume in a fresh instance
    s2, w2 = Stateful("stateful"), Worker(id="worker")
    wf2 = WorkflowBuilder(start_executor=s2, checkpoint_storage=st).add_edge(s2, w2).build()
    latest = await st.get_latest(workflow_name=wf.name)
    await wf2.run(checkpoint_id=latest.checkpoint_id)
    assert s2.seen == ["payload"]


def test_ch07_02_cosmos_checkpoint_storage_importable_without_credentials():
    """Book points at cosmos_workflow_checkpointing.py (CosmosCheckpointStorage). Import only - needs Azure to use."""
    from agent_framework_azure_cosmos import CosmosCheckpointStorage  # noqa: F401

    assert inspect.isclass(CosmosCheckpointStorage)


# ---------------------------------------------------------------- 7.3 closing paragraph: .with_request_info()
async def test_ch07_03_sequential_with_request_info_pauses_after_agent_and_resumes():
    a, ca = make_agent("a", Reply.text("A out"))
    b, cb = make_agent("b", Reply.text("B out"))
    wf = SequentialBuilder(participants=[a, b]).with_request_info(agents=[a]).build()
    first = await wf.run("go")
    reqs = first.get_request_info_events()
    assert len(reqs) == 1 and cb.requests == []  # b has not run: paused after a
    final = await wf.run(responses={reqs[0].request_id: AgentRequestInfoResponse.approve()})
    assert final.get_outputs()[0].text == "B out"
    assert len(cb.requests) == 1


async def test_ch07_03_sequential_with_request_info_human_feedback_reaches_next_agent():
    a, ca = make_agent("a", Reply.text("A out"), Reply.text("A revised"))
    b, cb = make_agent("b", Reply.text("B out"))
    wf = SequentialBuilder(participants=[a, b]).with_request_info(agents=[a]).build()
    first = await wf.run("go")
    req = first.get_request_info_events()[0]
    second = await wf.run(responses={req.request_id: AgentRequestInfoResponse.from_strings(["make it shorter"])})
    # human feedback re-prompts agent a (its client now got a second request containing the feedback)
    assert len(ca.requests) == 2
    assert "make it shorter" in [m.text for m in ca.requests[1]]
    assert len(second.get_request_info_events()) == 1  # a's revised answer is again up for review


async def test_ch07_03_concurrent_and_groupchat_expose_with_request_info():
    a, _ = make_agent("a", Reply.text("A"))
    b, _ = make_agent("b", Reply.text("B"))
    wf = ConcurrentBuilder(participants=[a, b]).with_request_info().build()
    r = await wf.run("q")
    assert len(r.get_request_info_events()) == 2  # one review request per participant
    assert hasattr(GroupChatBuilder, "with_request_info")


def test_ch07_03_MISMATCH_handoffbuilder_has_no_with_request_info():
    """Book 7.3 says SequentialBuilder, ConcurrentBuilder, GroupChatBuilder AND HandoffBuilder all expose
    .with_request_info(). In 1.21.0 (orchestrations 1.3.1) HandoffBuilder does not; it pauses for the user by itself
    (HandoffAgentUserRequest) unless autonomous mode is enabled."""
    assert not hasattr(HandoffBuilder, "with_request_info")
    for cls in (SequentialBuilder, ConcurrentBuilder, GroupChatBuilder):
        assert hasattr(cls, "with_request_info")


# ---------------------------------------------------------------- 7.5 observability
async def test_ch07_05_executor_invoked_and_completed_events_expose_io_without_touching_executors():
    start, worker = Start(id="start"), Worker(id="worker")
    wf = WorkflowBuilder(start_executor=start).add_edge(start, worker).build()
    log = []
    async for ev in wf.run("in", stream=True):
        if ev.type in ("executor_invoked", "executor_completed"):
            log.append((ev.type, ev.executor_id, ev.data))
    assert log == [
        ("executor_invoked", "start", "in"),
        ("executor_completed", "start", ["in|start"]),
        ("executor_invoked", "worker", "in|start"),
        ("executor_completed", "worker", ["in|start|worker"]),
    ]


async def test_ch07_02_GOTCHA_file_storage_silently_drops_checkpoint_with_custom_request_type(tmp_path, caplog):
    """Not in the book: a durable FileCheckpointStorage refuses to deserialize your own HumanApprovalRequest unless
    it is listed in allowed_checkpoint_types. The run does NOT fail; the pending-approval checkpoint is just not
    written (only a logged warning), so 'waiting == checkpointed' silently does not hold."""
    storage = FileCheckpointStorage(tmp_path)  # no allow-list
    wf, _ = build_hitl(storage)
    first = await wf.run("write a memo")
    req = first.get_request_info_events()[0]
    latest = await storage.get_latest(workflow_name="hitl")
    assert req.request_id not in latest.pending_request_info_events
    assert any("Failed to create checkpoint" in r.message for r in caplog.records)


async def test_ch07_02_GOTCHA_unnamed_workflow_name_is_random_per_instance():
    """Book 7.2 calls get_latest(workflow_name=workflow.name). For a *restart* you must give the builder a stable
    name=...; otherwise the rebuilt workflow gets a new random name and finds no checkpoints."""
    st = InMemoryCheckpointStorage()
    s1, w1 = Start(id="start"), Worker(id="worker")
    wf1 = WorkflowBuilder(start_executor=s1, checkpoint_storage=st).add_edge(s1, w1).build()
    await wf1.run("x")
    s2, w2 = Start(id="start"), Worker(id="worker")
    wf2 = WorkflowBuilder(start_executor=s2, checkpoint_storage=st).add_edge(s2, w2).build()
    assert wf1.name != wf2.name
    assert await st.get_latest(workflow_name=wf2.name) is None
    assert await st.get_latest(workflow_name=wf1.name) is not None
