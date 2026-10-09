"""Chapter 10.2-10.7: async patterns, packages, DevUI, typing, testing."""
import asyncio
import importlib
import time
import warnings

import pytest
from agent_framework import Agent, ChatResponse, Message, SupportsChatGetResponse, workflow
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError

from support.fake_client import Reply, ScriptedChatClient, flatten

warnings.filterwarnings("ignore")


# ---------- 10.2 async patterns ----------
class SlowClient(ScriptedChatClient):
    """Scripted client that awaits a delay per call so concurrency is observable."""

    def get_response(self, *a, **k):  # type: ignore[override]
        stream = k.get("stream", False)
        if stream:
            return super().get_response(*a, **k)

        async def _go():
            await asyncio.sleep(0.3)
            return await super(SlowClient, self).get_response(*a, **k)

        return _go()


def _slow_agent(name, text):
    return Agent(client=SlowClient([Reply.text(text)]), name=name, instructions=name)


async def test_gather_fan_out_runs_agents_concurrently():
    agents = [_slow_agent(f"a{i}", f"r{i}") for i in range(3)]
    t = time.perf_counter()
    results = await asyncio.gather(*[a.run("prompt") for a in agents])
    elapsed = time.perf_counter() - t
    assert [r.text for r in results] == ["r0", "r1", "r2"]
    assert elapsed < 0.75  # sequential would be >= 0.9s


async def test_plain_async_function_sequential_pipeline_with_branching():
    draft = Agent(client=ScriptedChatClient([Reply.text("short draft"), Reply.text("longer draft")]), name="w", instructions="w")
    review = Agent(client=ScriptedChatClient([Reply.text("REJECT"), Reply.text("APPROVE")]), name="r", instructions="r")

    async def pipeline(topic: str) -> str:
        text = (await draft.run(topic)).text
        for _ in range(3):  # loop for repetition, if/else for branching
            if "APPROVE" in (await review.run(text)).text:
                return text
            text = (await draft.run(f"improve: {text}")).text
        return text

    assert await pipeline("topic") == "longer draft"


async def test_functional_workflow_decorator_parallel_pipeline():
    a1, a2 = _slow_agent("x", "X"), _slow_agent("y", "Y")

    @workflow
    async def parallel(prompt: str) -> list[str]:
        rs = await asyncio.gather(a1.run(prompt), a2.run(prompt))
        return [r.text for r in rs]

    result = await parallel.build().run("go")
    assert result.get_outputs() == [["X", "Y"]]


# ---------- 10.3 package structure ----------
@pytest.mark.parametrize(
    "module",
    [
        "agent_framework",
        "agent_framework.openai",
        "agent_framework_foundry",
        "agent_framework_anthropic",
        "agent_framework_gemini",
        "agent_framework_orchestrations",
        "agent_framework_azure_ai_search",
        "agent_framework_declarative",
        "agent_framework_monty",
        "agent_framework_hyperlight",
        "agent_framework_devui",
    ],
)
def test_package_importable(module):
    importlib.import_module(module)


def test_orchestration_builders_named_in_book_exist():
    from agent_framework.orchestrations import MagenticBuilder, SequentialBuilder  # noqa: F401


# ---------- 10.4 AF Labs: pointer only ----------
def test_af_labs_not_installed_pointer_only():
    with pytest.raises(ImportError):
        importlib.import_module("agent_framework_lab")


# ---------- 10.5 DevUI ----------
def test_devui_in_memory_mode_serves_openai_compatible_api():
    from agent_framework.devui import DevServer

    agent = Agent(client=ScriptedChatClient([Reply.text("hello from devui")]), name="demo", instructions="x")
    server = DevServer(port=8090, ui_enabled=False, mode="developer", auth_enabled=False)
    server.register_entities([agent])
    http = TestClient(server.get_app(), base_url="http://localhost:8090")
    assert http.get("/health").json()["entities_count"] == 1
    ents = http.get("/v1/entities").json()["entities"]
    assert ents[0]["name"] == "demo" and ents[0]["type"] == "agent"
    r = http.post("/v1/responses", json={"model": "demo", "input": "hi", "metadata": {"entity_id": ents[0]["id"]}})
    assert r.status_code == 200
    assert r.json()["output"][0]["content"][0]["text"] == "hello from devui"


