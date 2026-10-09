"""Chapter 2: hello agent + streaming (book_snippets/chapter_02_*.py)."""
import pytest
from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from azure.identity import AzureCliCredential

from tests.ch02_04.helpers import Reply, RecordingClient, texts


def test_02_01_foundry_client_constructs_offline_with_explicit_config():
    # The book constructs FoundryChatClient(credential=AzureCliCredential()) relying on env vars.
    client = FoundryChatClient(
        project_endpoint="https://example.services.ai.azure.com/api/projects/p",
        model="gpt-x",
        credential=AzureCliCredential(),
    )
    agent = Agent(client=client, name="HaikuAgent", instructions="You are an upbeat assistant that writes beautifully.")
    assert agent.name == "HaikuAgent"


def test_02_01_foundry_client_without_env_raises_clear_error(monkeypatch):
    monkeypatch.delenv("FOUNDRY_MODEL", raising=False)
    monkeypatch.delenv("FOUNDRY_PROJECT_ENDPOINT", raising=False)
    with pytest.raises(ValueError, match="FOUNDRY_MODEL"):
        FoundryChatClient(credential=AzureCliCredential())


async def test_02_01_hello_agent_prints_text(capsys):
    client = RecordingClient([Reply.text("Agents wake at dawn\nTools hum, graphs align\nHello, framework")])
    agent = Agent(client=client, name="HaikuAgent", instructions="You are an upbeat assistant that writes beautifully.")
    print(await agent.run("Write a haiku about Microsoft Agent Framework."))
    out = capsys.readouterr().out
    assert "Hello, framework" in out  # str(AgentResponse) is the text
    assert client.options_seen[0]["instructions"] == "You are an upbeat assistant that writes beautifully."
    assert texts(client.requests[0]) == ["Write a haiku about Microsoft Agent Framework."]


async def test_02_02_streaming_loop_chunks_have_text(capsys):
    client = RecordingClient([Reply.text("Octopuses have three hearts.")])
    agent = Agent(client=client, name="A", instructions="x")
    async for chunk in agent.run("Tell me a one-sentence fun fact.", stream=True):
        if chunk.text:
            print(chunk.text, end="", flush=True)
    assert "three hearts" in capsys.readouterr().out


async def test_lifecycle_stateless_vs_session_2_5():
    """Sec 2.5 claims: bare run is stateless; session replays history; session updated after run."""
    client = RecordingClient(lambda m: Reply.text("ok"))
    agent = Agent(client=client, name="A", instructions="x")
    await agent.run("first")
    await agent.run("second")
    assert texts(client.requests[1]) == ["second"]  # no memory without a session
    s = agent.create_session()
    await agent.run("one", session=s)
    await agent.run("two", session=s)
    assert texts(client.requests[3]) == ["one", "ok", "two"]
