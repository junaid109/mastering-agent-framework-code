# from 04-part-3-workflows\chapter-07-human-in-the-loop.md:37
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
    async def on_human_feedback(self, original_request: HumanApprovalRequest, feedback: str, ctx: WorkflowContext) -> None:
        # feedback == "approve" or edit instructions — route accordingly
        ...