def test_devui_serve_default_port_matches_directory_mode():
    import inspect

    from agent_framework.devui import serve

    assert inspect.signature(serve).parameters["port"].default == 8080  # `python main.py` -> :8080


# ---------- 10.6 typing ----------
def test_snippet_10_02_reasoning_effort_is_not_an_option_key():
    """MISMATCH: OpenAIChatOptions has `reasoning`, not `reasoning_effort` (see test_ch10_openai_options)."""
    from agent_framework.openai import OpenAIChatOptions

    assert "reasoning_effort" not in OpenAIChatOptions.__annotations__
    assert "reasoning" in OpenAIChatOptions.__annotations__


class City(BaseModel):
    city: str
    population: int


async def test_pydantic_response_format_gives_typed_value():
    agent = Agent(client=ScriptedChatClient([Reply.text('{"city":"Paris","population":2}')]), name="a", instructions="x")
    r = await agent.run("q", options={"response_format": City})
    assert isinstance(r.value, City) and r.value.population == 2


async def test_invalid_structured_output_raises_validation_error_in_1_21():
    """Behaviour in 1.21: accessing .value on bad JSON raises pydantic ValidationError (not None)."""
    agent = Agent(client=ScriptedChatClient([Reply.text("not json")]), name="a", instructions="x")
    r = await agent.run("q", options={"response_format": City})
    with pytest.raises(ValidationError):
        _ = r.value


# ---------- 10.7 testing ----------
class LocalSummaryClient:
    """Verbatim from the book (chapter_10_03)."""

    async def get_response(self, messages: list[Message], *, stream: bool = False, **kwargs) -> ChatResponse:
        return ChatResponse(messages=[Message(role="assistant", contents=[f"Summary for {len(messages)} messages."])])


async def test_snippet_10_03_plain_class_works_as_agent_client():
    agent = Agent(client=LocalSummaryClient(), name="t", instructions="x")
    r = await agent.run("hello")
    assert r.text == "Summary for 1 messages."


def test_snippet_10_03_does_not_satisfy_runtime_protocol_without_additional_properties():
    """MISMATCH (minor): isinstance(..., SupportsChatGetResponse) is False; protocol also needs additional_properties."""
    assert not isinstance(LocalSummaryClient(), SupportsChatGetResponse)

    class Fixed(LocalSummaryClient):
        additional_properties: dict = {}

    assert isinstance(Fixed(), SupportsChatGetResponse)


class InspectingChatClient:
    """Records inputs AND returns a scripted output (pattern described in 10.7)."""

    additional_properties: dict = {}

    def __init__(self, reply: str):
        self.reply, self.seen = reply, []

    async def get_response(self, messages, *, stream=False, **kwargs):
        self.seen.append(list(messages))
        return ChatResponse(messages=[Message(role="assistant", contents=[self.reply])])


async def test_inspecting_client_records_what_agent_sent():
    c = InspectingChatClient("done")
    agent = Agent(client=c, name="t", instructions="be terse")
    await agent.run("ping")
    assert [m.text for m in c.seen[0]] == ["ping"]
    assert isinstance(c, SupportsChatGetResponse)


async def test_fake_client_tests_tool_wiring_and_session_without_network():
    from agent_framework import tool

    @tool
    def add(a: int, b: int) -> int:
        """Add."""
        return a + b

    client = ScriptedChatClient([Reply.tool_call("add", {"a": 2, "b": 3}), Reply.text("5"), Reply.text("still 5")])
    agent = Agent(client=client, name="m", instructions="x", tools=[add])
    session = agent.create_session()
    assert (await agent.run("2+3?", session=session)).text == "5"
    await agent.run("again?", session=session)
    assert ("tool", "function_result", "5") in flatten(client.requests[1])
    assert ("tool", "function_result", "5") in flatten(client.requests[2])  # session kept history
