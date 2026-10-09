# from 04-part-3-workflows\chapter-06-graph-based-orchestration.md:24
@executor(id="reverse_text_executor")
async def reverse_text(text: str, ctx: WorkflowContext[Never, str]) -> None:
    await ctx.yield_output(text[::-1])
