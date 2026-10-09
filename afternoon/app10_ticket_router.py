"""Afternoon agent 10: one classifier, three destinations. Anything unclear goes to a human, never guessed."""
import asyncio
from typing import Any, Literal

from agent_framework import Agent, AgentExecutorResponse, WorkflowBuilder, WorkflowContext, executor
from pydantic import BaseModel
from typing_extensions import Never

from afternoon.common import make_client


class Ticket(BaseModel):
    category: Literal["billing", "technical", "other"]
    urgency: Literal["low", "high"]


def when(category: str | None):
    """Edge condition. category=None is the catch-all: 'other', or an answer we could not parse (fail to a human)."""
    def condition(message: Any) -> bool:
        try:
            got = Ticket.model_validate_json(message.agent_response.text).category
        except Exception:
            return category is None
        return got == category if category else got not in ("billing", "technical")
    return condition


def build_workflow(client):
    classifier = Agent(client=client, name="classifier", instructions="Classify the support ticket as JSON.",
                       default_options={"response_format": Ticket})

    def route(id_: str, label: str):
        @executor(id=id_)
        async def handler(response: AgentExecutorResponse, ctx: WorkflowContext[Never, str]) -> None:
            await ctx.yield_output(f"{label}: {response.agent_response.text}")
        return handler

    billing, technical, human = route("billing", "-> billing team"), route("technical", "-> on-call engineer"), route("human", "-> human triage")
    return (WorkflowBuilder(start_executor=classifier, output_from=[billing, technical, human])
            .add_edge(classifier, billing, condition=when("billing"))
            .add_edge(classifier, technical, condition=when("technical"))
            .add_edge(classifier, human, condition=when(None))
            .build())


async def main():
    from support.fake_client import Reply

    answers = {"double charge": '{"category": "billing", "urgency": "high"}',
               "app crashes": '{"category": "technical", "urgency": "low"}',
               "garbled model output": "I think it is probably billing?"}
    for ticket, answer in answers.items():
        result = await build_workflow(make_client([Reply.text(answer)])).run(ticket)
        print(f"{ticket:22}", result.get_outputs()[0][:40])


if __name__ == "__main__":
    asyncio.run(main())
