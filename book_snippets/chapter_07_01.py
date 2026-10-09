# from 04-part-3-workflows\chapter-07-human-in-the-loop.md:13
checkpoint_storage = InMemoryCheckpointStorage()

workflow = (
    WorkflowBuilder(start_executor=start, checkpoint_storage=checkpoint_storage)
    .add_edge(start, worker)
    .build()
)

# ... run, get interrupted, come back later ...

latest_checkpoint = await checkpoint_storage.get_latest(workflow_name=workflow.name)
print(f"Checkpoint {latest_checkpoint.checkpoint_id}: iter={latest_checkpoint.iteration_count}")

async for event in workflow.run(checkpoint_id=latest_checkpoint.checkpoint_id, stream=True):
    ...
