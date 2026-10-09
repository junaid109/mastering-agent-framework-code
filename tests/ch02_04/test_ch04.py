"""Chapter 4: tools and skills (book_snippets/chapter_04_*.py)."""
from typing import Annotated

import pytest
from pydantic import BaseModel, Field

from agent_framework import Agent, FunctionInvocationContext, Message, tool
from agent_framework.openai import OpenAIChatClient

from tests.ch02_04.helpers import Reply, RecordingClient, flatten, texts


# ------------------------------------------------------------ 4.1 (04_01)
@tool(approval_mode="never_require")
def get_weather(
    location: Annotated[str, Field(description="The location to get the weather for.")],
) -> str:
    """Get the weather for a given location."""
    return f"Sunny in {location}"


def test_04_01_tool_schema_is_derived_from_signature():
    assert get_weather.name == "get_weather"  # function name -> tool name
    assert get_weather.description == "Get the weather for a given location."  # docstring -> description
    schema = get_weather.parameters()
    assert schema["properties"]["location"]["type"] == "string"  # type hint
    assert schema["properties"]["location"]["description"] == "The location to get the weather for."  # Field metadata
    assert schema["required"] == ["location"]
    assert get_weather.approval_mode == "never_require"


def test_04_01_verbatim_snippet_body_is_ellipsis_returns_none():
    """The book's literal body is `...`; calling it would return None (it is a stub, not runnable as-is)."""

    @tool(approval_mode="never_require")
    def stub(location: Annotated[str, Field(description="d")]) -> str:
        """Stub."""
        ...

    assert stub.func("x") is None


async def test_04_01_tool_list_makes_tool_callable_end_to_end():
    client = RecordingClient([Reply.tool_call("get_weather", {"location": "Seattle"}), Reply.text("It is sunny.")])
    agent = Agent(client=client, instructions="x", tools=[get_weather])
    r = await agent.run("weather in Seattle?")
    assert r.text == "It is sunny."
    assert ("tool", "function_result", "Sunny in Seattle") in flatten(client.requests[1])
    sent = client.options_seen[0]["tools"]
    assert [t.name for t in sent] == ["get_weather"]


async def test_04_01_explicit_schema_override():
    class Args(BaseModel):
        city: Annotated[str, Field(description="City name")]

    @tool(name="weather", description="Weather lookup", schema=Args)
    def lookup(location: str) -> str:
        return "x"

    assert lookup.name == "weather"
    assert "city" in lookup.parameters()["properties"]  # model sees "city", code param is "location"


async def test_04_01_declaration_only_tool_is_not_executed_locally():
    from agent_framework import FunctionTool

    remote = FunctionTool(name="remote_search", description="Runs elsewhere", func=None,
                          input_model={"type": "object", "properties": {"q": {"type": "string"}}, "required": ["q"]})
    assert remote.declaration_only
    client = RecordingClient([Reply.tool_call("remote_search", {"q": "x"}), Reply.text("unused")])
    agent = Agent(client=client, instructions="x", tools=[remote])
    r = await agent.run("go")
    kinds = [c.type for m in r.messages for c in m.contents]
    assert "function_call" in kinds and "function_result" not in kinds
    assert len(client.requests) == 1  # loop stops and hands the call back to the caller


async def test_04_01_tool_in_class_bound_method():
    class Weather:
        def __init__(self):
            self.calls = 0

        @tool(approval_mode="never_require")
        def forecast(self, location: str) -> str:
            """Forecast."""
            self.calls += 1
            return f"fc {location}"

    w = Weather()
    client = RecordingClient([Reply.tool_call("forecast", {"location": "Oslo"}), Reply.text("done")])
    agent = Agent(client=client, instructions="x", tools=[w.forecast])
    await agent.run("go")
    assert w.calls == 1


# ------------------------------------------------------------ 4.3-4.6 hosted tools (04_02..04_05)
@pytest.fixture
def oai():
    return OpenAIChatClient(model="gpt-5.4-nano", api_key="sk-test")


def test_04_02_code_interpreter_tool_shape(oai):
    t = oai.get_code_interpreter_tool()
    assert t["type"] == "code_interpreter"
    Agent(client=oai, instructions="x", tools=oai.get_code_interpreter_tool())  # bare tool accepted


