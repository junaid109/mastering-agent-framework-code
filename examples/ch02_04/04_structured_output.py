"""Ch 3.5: Pydantic and raw JSON-schema response_format (chapter_03_08/09)."""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent_framework import Agent, AgentResponse
from pydantic import BaseModel
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


class OutputStruct(BaseModel):
    city: str
    description: str


async def main():
    payload = json.dumps({"city": "Paris", "description": "The French capital."})
    agent = Agent(
        client=make_client([Reply.text(payload), Reply.text(payload),
                            Reply.text(json.dumps({"summary": "Cloudy", "high_c": 14}))]),
        name="CityAgent",
        instructions="You are a helpful agent that describes cities in a structured format.",
    )

    result = await agent.run("Tell me about Paris, France", options={"response_format": OutputStruct})
    if structured := result.value:
        print("typed:", structured.city, "-", structured.description)

    streamed = await AgentResponse.from_update_generator(
        agent.run("Tell me about Paris, France", stream=True, options={"response_format": OutputStruct}),
        output_format_type=OutputStruct,
    )
    print("streamed typed:", streamed.value)

    schema = {
        "type": "object",
        "properties": {"summary": {"type": "string"}, "high_c": {"type": "number"}},
        "required": ["summary", "high_c"],
        "additionalProperties": False,
    }
    response = await agent.run(
        "Give a brief weather digest for Seattle.",
        options={"response_format": {"type": "json_schema",
                                     "json_schema": {"name": "WeatherDigest", "strict": True, "schema": schema}}},
    )
    print("runtime schema:", json.loads(response.text))


if __name__ == "__main__":
    asyncio.run(main())
