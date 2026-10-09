# from 04-part-3-workflows\chapter-06-graph-based-orchestration.md:49
workflow = WorkflowBuilder(start_executor=writer_agent).add_edge(writer_agent, reviewer_agent).build()

async for event in workflow.run(
    Message("user", ["Create a slogan for a new electric SUV."]),
    stream=True,
):
    if event.type == "output" and isinstance(event.data, AgentResponseUpdate):
        update = event.data
        print(f"[{update.author_name}] {update.text}", end="")
