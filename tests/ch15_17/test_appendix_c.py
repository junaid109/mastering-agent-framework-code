"""Appendix C quick-reference: every Python entry executed or checked against 1.21.0."""
import importlib
import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated

import pytest
from agent_framework import (
    Agent,
    AgentSession,
    ChatContext,
    Filter,
    FilterGroup,
    FunctionInvocationContext,
    FunctionMiddleware,
    InMemoryStore,
    Message,
    SlidingWindowStrategy,
    VectorStoreField,
    chat_middleware,
    tool,
    vectorstoremodel,
)
from pydantic import BaseModel, ValidationError

from support.fake_client import Reply, ScriptedChatClient, flatten
from tests.ch15_17.helpers import DIM, HashEmbeddingClient, RecordingClient

pytestmark = pytest.mark.filterwarnings("ignore")


# ---------------------------------------------------------------- C.1 (appendix_c_01 is a placeholder)
def test_c1_agent_constructor_keywords_exist():
    params = inspect.signature(Agent.__init__).parameters
    for p in ("client", "name", "instructions", "tools", "compaction_strategy", "tokenizer", "middleware",
              "context_providers", "default_options"):
        assert p in params, p


async def test_c1_run_single_and_streaming():  # appendix_c_02
    agent = Agent(client=ScriptedChatClient([Reply.text("whole")]), name="a")
    assert (await agent.run("q")).text == "whole"
    agent2 = Agent(client=ScriptedChatClient([Reply.text("streamed")]), name="a")
    chunks = [c.text async for c in agent2.run("q", stream=True)]
    assert "".join(chunks) == "streamed"


async def test_c1_sessions_round_trip():  # appendix_c_03
    client = RecordingClient([Reply.text("a1"), Reply.text("a2")])
    agent = Agent(client=client, name="a")
    session = agent.create_session()
    await agent.run("first", session=session)
    serialized = session.to_dict()
    resumed = AgentSession.from_dict(serialized)
    await agent.run("second", session=resumed)
    texts = [(r, t) for r, k, t in flatten(client.requests[1]) if k == "text"]
    assert texts == [("user", "first"), ("assistant", "a1"), ("user", "second")]


class MyPydanticModel(BaseModel):
    a: int


async def test_c1_structured_output_value_typed_instance():  # appendix_c_04 (happy path)
    agent = Agent(client=ScriptedChatClient([Reply.text('{"a": 7}')]), name="a")
    result = await agent.run("q", options={"response_format": MyPydanticModel})
    data = result.value
    assert isinstance(data, MyPydanticModel) and data.a == 7


@pytest.mark.parametrize("bad", ["not json at all", '{"a": "NaN"}'])
async def test_c1_structured_output_value_is_NOT_none_on_parse_failure_it_raises(bad):
    """MISMATCH: appendix says 'typed instance, or None if parsing failed'. In 1.21.0 .value raises."""
    agent = Agent(client=ScriptedChatClient([Reply.text(bad)]), name="a")
    result = await agent.run("q", options={"response_format": MyPydanticModel})  # run itself succeeds
    assert result.text == bad
    with pytest.raises(ValidationError):
        _ = result.value


async def test_c1_structured_output_verified_fix_try_except():
    agent = Agent(client=ScriptedChatClient([Reply.text("garbage")]), name="a")
    result = await agent.run("q", options={"response_format": MyPydanticModel})
    try:
        data = result.value
    except ValidationError:
        data = None
    assert data is None


async def test_c1_value_is_none_only_when_no_response_format():
    agent = Agent(client=ScriptedChatClient([Reply.text("plain")]), name="a")
    assert (await agent.run("q")).value is None


def test_c1_compaction_agent_kwargs():  # appendix_c_05 (tokenizer=... placeholder)
    class T:
        def count_tokens(self, text):  # minimal tokenizer shape
            return len(text.split())

    agent = Agent(client=ScriptedChatClient([Reply.text("x")]), name="a",
                  compaction_strategy=SlidingWindowStrategy(keep_last_groups=4), tokenizer=T())
    assert agent is not None


async def test_c1_tool_with_approval_and_never_require():  # appendix_c_06
    ran = []

    @tool(approval_mode="always_require")
    def my_tool(x: str) -> str:
        """t"""
        ran.append(x)
        return "ok"

    @tool(approval_mode="never_require")
    def demo_tool(x: str) -> str:
        """t"""
        ran.append("demo")
        return "ok"

    agent = Agent(client=ScriptedChatClient([Reply.tool_call("my_tool", {"x": "1"}), Reply.text("d")]), name="a",
                  tools=[my_tool, demo_tool])
    r = await agent.run("go", session=agent.create_session())
    assert len(r.user_input_requests) == 1 and ran == []
    agent2 = Agent(client=ScriptedChatClient([Reply.tool_call("demo_tool", {"x": "1"}), Reply.text("d")]), name="a",
                   tools=[my_tool, demo_tool])
    r = await agent2.run("go2", session=agent2.create_session())
    assert ran == ["demo"] and not r.user_input_requests


