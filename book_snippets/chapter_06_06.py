# from 04-part-3-workflows\chapter-06-graph-based-orchestration.md:93
workflow = (
    WorkflowBuilder(start_executor=dispatcher)
    .add_fan_out_edges(dispatcher, [researcher, marketer, legal])   # parallel branches
    .add_fan_in_edges([researcher, marketer, legal], aggregator)    # join point
    .build()
)