async def test_04_02_code_interpreter_reaches_model_request():
    ci = OpenAIChatClient(model="m", api_key="k").get_code_interpreter_tool()
    client = RecordingClient([Reply.text("93326215443944152681699238856266700490715968264381621468592963895217599993229915608941463976156518286253697920827223758251185210916864000000000000000000000000")])
    agent = Agent(client=client, instructions="x", tools=ci)
    await agent.run("Use code to get the factorial of 100?")
    assert client.options_seen[0]["tools"] == [ci]


def test_04_03_file_search_tool_and_openai_client_vector_store_surface(oai):
    # `client.client.vector_stores...` path used by the book exists on the underlying AsyncOpenAI client.
    assert hasattr(oai.client, "vector_stores")
    assert hasattr(oai.client.vector_stores.files, "create_and_poll")
    t = oai.get_file_search_tool(vector_store_ids=["vs_123"])
    assert t == {"type": "file_search", "vector_store_ids": ["vs_123"]}
    Agent(client=oai, instructions="x", tools=[t])


def test_04_03_file_search_requires_keyword_vector_store_ids(oai):
    with pytest.raises(TypeError):
        oai.get_file_search_tool(["vs_123"])  # positional not allowed -> the book's keyword form is required


def test_04_04_web_search_tool_user_location(oai):
    t = oai.get_web_search_tool(user_location={"city": "Seattle", "country": "US"})
    assert t["type"] == "web_search"
    assert t["user_location"]["city"] == "Seattle" and t["user_location"]["country"] == "US"
    Agent(client=oai, instructions="x", tools=[t])


def test_04_05_mcp_tool_shape_is_executed_by_provider(oai):
    github_pat = "ghp_test"
    t = oai.get_mcp_tool(
        name="GitHub",
        url="https://api.githubcopilot.com/mcp/",
        headers={"Authorization": f"Bearer {github_pat}"},
        approval_mode="never_require",
    )
    assert t["type"] == "mcp"  # a hosted tool description, sent to the provider (not run locally)
    assert t["server_label"] == "GitHub"
    assert t["server_url"] == "https://api.githubcopilot.com/mcp/"
    assert t["require_approval"] == "never"
    assert t["headers"] == {"Authorization": "Bearer ghp_test"}


# ------------------------------------------------------------ 4.7 approvals (04_06)
_ran: list[str] = []


@tool(approval_mode="always_require")
def send_email(to: str) -> str:
    """Send an email."""
    _ran.append(to)
    return f"sent to {to}"


def _approval_agent():
    _ran.clear()
    client = RecordingClient([Reply.tool_call("send_email", {"to": "a@b.c"}), Reply.text("Email sent.")])
    return client, Agent(client=client, instructions="x", tools=send_email)


async def test_04_06_always_require_pauses_with_user_input_requests():
    client, agent = _approval_agent()
    result = await agent.run("email a@b.c")
    assert len(result.user_input_requests) == 1
    req = result.user_input_requests[0]
    assert req.function_call.name == "send_email"
    assert "a@b.c" in str(req.function_call.arguments)
    assert _ran == []  # tool did NOT run yet


async def test_04_06_book_loop_verbatim_without_session_never_runs_tool():
    """MISMATCH: the book loop passes no session; in 1.21.0 the approval response is ignored and the tool never runs."""
    client, agent = _approval_agent()
    query = "email a@b.c"
    result = await agent.run(query)
    while len(result.user_input_requests) > 0:
        new_inputs = [query]
        for user_input_needed in result.user_input_requests:
            new_inputs.append(Message("assistant", [user_input_needed]))
            new_inputs.append(Message("user", [user_input_needed.to_function_approval_response(True)]))
        result = await agent.run(new_inputs)
    assert _ran == []  # approved, yet the tool never executed
    assert ("tool", "function_result", "sent to a@b.c") not in flatten(client.requests[-1])


async def test_04_06_fixed_loop_with_session_runs_tool_when_approved():
    client, agent = _approval_agent()
    session = agent.create_session()
    query = "email a@b.c"
    result = await agent.run(query, session=session)
    while len(result.user_input_requests) > 0:
        new_inputs = [query]
        for u in result.user_input_requests:
            new_inputs.append(Message("assistant", [u]))
            new_inputs.append(Message("user", [u.to_function_approval_response(True)]))
        result = await agent.run(new_inputs, session=session)
    assert _ran == ["a@b.c"]
    assert result.text == "Email sent."
    assert ("tool", "function_result", "sent to a@b.c") in flatten(client.requests[-1])


