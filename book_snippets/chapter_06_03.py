# from 04-part-3-workflows\chapter-06-graph-based-orchestration.md:32
workflow = (
    WorkflowBuilder(start_executor=upper_case)
    .add_edge(upper_case, reverse_text)
    .build()
)

result = await workflow.run("hello world")
print(result.get_outputs())  # ['DLROW OLLEH']
