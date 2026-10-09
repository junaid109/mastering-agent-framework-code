"""Ch 7: request_info approval, durable checkpoints, restart-resume and time-travel (chapter_07_01, chapter_07_02)."""
import asyncio
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root, for support.fake_client

from typing_extensions import Never

from agent_framework import (
    Agent,
    AgentExecutorResponse,
    Executor,
    FileCheckpointStorage,
    InMemoryCheckpointStorage,
    WorkflowBuilder,
    WorkflowContext,
    handler,
    response_handler,
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


@dataclass
class HumanApprovalRequest:
    prompt: str
    draft: str


# NB: a durable FileCheckpointStorage only deserializes custom types you allow-list (not mentioned in the book).
ALLOWED = [f"{HumanApprovalRequest.__module__}:{HumanApprovalRequest.__qualname__}"]
if __name__ == "__main__":  # when run as a script the module name is __main__
    ALLOWED = ["__main__:HumanApprovalRequest"]


class ReviewerGateway(Executor):
    @handler
    async def on_agent_response(self, response: AgentExecutorResponse, ctx: WorkflowContext) -> None:
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
            await ctx.yield_output(f"PUBLISHED: {original_request.draft}")
        else:
            await ctx.yield_output(f"SENT BACK FOR EDITS ({feedback}): {original_request.draft}")


def create_workflow(storage):
    writer = Agent(client=make_client([Reply.text("Q3 memo: revenue is up 8%.")]), name="writer", instructions="Draft memos.")
    gateway = ReviewerGateway(id="reviewer_gateway")
    # an explicit, stable name is what lets a *restarted* process find its checkpoints again
    return (
        WorkflowBuilder(name="memo_approval", start_executor=writer, checkpoint_storage=storage, output_from=[gateway])
        .add_edge(writer, gateway)
        .build()
    )


async def main():
    with tempfile.TemporaryDirectory() as tmp:
        # ---- process 1: run until the human is needed, then "crash" ----
        storage = FileCheckpointStorage(tmp, allowed_checkpoint_types=ALLOWED)
        wf = create_workflow(storage)
        first = await wf.run("Write the Q3 memo")
        request = first.get_request_info_events()[0]
        print("paused on:", request.data.prompt, "| state:", first.get_final_state().name)

        # ---- process 2: brand new objects, same directory; answer the pending request ----
        storage2 = FileCheckpointStorage(tmp, allowed_checkpoint_types=ALLOWED)
        wf2 = create_workflow(storage2)
        latest = await storage2.get_latest(workflow_name=wf2.name)
        print(f"Checkpoint {latest.checkpoint_id[:8]}: iter={latest.iteration_count}, pending={len(latest.pending_request_info_events)}")
        resumed = await wf2.run(checkpoint_id=latest.checkpoint_id, responses={request.request_id: "approve"})
        print("resumed ->", resumed.get_outputs())

    # ---- time travel: resume from an EARLIER checkpoint of the same history ----
    mem = InMemoryCheckpointStorage()
    wf3 = create_workflow(mem)
    await wf3.run("Write the Q3 memo")
    history = sorted(await mem.list_checkpoints(workflow_name=wf3.name), key=lambda c: c.iteration_count)
    print("checkpoint history (iteration_count):", [c.iteration_count for c in history])
    earliest = history[0]
    replay = await wf3.run(checkpoint_id=earliest.checkpoint_id)
    print(f"replay from iter={earliest.iteration_count}: paused again on {len(replay.get_request_info_events())} request(s)")


if __name__ == "__main__":
    asyncio.run(main())
