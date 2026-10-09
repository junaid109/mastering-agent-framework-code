"""Ch 6.2-6.4: executors, edges and conditional routing with a fail-closed condition (chapter_06_01/02/03/05)."""
import asyncio
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root, for support.fake_client

from pydantic import BaseModel
from typing_extensions import Never

from agent_framework import (
    Agent,
    AgentExecutorRequest,
    AgentExecutorResponse,
    Executor,
    Message,
    WorkflowBuilder,
    WorkflowContext,
    executor,
    handler,
)
from support.fake_client import Reply, ScriptedChatClient


def make_client(script):
    """Offline ScriptedChatClient by default; set BOOK_CLIENT=openai-compatible for a real endpoint."""
    if os.environ.get("BOOK_CLIENT") == "openai-compatible":
        from agent_framework.openai import OpenAIChatCompletionClient

        return OpenAIChatCompletionClient(
            base_url=os.environ["BOOK_BASE_URL"],
            api_key=os.environ.get("BOOK_API_KEY", "not-needed"),
            model=os.environ["BOOK_MODEL"],
        )
    return ScriptedChatClient(script)


# --- 6.2: a class executor and a function executor wired with add_edge -------------------------
class UpperCase(Executor):
    @handler
    async def to_upper_case(self, text: str, ctx: WorkflowContext[str]) -> None:
        await ctx.send_message(text.upper())


@executor(id="reverse_text_executor")
async def reverse_text(text: str, ctx: WorkflowContext[Never, str]) -> None:
    await ctx.yield_output(text[::-1])


# --- 6.4: conditional edges driven by a structured agent answer --------------------------------
class DetectionResult(BaseModel):
    is_spam: bool
    reason: str


def get_condition(expected_result: bool):
    def condition(message: Any) -> bool:
        if not isinstance(message, AgentExecutorResponse):
            return True
        try:
            detection = DetectionResult.model_validate_json(message.agent_response.text)
            return detection.is_spam == expected_result
        except Exception:
            return False  # fail closed: don't route on a parse error

    return condition


def create_spam_workflow(detector_reply: str):
    """Factory (not a module-level singleton) so every run gets fresh executors."""
    detector = Agent(
        client=make_client([Reply.text(detector_reply)]),
        name="spam_detector",
        instructions="Return JSON {is_spam: bool, reason: str}.",
        default_options={"response_format": DetectionResult},
    )
    email_assistant = Agent(
        client=make_client([Reply.text("Thanks for your note - see you Thursday.")]),
        name="email_assistant",
        instructions="Draft a short, polite reply.",
    )

    @executor(id="to_email_assistant_request")
    async def to_email_assistant_request(response: AgentExecutorResponse, ctx: WorkflowContext[AgentExecutorRequest]) -> None:
        await ctx.send_message(AgentExecutorRequest(messages=[Message("user", ["Draft a reply."])], should_respond=True))

    @executor(id="handle_spam")
    async def handle_spam(response: AgentExecutorResponse, ctx: WorkflowContext[Never, str]) -> None:
        await ctx.yield_output("Marked as spam, nothing sent.")

    @executor(id="send_email")
    async def send_email(response: AgentExecutorResponse, ctx: WorkflowContext[Never, str]) -> None:
        await ctx.yield_output(f"Sent: {response.agent_response.text}")

    return (
        # output_from keeps the agents' own AgentResponse out of the caller-facing output (section 6.6)
        WorkflowBuilder(start_executor=detector, output_from=[send_email, handle_spam])
        .add_edge(detector, to_email_assistant_request, condition=get_condition(False))
        .add_edge(detector, handle_spam, condition=get_condition(True))
        .add_edge(to_email_assistant_request, email_assistant)
        .add_edge(email_assistant, send_email)
        .build()
    )


async def main():
    upper = UpperCase(id="upper_case_executor")
    wf = WorkflowBuilder(start_executor=upper).add_edge(upper, reverse_text).build()
    print("pipeline:", (await wf.run("hello world")).get_outputs())  # ['DLROW OLLEH']

    cases = {
        "ham": '{"is_spam": false, "reason": "normal mail"}',
        "spam": '{"is_spam": true, "reason": "lottery"}',
        "garbled": "I think maybe spam?",  # parse error -> fail closed -> nothing routes
    }
    for label, reply in cases.items():
        result = await create_spam_workflow(reply).run("Are we still on for Thursday?")
        print(f"{label:8} ->", result.get_outputs() or "(no branch fired)")


if __name__ == "__main__":
    asyncio.run(main())
