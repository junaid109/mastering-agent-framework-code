# from 04-part-3-workflows\chapter-06-graph-based-orchestration.md:15
class UpperCase(Executor):
    @handler
    async def to_upper_case(self, text: str, ctx: WorkflowContext[str]) -> None:
        await ctx.send_message(text.upper())
