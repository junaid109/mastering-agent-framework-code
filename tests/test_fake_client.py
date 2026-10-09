import pytest
from agent_framework import Agent, tool

from support.fake_client import Reply, ScriptedChatClient, flatten


@tool
def get_weather(city: str) -> str:
    """Get the weather for a city."""
    return f"Sunny in {city}"


@pytest.mark.asyncio
async def test_text_reply():
    agent = Agent(client=ScriptedChatClient([Reply.text("Paris.")]), name="a", instructions="x")
    assert "Paris" in (await agent.run("Capital of France?")).text


@pytest.mark.asyncio
async def test_tool_loop():
    client = ScriptedChatClient([Reply.tool_call("get_weather", {"city": "Seattle"}), Reply.text("Sunny.")])
    agent = Agent(client=client, name="a", instructions="x", tools=[get_weather])
    result = await agent.run("Weather in Seattle?")
    assert result.text == "Sunny."
    # the second model request must contain the tool result
    assert ("tool", "function_result", "Sunny in Seattle") in flatten(client.requests[1])
