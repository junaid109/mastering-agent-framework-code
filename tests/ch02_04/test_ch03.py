"""Chapter 3: anatomy of an agent (book_snippets/chapter_03_*.py)."""
import json
import os

import pytest
from pydantic import BaseModel, ValidationError

from agent_framework import (
    Agent,
    AgentResponse,
    AgentSession,
    HistoryProvider,
    Message,
    SlidingWindowStrategy,
    TruncationStrategy,
    tool,
)
from agent_framework.anthropic import AnthropicClient
from agent_framework.gemini import GeminiChatClient
from agent_framework.openai import OpenAIChatClient
from azure.identity import AzureCliCredential

from tests.ch02_04.helpers import Reply, RecordingClient, flatten, texts


@tool(approval_mode="never_require")
def get_weather(location: str) -> str:
    """Get the weather for a location."""
    return f"Sunny in {location}"


# ------------------------------------------------------------ 3.1 providers (03_01..03_03)
def test_03_01_openai_client_constructs(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    agent = Agent(
        client=OpenAIChatClient(model="gpt-5.4-nano", api_key=os.getenv("OPENAI_API_KEY")),
        name="WeatherAgent",
        instructions="You are a helpful weather agent.",
        tools=get_weather,  # a bare tool, not a list, is accepted
    )
    assert agent.name == "WeatherAgent"


def test_03_02_azure_openai_is_same_class_with_azure_endpoint_and_credential():
    client = OpenAIChatClient(
        model="gpt-4o",
        azure_endpoint="https://example.openai.azure.com",
        api_version="2024-10-21",
        credential=AzureCliCredential(),
    )
    assert type(client) is OpenAIChatClient  # book claim: same class, not a separate Azure type
    Agent(client=client, name="WeatherAgent", instructions="x", tools=get_weather)


def test_03_03_anthropic_and_gemini_construct():
    Agent(client=AnthropicClient(model="claude-sonnet-4-5-20250929", api_key="k"), name="W", instructions="x", tools=get_weather)
    Agent(client=GeminiChatClient(api_key="k", model="gemini-2.5-flash"), name="W", instructions="x", tools=[get_weather])


def test_03_03_gemini_reads_env_when_no_args(monkeypatch):
    """Book: GeminiChatClient() takes no args because it reads GOOGLE_MODEL + GOOGLE_API_KEY."""
    monkeypatch.setenv("GOOGLE_API_KEY", "k")
    monkeypatch.setenv("GOOGLE_MODEL", "gemini-2.5-flash")
    GeminiChatClient()


def test_03_03_gemini_without_key_raises(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_GENAI_USE_ENTERPRISE", raising=False)
    monkeypatch.delenv("GOOGLE_GENAI_USE_VERTEXAI", raising=False)
    with pytest.raises(ValueError):
        GeminiChatClient()


def test_openai_client_no_args_reads_env(monkeypatch):
    """3.3/3.5 snippets use OpenAIChatClient() with no args: works only with env vars."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5.4-nano")
    OpenAIChatClient()


# ------------------------------------------------------------ 3.2 instructions (03_04)
async def test_03_04_instructions_sent_as_system_instructions_every_request():
    instr = (
        "You are the customer support triage agent.\n"
        "Routing policy:\n"
        "1. Route refund-related requests to refund_agent.\n"
        "2. Route replacement/shipping requests to order_agent.\n"
        "3. Do not force replacement if the user asked for refund only.\n"
        "4. If the issue is fully resolved, send a concise wrap-up that ends with exactly: Case complete."
    )
    client = RecordingClient(lambda m: Reply.text("ok"))
    agent = Agent(client=client, name="triage", instructions=instr)
    s = agent.create_session()
    await agent.run("a", session=s)
    await agent.run("b", session=s)
    assert [o["instructions"] for o in client.options_seen] == [instr, instr]


# ------------------------------------------------------------ 3.3 sessions (03_05, 03_06)
async def test_03_05_session_accumulates_history_and_tool_calls():
    client = RecordingClient([
        Reply.tool_call("get_weather", {"location": "Tokyo"}), Reply.text("Tokyo is sunny"),
        Reply.tool_call("get_weather", {"location": "London"}), Reply.text("London is sunny"),
        Reply.text("Both sunny"),
    ])
    agent = Agent(client=client, instructions="You are a helpful weather agent.", tools=get_weather)
    session = agent.create_session()
    await agent.run("What's the weather like in Tokyo?", session=session)
    await agent.run("How about London?", session=session)
    r3 = await agent.run("Which of the cities I asked about has better weather?", session=session)
    assert r3.text == "Both sunny"
    last = texts(client.requests[-1])
    assert "What's the weather like in Tokyo?" in last and "How about London?" in last
    kinds = [t for (_r, t, _v) in flatten(client.requests[-1])]
    assert "function_call" in kinds and "function_result" in kinds  # tool exchanges replayed too


async def test_03_03_default_run_is_stateless():
    client = RecordingClient(lambda m: Reply.text("ok"))
    agent = Agent(client=client, instructions="x")
    await agent.run("What city?")
    await agent.run("What was the last city I asked about?")
    assert texts(client.requests[1]) == ["What was the last city I asked about?"]


def test_03_03_service_session_id_reconstruct():
    s = AgentSession(service_session_id="resp_123")
    assert s.service_session_id == "resp_123"


def test_03_03_session_to_dict_from_dict_roundtrip():
    s = AgentSession(service_session_id="resp_123")
    s.state["k"] = {"v": 1}
    d = s.to_dict()
    json.dumps(d)  # "plain dict you can hand to any storage layer"
    s2 = AgentSession.from_dict(d)
    assert s2.session_id == s.session_id
    assert s2.service_session_id == "resp_123"
    assert s2.state["k"] == {"v": 1}


async def test_03_03_roundtrip_session_keeps_conversation():
    client = RecordingClient(lambda m: Reply.text("ok"))
    agent = Agent(client=client, instructions="x")
    s = agent.create_session()
    await agent.run("one", session=s)
    restored = AgentSession.from_dict(json.loads(json.dumps(s.to_dict())))
    await agent.run("two", session=restored)
    assert texts(client.requests[1]) == ["one", "ok", "two"]


class CustomHistoryProvider(HistoryProvider):
    def __init__(self) -> None:
        super().__init__("custom-history")
        self._storage: dict[str, list[Message]] = {}

    async def get_messages(self, session_id, *, state=None, **kwargs) -> list[Message]:
        return list(self._storage.get(session_id or "default", []))

    async def save_messages(self, session_id, messages, *, state=None, **kwargs) -> None:
        key = session_id or "default"
        self._storage.setdefault(key, []).extend(messages)


async def test_03_06_custom_history_provider_stores_and_replays():
    provider = CustomHistoryProvider()
    client = RecordingClient(lambda m: Reply.text("ok"))
    agent = Agent(client=client, instructions="remember", context_providers=[provider])
    s = agent.create_session()
    await agent.run("one", session=s)
    await agent.run("two", session=s)
    assert texts(client.requests[1]) == ["one", "ok", "two"]
    assert [m.text for m in provider._storage[s.session_id]] == ["one", "ok", "two", "ok"]
    s2 = agent.create_session()
    await agent.run("three", session=s2)
    assert texts(client.requests[2]) == ["three"]


# ------------------------------------------------------------ 3.4 compaction (03_07)
class FixedTokenizer:
    """The book snippet uses FixedTokenizer but never defines/imports it (not an agent_framework export)."""

    def __init__(self, n: int) -> None:
        self.n = n

    def count_tokens(self, text: str) -> int:
        return self.n


def test_03_07_FixedTokenizer_is_not_exported_by_framework():
    import agent_framework

    assert not hasattr(agent_framework, "FixedTokenizer")


class _Spy:
    """Compaction strategy that records that it was invoked (never changes messages)."""

    def __init__(self, name, calls):
        self.name, self.calls = name, calls

    async def __call__(self, messages):
        self.calls.append(self.name)
        return False


def _client(strategy=None, tokenizer=None):
    kw = {}
    if strategy is not None:
        kw = {"compaction_strategy": strategy, "tokenizer": tokenizer}
    return RecordingClient(lambda m: Reply.text("ok"), **kw)


async def test_03_07_client_level_truncation_compacts_history():
    client = _client(TruncationStrategy(max_n=3, compact_to=2), FixedTokenizer(7))
    agent = Agent(client=client, name="ClientDefaultAgent")
    s = agent.create_session()
    for i in range(4):
        await agent.run(f"m{i}", session=s)
    assert [len(r) for r in client.requests] == [1, 3, 2, 2]  # >3 messages -> trimmed to 2
    assert texts(client.requests[-1]) == ["ok", "m3"]


async def test_03_07_agent_level_overrides_client_default():
    calls = []
    client = _client(_Spy("client", calls), FixedTokenizer(7))
    agent = Agent(client=client, name="AgentOverrideAgent",
                  compaction_strategy=_Spy("agent", calls), tokenizer=FixedTokenizer(11))
    await agent.run("hi")
    assert calls == ["agent"]


async def test_03_07_default_agent_uses_client_strategy():
    calls = []
    client = _client(_Spy("client", calls), FixedTokenizer(7))
    await Agent(client=client, name="ClientDefaultAgent").run("hi")
    assert calls == ["client"]


async def test_03_07_run_level_overrides_agent_and_client():
    calls = []
    client = _client(_Spy("client", calls), FixedTokenizer(7))
    agent = Agent(client=client, compaction_strategy=_Spy("agent", calls), tokenizer=FixedTokenizer(11))
    await agent.run("hi", compaction_strategy=_Spy("run", calls), tokenizer=FixedTokenizer(23))
    assert calls == ["run"]


async def test_03_07_snippet_shape_with_real_strategies():
    shared = _client(TruncationStrategy(max_n=3, compact_to=2), FixedTokenizer(7))
    override = Agent(client=shared, name="AgentOverrideAgent",
                     compaction_strategy=SlidingWindowStrategy(keep_last_groups=3), tokenizer=FixedTokenizer(11))
    messages = [Message("user", ["a"]), Message("assistant", ["b"]), Message("user", ["c"])]
    await override.run(messages, compaction_strategy=TruncationStrategy(max_n=2, compact_to=1), tokenizer=FixedTokenizer(23))
    assert texts(shared.requests[0]) == ["c"]  # run-level TruncationStrategy(max_n=2, compact_to=1) applied


def test_03_04_strategy_family_exists():
    import agent_framework as af

    for n in ["TruncationStrategy", "SlidingWindowStrategy", "SelectiveToolCallCompactionStrategy",
              "ToolResultCompactionStrategy", "SummarizationStrategy", "TokenBudgetComposedStrategy"]:
        assert hasattr(af, n), n


# ------------------------------------------------------------ 3.5 structured output (03_08, 03_09)
class OutputStruct(BaseModel):
    city: str
    description: str


async def test_03_08_pydantic_response_format_and_value():
    client = RecordingClient([Reply.text(json.dumps({"city": "Paris", "description": "City of light"}))])
    agent = Agent(client=client, name="CityAgent", instructions="structured")
    result = await agent.run("Tell me about Paris, France", options={"response_format": OutputStruct})
    assert client.options_seen[0]["response_format"] is OutputStruct  # forwarded to the client
    assert isinstance(result.value, OutputStruct)
    assert (result.value.city, result.value.description) == ("Paris", "City of light")


async def test_03_08_value_is_none_without_response_format():
    client = RecordingClient([Reply.text("Paris is nice")])
    result = await Agent(client=client, name="C", instructions="x").run("q")
    assert result.value is None


async def test_03_08_value_on_unparseable_output_raises_validation_error():
    """Not stated by the book, but `if structured_data := result.value:` suggests None on failure.
    Actual 1.21.0 behaviour: pydantic ValidationError is raised from .value."""
    client = RecordingClient([Reply.text("not json")])
    result = await Agent(client=client, name="C", instructions="x").run("q", options={"response_format": OutputStruct})
    with pytest.raises(ValidationError):
        result.value  # noqa: B018


async def test_03_08_streaming_structured_output_via_from_update_generator():
    client = RecordingClient([Reply.text(json.dumps({"city": "Paris", "description": "d"}))])
    agent = Agent(client=client, name="CityAgent", instructions="x")
    resp = await AgentResponse.from_update_generator(
        agent.run("q", stream=True, options={"response_format": OutputStruct}),
        output_format_type=OutputStruct,
    )
    assert resp.value == OutputStruct(city="Paris", description="d")


async def test_03_09_runtime_json_schema_dict_response_format():
    runtime_schema = {
        "type": "object",
        "properties": {"summary": {"type": "string"}, "high_c": {"type": "number"}},
        "required": ["summary", "high_c"],
        "additionalProperties": False,
    }
    rf = {"type": "json_schema", "json_schema": {"name": "WeatherDigest", "strict": True, "schema": runtime_schema}}
    client = RecordingClient([Reply.text(json.dumps({"summary": "Cloudy", "high_c": 14}))])
    agent = Agent(client=client, instructions="x")
    response = await agent.run("Give a brief weather digest for Seattle.", options={"response_format": rf})
    assert client.options_seen[0]["response_format"] == rf  # dict passes through unchanged
    assert json.loads(response.text) == {"summary": "Cloudy", "high_c": 14}
