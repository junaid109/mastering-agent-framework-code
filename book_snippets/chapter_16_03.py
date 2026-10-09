# from 08-part-7-real-systems\chapter-16-shipping-to-production.md:85
from azure.ai.agentserver.core.tasks import set_resilient_tasks_enabled
from azure.ai.agentserver.responses import ResponsesServerOptions
from agent_framework import WorkflowBuilder
from agent_framework_foundry_hosting import CheckpointStoreProvider, ResponsesHostServer

def build_workflow(request) -> Workflow:
    """Return freshly built executors with stable IDs for every invocation and recovery."""
    start, countdown = StartExecutor(), CountdownExecutor()
    return (WorkflowBuilder(name="countdown-workflow-v1", start_executor=start)
            .add_edge(start, countdown).add_edge(countdown, countdown).build())

set_resilient_tasks_enabled(True)
ResponsesHostServer(
    workflow=build_workflow,
    parse_response=parse_response,
    checkpoint_store_provider=CheckpointStoreProvider(
        allowed_checkpoint_types=[f"{CountdownRequest.__module__}:{CountdownRequest.__qualname__}"]),
    options=ResponsesServerOptions(resilient_background=True),
).run()