# ---------------------------------------------------------------- C.2
@pytest.mark.parametrize("module,cls", [
    ("agent_framework.openai", "OpenAIChatClient"), ("agent_framework.anthropic", "AnthropicClient"),
    ("agent_framework.gemini", "GeminiChatClient"), ("agent_framework.foundry", "FoundryChatClient"),
    ("agent_framework.amazon", "BedrockChatClient"), ("agent_framework.github", "GitHubCopilotAgent"),
    ("agent_framework.ollama", "OllamaChatClient"), ("agent_framework.azure", "AzureAISearchContextProvider"),
])
def test_c2_provider_classes_import(module, cls):
    assert hasattr(importlib.import_module(module), cls)


@pytest.mark.parametrize("method", ["get_code_interpreter_tool", "get_file_search_tool",
                                    "get_web_search_tool", "get_mcp_tool"])
def test_c2_hosted_tool_factories_on_openai_client(method):
    from agent_framework.openai import OpenAIChatClient

    assert hasattr(OpenAIChatClient, method)


def test_c2_file_search_and_mcp_factory_keywords():
    from agent_framework.openai import OpenAIChatClient

    assert "vector_store_ids" in inspect.signature(OpenAIChatClient.get_file_search_tool).parameters
    p = inspect.signature(OpenAIChatClient.get_mcp_tool).parameters
    assert {"name", "url"} <= set(p)
    assert "headers" in p, "appendix lists get_mcp_tool(name=, url=, headers=)"


def test_c2_openai_chat_client_constructs_offline_with_api_key():
    from agent_framework.openai import OpenAIChatClient

    assert OpenAIChatClient(model="gpt-4o", api_key="sk-test") is not None


def test_c2_vector_rows_exist_in_core():
    import agent_framework as af

    for n in ("create_vector_search_tool", "VectorCollectionContextProvider", "VectorStoreHistoryProvider"):
        assert hasattr(af, n)


# ---------------------------------------------------------------- C.3
async def test_c3_function_decorator_chat_middleware_runs_per_model_call():  # appendix_c_07
    calls = []

    @chat_middleware
    async def my_middleware(context: ChatContext, call_next: Callable[[], Awaitable[None]]) -> None:
        calls.append(len(context.messages))
        await call_next()

    agent = Agent(client=ScriptedChatClient([Reply.text("ok")]), name="a", middleware=[my_middleware])
    assert (await agent.run("hi")).text == "ok"
    assert calls == [1]


async def test_c3_class_based_function_middleware():  # appendix_c_08
    seen = []

    class MyMiddleware(FunctionMiddleware):
        async def process(self, context: FunctionInvocationContext, call_next) -> None:
            seen.append(context.function.name)
            await call_next()

    @tool
    def t(x: str) -> str:
        """t"""
        return "r"

    client = ScriptedChatClient([Reply.tool_call("t", {"x": "1"}), Reply.text("done")])
    await Agent(client=client, name="a", tools=[t], middleware=[MyMiddleware()]).run("go")
    assert seen == ["t"]


async def test_c3_blocking_by_not_calling_call_next():
    @chat_middleware
    async def block(context: ChatContext, call_next) -> None:
        from agent_framework import ChatResponse
        context.result = ChatResponse(messages=[Message("assistant", ["blocked"])])

    client = ScriptedChatClient([Reply.text("should not run")])
    r = await Agent(client=client, name="a", middleware=[block]).run("hi")
    assert r.text == "blocked" and client.requests == []


async def test_c3_not_calling_call_next_without_setting_a_result_crashes_in_1_21_0():
    """MISMATCH: 'simply don't call call_next()' only works if the middleware also sets context.result."""
    @chat_middleware
    async def silent(context: ChatContext, call_next) -> None:
        return

    client = ScriptedChatClient([Reply.text("never")])
    with pytest.raises(AttributeError, match="usage_details"):
        await Agent(client=client, name="a", middleware=[silent]).run("hi")
    assert client.requests == []


async def test_c3_middleware_termination_needs_a_result_too():
    """MISMATCH: raising MiddlewareTermination without context.result -> AttributeError; with result it terminates cleanly."""
    from agent_framework import ChatResponse, MiddlewareTermination

    @chat_middleware
    async def bare(context: ChatContext, call_next) -> None:
        raise MiddlewareTermination

    @chat_middleware
    async def with_result(context: ChatContext, call_next) -> None:
        context.result = ChatResponse(messages=[Message("assistant", ["terminated"])])
        raise MiddlewareTermination

    client = ScriptedChatClient([Reply.text("never")])
    with pytest.raises(AttributeError):
        await Agent(client=client, name="a", middleware=[bare]).run("hi")
    r = await Agent(client=client, name="a", middleware=[with_result]).run("hi")
    assert r.text == "terminated" and client.requests == []


@pytest.mark.parametrize("builder", ["HandoffBuilder", "SequentialBuilder", "GroupChatBuilder",
                                     "ConcurrentBuilder", "MagenticBuilder"])
def test_c3_orchestration_builders_exist(builder):
    assert hasattr(importlib.import_module("agent_framework.orchestrations"), builder)


