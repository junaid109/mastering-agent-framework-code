"""Chapter 10.6: Pydantic for what comes OUT of a model call, TypedDict options for what goes IN.

Corrects the book: the OpenAI Responses client takes reasoning={"effort": ...}, not reasoning_effort=...
"""
import asyncio

import os
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from support.fake_client import Reply, ScriptedChatClient  # noqa: E402


def make_client(script):
    if os.environ.get("BOOK_CLIENT") == "openai-compatible":
        from agent_framework.openai import OpenAIChatCompletionClient

        return OpenAIChatCompletionClient(
            base_url=os.environ["BOOK_BASE_URL"],
            api_key=os.environ.get("BOOK_API_KEY", "not-needed"),
            model=os.environ["BOOK_MODEL"],
        )
    return ScriptedChatClient(script)


from agent_framework import Agent  # noqa: E402
from agent_framework.openai import OpenAIChatOptions  # noqa: E402
from pydantic import BaseModel  # noqa: E402


class CityFact(BaseModel):
    city: str
    country: str


async def main() -> None:
    agent = Agent(
        client=make_client([Reply.text('{"city": "Paris", "country": "France"}')]),
        name="geo",
        instructions="Reply with JSON matching the schema.",
    )
    # IN: provider-specific typed options (IDE-checked)
    options = OpenAIChatOptions(temperature=0.7, reasoning={"effort": "medium"}, response_format=CityFact)
    # Only keep options that are valid for a generic client when running offline/compatible endpoints
    result = await agent.run("What is the capital of France?", options={"response_format": CityFact})
    # OUT: validated, typed value
    fact = result.value
    print(type(fact).__name__, fact.city, fact.country)
    print("typed options example:", {k: v for k, v in options.items() if k != "response_format"})


if __name__ == "__main__":
    asyncio.run(main())
