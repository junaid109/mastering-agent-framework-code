"""Chapter 17.3 - checkpoint type allow-list. File storage only reconstructs types you declare."""
import asyncio
import logging
import os
import sys
import tempfile
from dataclasses import dataclass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from agent_framework import (  # noqa: E402
    Executor, FileCheckpointStorage, WorkflowBuilder, WorkflowContext, handler, register_checkpoint_type,
    response_handler,
)

logging.getLogger("agent_framework").setLevel(logging.ERROR)


@dataclass
class HumanApprovalRequest:
    prompt: str


@dataclass
class DeclaredNowhere:
    prompt: str


def gate(request_type):
    class Gate(Executor):
        def __init__(self):
            super().__init__(id="gate")

        @handler
        async def start(self, text: str, ctx: WorkflowContext) -> None:
            await ctx.request_info(request_data=request_type(prompt=text), response_type=str)

        @response_handler
        async def reply(self, original_request: request_type, response: str, ctx: WorkflowContext[str, str]) -> None:
            await ctx.yield_output(f"approved:{response}")

    return Gate


async def run(request_type, **storage_kwargs):
    folder = tempfile.mkdtemp()
    Gate = gate(request_type)
    storage = FileCheckpointStorage(folder, **storage_kwargs)
    wf = WorkflowBuilder(name="approval-wf", start_executor=Gate(), checkpoint_storage=storage).build()
    first = (await wf.run("ship it")).get_request_info_events()[0]
    # --- "process restart": brand-new storage + workflow over the same folder
    storage2 = FileCheckpointStorage(folder, **storage_kwargs)
    wf2 = WorkflowBuilder(name="approval-wf", start_executor=Gate(), checkpoint_storage=storage2).build()
    latest = await storage2.get_latest(workflow_name="approval-wf")
    pending = (await wf2.run(checkpoint_id=latest.checkpoint_id)).get_request_info_events()[0]
    print(f"  checkpoint iteration {latest.iteration_count}; same pending request restored: "
          f"{pending.request_id == first.request_id}")


async def main():
    print("undeclared application type:")
    await run(DeclaredNowhere)                                    # checkpoint with the pending request is refused
    print("allowed_checkpoint_types on this storage instance:")
    await run(HumanApprovalRequest,
              allowed_checkpoint_types=[f"{HumanApprovalRequest.__module__}:{HumanApprovalRequest.__qualname__}"])
    print("register_checkpoint_type (process-wide):")
    register_checkpoint_type(HumanApprovalRequest)
    await run(HumanApprovalRequest)


if __name__ == "__main__":
    asyncio.run(main())