# ---------------------------------------------------------------- C.4 (appendix_c_09)
@vectorstoremodel
@dataclass
class Doc:
    key: Annotated[str, VectorStoreField("key")]
    text: Annotated[str, VectorStoreField("data", is_full_text_indexed=True)]
    vector: Annotated[list[float] | str | None, VectorStoreField("vector", dimensions=1536)] = None


def test_c4_doc_model_and_filter_construct():
    flt = FilterGroup("and", (Filter("site", "eq", "A14"), Filter("severity", "gte", 3)))
    assert flt.operator == "and" and len(flt.filters) == 2


async def test_c4_filter_on_fields_the_doc_model_lacks_is_rejected_at_search_time():
    """Note: the C.4 filter uses site/severity, which the C.4 Doc model does not declare -> search rejects it."""
    col = InMemoryStore(embedding_generator=HashEmbeddingClient(dim=1536)).get_collection(Doc, collection_name="d")
    await col.ensure_collection_exists()
    await col.upsert([Doc("1", "hello world", vector="hello world")])
    flt = FilterGroup("and", (Filter("site", "eq", "A14"), Filter("severity", "gte", 3)))
    with pytest.raises(Exception):
        [r async for r in await col.search("hello", filter=flt)]
    ok = [r async for r in await col.search("hello", filter=Filter("text", "eq", "hello world"))]
    assert len(ok) == 1


def test_c4_hosting_security_names_exist():
    from agent_framework import register_checkpoint_type  # noqa: F401
    from agent_framework.security import PRINCIPAL_METADATA_KEY, SecureAgentConfig  # noqa: F401
    from agent_framework_foundry_hosting import InvocationsHostServer, ResponsesHostServer  # noqa: F401
    from azure.ai.agentserver.core.tasks import set_resilient_tasks_enabled  # noqa: F401
    from azure.ai.agentserver.responses import ResponsesServerOptions

    assert ResponsesServerOptions(resilient_background=True).resilient_background is True
    assert "agent_session_store_provider" in inspect.signature(ResponsesHostServer.__init__).parameters
    assert "checkpoint_store_provider" in inspect.signature(ResponsesHostServer.__init__).parameters


def test_c4_function_invocation_configuration_has_documented_key():
    c = ScriptedChatClient([Reply.text("x")])
    assert "disable_approval_response_binding" in c.function_invocation_configuration


async def test_c4_evaluation_line_assert_passed_mismatch_and_fix():  # appendix_c_10
    """MISMATCH: `for r in results: r.assert_passed()` -> AttributeError; `r.raise_for_status()` works."""
    from agent_framework import LocalEvaluator, evaluate_agent, keyword_check

    agent = Agent(client=ScriptedChatClient([Reply.text("sunny")]), name="a")
    results = await evaluate_agent(agent=agent, queries=["q"], evaluators=LocalEvaluator(keyword_check("sunny")))
    for r in results:
        with pytest.raises(AttributeError):
            r.assert_passed()
        r.raise_for_status()


def test_c4_purview_line_constructs():
    from agent_framework.microsoft import PurviewPolicyMiddleware, PurviewSettings

    class Cred:
        pass

    mw = PurviewPolicyMiddleware(Cred(), PurviewSettings(app_name="MyApp"))
    agent = Agent(client=ScriptedChatClient([Reply.text("x")]), middleware=[mw])
    assert agent is not None


def test_c4_foundry_evals_line_constructs_offline():
    from agent_framework.foundry import FoundryChatClient, FoundryEvals
    from azure.identity import DefaultAzureCredential

    client = FoundryChatClient(project_endpoint="https://x.services.ai.azure.com/api/projects/p", model="m",
                               credential=DefaultAzureCredential())
    FoundryEvals(client=client, evaluators=[FoundryEvals.RELEVANCE, FoundryEvals.TOOL_CALL_ACCURACY])


async def test_c4_hash_embedding_dims_sanity():
    assert DIM == 8


async def test_c3_context_terminate_flag_has_no_effect_in_1_21_0():
    """MISMATCH: appendix C.3 says 'set context.terminate before/after call_next() for pre/post termination'.
    No such field exists on the contexts; assigning it is silently ignored and the model is still called."""
    from agent_framework import agent_middleware

    @chat_middleware
    async def chat_pre(context: ChatContext, call_next) -> None:
        context.terminate = True
        await call_next()

    @agent_middleware
    async def agent_pre(context, call_next) -> None:
        context.terminate = True
        await call_next()

    for mw in (chat_pre, agent_pre):
        client = ScriptedChatClient([Reply.text("real answer")])
        r = await Agent(client=client, name="a", middleware=[mw]).run("hi")
        assert r.text == "real answer" and len(client.requests) == 1  # NOT terminated


async def test_c3_middleware_termination_with_result_kwarg_still_crashes_at_chat_level():
    from agent_framework import ChatResponse, MiddlewareTermination

    @chat_middleware
    async def mw(context: ChatContext, call_next) -> None:
        raise MiddlewareTermination(result=ChatResponse(messages=[Message("assistant", ["viaresult"])]))

    with pytest.raises(AttributeError):
        await Agent(client=ScriptedChatClient([Reply.text("x")]), name="a", middleware=[mw]).run("hi")