async def test_04_06_fixed_loop_denial_does_not_run_tool():
    client, agent = _approval_agent()
    session = agent.create_session()
    result = await agent.run("email", session=session)
    u = result.user_input_requests[0]
    result = await agent.run(
        [Message("assistant", [u]), Message("user", [u.to_function_approval_response(False)])], session=session
    )
    assert _ran == []
    assert any("rejected" in str(v) for (_r, t, v) in flatten(client.requests[-1]) if t == "function_result")


async def test_04_06_alternative_fix_disable_binding_option():
    """Without a session, the framework's own hint works: disable_approval_response_binding."""
    client, agent = _approval_agent()
    client.function_invocation_configuration["disable_approval_response_binding"] = True
    query = "email a@b.c"
    result = await agent.run(query)
    u = result.user_input_requests[0]
    await agent.run([query, Message("assistant", [u]), Message("user", [u.to_function_approval_response(True)])])
    assert _ran == ["a@b.c"]


# ------------------------------------------------------------ 4.8 design patterns (prose claims)
async def test_04_08_dynamic_tool_exposure_via_ctx_add_tools():
    @tool(approval_mode="never_require")
    def secret_math(x: int) -> int:
        """Doubles."""
        return x * 2

    @tool(approval_mode="never_require")
    def load_math(ctx: FunctionInvocationContext) -> str:
        """Load math tools."""
        ctx.add_tools(secret_math)
        return "loaded"

    client = RecordingClient([
        Reply.tool_call("load_math", {}), Reply.tool_call("secret_math", {"x": 21}), Reply.text("42"),
    ])
    agent = Agent(client=client, instructions="x", tools=[load_math])
    r = await agent.run("go")
    assert r.text == "42"
    names = [[t.name for t in o["tools"]] for o in client.options_seen]
    assert names[0] == ["load_math"]  # not frontloaded
    assert "secret_math" in names[1]  # takes effect on the next loop iteration
    assert ("tool", "function_result", "42") in flatten(client.requests[2])


async def test_04_08_max_invocations_caps_a_tool():
    @tool(approval_mode="never_require", max_invocations=1)
    def once(x: str) -> str:
        """once"""
        return "ok"

    client = RecordingClient([Reply.tool_call("once", {"x": "1"}), Reply.tool_call("once", {"x": "2"}), Reply.text("end")])
    agent = Agent(client=client, instructions="x", tools=[once])
    await agent.run("go")
    assert once.invocation_count == 1
    results = [v for (_r, t, v) in flatten(client.requests[2]) if t == "function_result"]
    assert results[0] == "ok" and results[1].startswith("Error")  # 2nd call refused, error goes back to the model


async def test_04_08_max_invocation_exceptions_caps_failures():
    @tool(approval_mode="never_require", max_invocation_exceptions=1)
    def flaky(x: str) -> str:
        """flaky"""
        raise RuntimeError("boom")

    client = RecordingClient([Reply.tool_call("flaky", {"x": "1"}), Reply.tool_call("flaky", {"x": "2"}), Reply.text("end")])
    agent = Agent(client=client, instructions="x", tools=[flaky])
    await agent.run("go")
    assert flaky.invocation_exception_count == 1  # second attempt refused without running


async def test_04_08_tool_error_is_returned_to_model_not_raised():
    @tool(approval_mode="never_require")
    def lookup(x: str) -> str:
        """lookup"""
        raise ValueError("no such record")

    client = RecordingClient([Reply.tool_call("lookup", {"x": "1"}), Reply.text("I could not find it.")])
    agent = Agent(client=client, instructions="x", tools=[lookup])
    r = await agent.run("go")  # does not raise
    assert r.text == "I could not find it."
    res = [v for (_r, t, v) in flatten(client.requests[1]) if t == "function_result"]
    assert res and "Error" in res[0]


async def test_04_08_function_invocation_configuration_iteration_limit():
    @tool(approval_mode="never_require")
    def loop(x: str) -> str:
        """loop"""
        return "again"

    client = RecordingClient(lambda m: Reply.tool_call("loop", {"x": "1"}))
    client.function_invocation_configuration["max_iterations"] = 3
    agent = Agent(client=client, instructions="x", tools=[loop])
    await agent.run("go")
    assert loop.invocation_count <= 3
