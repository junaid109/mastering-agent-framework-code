"""Chapter 16: hosting servers are constructed and exercised through their ASGI apps (no network, no model)."""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass

import pytest
from agent_framework import (
    Agent,
    Executor,
    InMemoryHistoryProvider,
    SessionStore,
    Workflow,
    WorkflowBuilder,
    WorkflowContext,
    handler,
)
from agent_framework_foundry_hosting import (
    CheckpointStoreProvider,
    InvocationRun,
    InvocationsHostServer,
    ResponsesHostServer,
    WorkflowTurn,
)
from agent_framework_foundry_hosting._state_store import StoreProvider
from starlette.testclient import TestClient

from support.fake_client import Reply, flatten
from tests.ch15_17.helpers import RecordingClient

pytestmark = pytest.mark.filterwarnings("ignore")


@pytest.fixture(autouse=True)
def _isolated_cwd(tmp_path, monkeypatch):
    """The SDK's local file-backed stores write relative to cwd/HOME; keep that out of the repo."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))


def _client(text="pong", cls=RecordingClient):
    return cls(lambda m: Reply.text(text))


def _agent(client, *, history=True, store_false=True, **kw):
    extra = {}
    if history:
        extra["context_providers"] = [InMemoryHistoryProvider()]
    if store_false:
        extra["default_options"] = {"store": False}
    return Agent(client=client, instructions="Be concise.", **extra, **kw)


def _post(tc, text, prev=None, **extra):
    body = {"model": "x", "input": text, "store": True, **extra}
    if prev:
        body["previous_response_id"] = prev
    return tc.post("/responses", json=body)


# ------------------------------------------------------------------ chapter_16_01
def test_16_01_snippet_foundry_client_constructs_offline_and_server_builds():
    """The real snippet's FoundryChatClient builds with no network; only .run() would bind a port."""
    from agent_framework.foundry import FoundryChatClient
    from azure.identity import DefaultAzureCredential

    client = FoundryChatClient(
        project_endpoint="https://example.services.ai.azure.com/api/projects/p",
        model="gpt-4o", credential=DefaultAzureCredential())
    agent = Agent(client=client, instructions="Be concise.",
                  context_providers=[InMemoryHistoryProvider()], default_options={"store": False})
    server = ResponsesHostServer(agent=agent, history_source="agent")
    assert hasattr(server, "run")


def test_16_01_default_history_source_is_agent_server():
    import inspect
    sig = inspect.signature(ResponsesHostServer.__init__)
    assert sig.parameters["history_source"].default == "agent_server"


def test_16_01_history_source_agent_one_owner_model_sees_each_turn_once():
    client = _client()
    server = ResponsesHostServer(agent=_agent(client), history_source="agent")
    with TestClient(server) as tc:
        r1 = _post(tc, "My name is Ada").json()
        r2 = _post(tc, "What is my name?", prev=r1["id"])
    assert r2.status_code == 200
    seen = [(r, t) for r, k, t in flatten(client.requests[-1]) if k == "text"]
    assert seen == [("user", "My name is Ada"), ("assistant", "pong"), ("user", "What is my name?")]


def test_16_01_agent_server_default_rejects_a_history_provider_that_loads_messages():
    """Book: 'it rejects any history provider configured to load messages'."""
    with pytest.raises(RuntimeError, match="load-enabled HistoryProvider"):
        ResponsesHostServer(agent=_agent(_client()), history_source="agent_server")
    with pytest.raises(RuntimeError, match="load-enabled HistoryProvider"):
        ResponsesHostServer(agent=_agent(_client()))  # default


def test_16_01_agent_server_transcript_comes_from_platform_not_agent():
    client = _client()
    agent = _agent(client, history=False, store_false=False)
    server = ResponsesHostServer(agent=agent)  # default history_source
    with TestClient(server) as tc:
        r1 = _post(tc, "My name is Ada").json()
        r2 = _post(tc, "What is my name?", prev=r1["id"])
    assert r2.status_code == 200
    seen = [(r, t) for r, k, t in flatten(client.requests[-1]) if k == "text"]
    assert seen == [("user", "My name is Ada"), ("assistant", "pong"), ("user", "What is my name?")]  # once, not twice


def test_16_01_agent_server_forces_downstream_storage_off_for_storing_client():
    class StoringClient(RecordingClient):
        STORES_BY_DEFAULT = True

    client = _client(cls=StoringClient)
    server = ResponsesHostServer(agent=Agent(client=client, instructions="x"), history_source="agent_server")
    with TestClient(server) as tc:
        r1 = _post(tc, "hello").json()
        _post(tc, "again", prev=r1["id"])
    assert all(o.get("store") is False for o in client.options_seen)


def test_16_01_invalid_history_source_rejected():
    with pytest.raises(ValueError, match="history_source"):
        ResponsesHostServer(agent=_agent(_client()), history_source="both")  # type: ignore[arg-type]


def test_16_01_exactly_one_of_agent_or_workflow():
    with pytest.raises(ValueError, match="exactly one"):
        ResponsesHostServer()
    with pytest.raises(ValueError, match="exactly one"):
        ResponsesHostServer(agent=_agent(_client(), history=False), workflow=lambda r: None)  # type: ignore[arg-type]


# ------------------------------------------------------------------ chapter_16_02
class RecordingSessionStore(SessionStore):
    gets: list[str] = []
    saves: list[str] = []

    async def get(self, session_id):
        RecordingSessionStore.gets.append(session_id)
        return await super().get(session_id)

    async def set(self, session_id, session, *a, **kw):
        RecordingSessionStore.saves.append(session_id)
        return await super().set(session_id, session, *a, **kw)


class CustomSessionStoreProvider(StoreProvider[SessionStore]):
    def __init__(self):
        self._store = RecordingSessionStore()
        self.requests = 0

    def get_store(self, *, config, platform_context):
        self.requests += 1
        return self._store


def test_16_02_factory_builds_agent_per_request_and_custom_session_store_is_used():
    RecordingSessionStore.gets.clear()
    RecordingSessionStore.saves.clear()
    built = []
    client = _client()

    def create_agent():
        a = Agent(client=client, instructions="x")
        built.append(a)
        return a

    provider = CustomSessionStoreProvider()
    server = ResponsesHostServer(agent=create_agent, history_source="agent_server",
                                 agent_session_store_provider=provider)
    with TestClient(server) as tc:
        r1 = _post(tc, "one").json()
        r2 = _post(tc, "two", prev=r1["id"])
    assert r2.status_code == 200
    assert len(built) == 2 and built[0] is not built[1]  # "build the agent per request"
    assert provider.requests >= 1  # the platform asked OUR provider for the store
    assert RecordingSessionStore.saves, "session snapshots were saved through the custom store"


# ------------------------------------------------------------------ Invocations (prose after 16_02)
def _inv_server(client, **kw):
    seen = {}

    async def parse_request(request):
        body = await request.json()
        return InvocationRun(messages=body["prompt"], options=body.get("options", {}), stream=body.get("stream", False))

    def prepare_options(request, options):
        seen["incoming"] = dict(options)
        return {k: v for k, v in options.items() if k in ("temperature", "max_tokens")}

    server = InvocationsHostServer(Agent(client=client, instructions="x"), parse_request=parse_request,
                                   prepare_options=prepare_options, **kw)
    return server, seen


def test_16_inv_prepare_options_whitelists_caller_options():
    client = _client()
    server, seen = _inv_server(client)
    with TestClient(server) as tc:
        r = tc.post("/invocations?agent_session_id=s1",
                    json={"prompt": "hi", "options": {"temperature": 0.1, "top_p": 0.9, "max_tokens": 7}})
    assert r.status_code == 200 and r.json() == {"response": "pong"}
    assert seen["incoming"] == {"temperature": 0.1, "top_p": 0.9, "max_tokens": 7}
    opts = client.options_seen[0]
    assert opts.get("temperature") == 0.1 and opts.get("max_tokens") == 7
    assert "top_p" not in opts  # the client could not override what the host did not allow


def test_16_inv_streaming_emits_delta_events_then_done_with_session_and_history_is_durable():
    client = _client("streamed")
    server, _ = _inv_server(client)
    with TestClient(server) as tc:
        r = tc.post("/invocations?agent_session_id=s1", json={"prompt": "hi", "stream": True})
        frames = [f for f in r.text.split("\n\n") if f]
        events = [f.split("\n")[0] for f in frames]
        assert events[0] == "event: delta" and events[-1] == "event: done"
        assert json.loads(frames[0].split("data: ")[1]) == {"text": "streamed"}
        assert json.loads(frames[-1].split("data: ")[1]) == {"session_id": "s1"}
        # "a client that sees done knows the conversation state is durable": next turn sees the first
        tc.post("/invocations?agent_session_id=s1", json={"prompt": "again"})
    texts = [(r, t) for r, k, t in flatten(client.requests[-1]) if k == "text"]
    assert texts == [("user", "hi"), ("assistant", "streamed"), ("user", "again")]


def test_16_inv_different_sessions_do_not_share_history():
    client = _client()
    server, _ = _inv_server(client)
    with TestClient(server) as tc:
        tc.post("/invocations?agent_session_id=a", json={"prompt": "secret-a"})
        tc.post("/invocations?agent_session_id=b", json={"prompt": "hello-b"})
    assert "secret-a" not in " ".join(t for _, _, t in flatten(client.requests[-1]))


def test_16_inv_constructor_requires_exactly_one_of_agent_or_workflow():
    with pytest.raises(TypeError):
        InvocationsHostServer()
    with pytest.raises(TypeError):
        InvocationsHostServer(Agent(client=_client(), instructions="x"), workflow=lambda r: None)  # type: ignore[arg-type]


# ------------------------------------------------------------------ chapter_16_03
@dataclass
class CountdownRequest:
    n: int


class StartExecutor(Executor):
    def __init__(self):
        super().__init__(id="start")

    @handler
    async def go(self, req: CountdownRequest, ctx: WorkflowContext[CountdownRequest]) -> None:
        await ctx.send_message(req)


class CountdownExecutor(Executor):
    def __init__(self):
        super().__init__(id="countdown")

    @handler
    async def step(self, req: CountdownRequest, ctx: WorkflowContext[CountdownRequest, str]) -> None:
        await ctx.yield_output(f"tick {req.n}")
        if req.n > 1:
            await ctx.send_message(CountdownRequest(req.n - 1))


def build_workflow(request) -> Workflow:
    """Body of the book's build_workflow (the book omits the `Workflow` import, see RESULTS)."""
    start, countdown = StartExecutor(), CountdownExecutor()
    return (WorkflowBuilder(name="countdown-workflow-v1", start_executor=start)
            .add_edge(start, countdown).add_edge(countdown, countdown).build())


async def parse_response(request):
    return WorkflowTurn(input=CountdownRequest(int(await request.get_input_text())))


def _wf_server(**kw):
    from azure.ai.agentserver.responses import ResponsesServerOptions

    return ResponsesHostServer(
        workflow=build_workflow,
        parse_response=parse_response,
        checkpoint_store_provider=CheckpointStoreProvider(
            allowed_checkpoint_types=[f"{CountdownRequest.__module__}:{CountdownRequest.__qualname__}"]),
        options=ResponsesServerOptions(resilient_background=True),
        **kw,
    )


def test_16_03_book_snippet_workflow_host_runs_and_yields_outputs():
    from azure.ai.agentserver.core.tasks import set_resilient_tasks_enabled
    set_resilient_tasks_enabled(True)
    try:
        server = _wf_server()
        with TestClient(server) as tc:
            r = _post(tc, "3")
        assert r.status_code == 200
        out = [c["text"] for item in r.json()["output"] for c in item["content"]]
        assert out == ["tick 3", "tick 2", "tick 1"]
    finally:
        set_resilient_tasks_enabled(False)


def test_16_03_background_start_returns_immediately_and_can_be_polled():
    """Client starts with {"background": true, "store": true} and polls the response."""
    from azure.ai.agentserver.core.tasks import set_resilient_tasks_enabled
    set_resilient_tasks_enabled(True)
    try:
        server = _wf_server()
        with TestClient(server) as tc:
            r = tc.post("/responses", json={"model": "x", "input": "2", "background": True, "store": True})
            assert r.status_code == 200
            rid = r.json()["id"]
            deadline = time.time() + 20
            status = r.json()["status"]
            while status not in ("completed", "failed") and time.time() < deadline:
                time.sleep(0.2)
                status = tc.get(f"/responses/{rid}").json()["status"]
        assert status == "completed"
    finally:
        set_resilient_tasks_enabled(False)


def test_16_03_workflow_instance_cannot_be_resilient_a_factory_is_required():
    """Book: 'The workflow is passed as a factory ... because workflow instances are single-use'."""
    from azure.ai.agentserver.responses import ResponsesServerOptions

    with pytest.raises(ValueError, match="request-aware factory"):
        ResponsesHostServer(workflow=build_workflow(None), parse_response=parse_response,
                            options=ResponsesServerOptions(resilient_background=True))


def test_16_03_workflow_hosting_requires_parse_response():
    with pytest.raises(TypeError, match="parse_response"):
        ResponsesHostServer(workflow=build_workflow)


def test_16_03_workflow_host_rejects_agent_history_policies():
    with pytest.raises(ValueError, match="checkpoint history"):
        ResponsesHostServer(workflow=build_workflow, parse_response=parse_response, history_source="agent")


def test_16_03_allowed_checkpoint_types_is_enforced_by_the_provider():
    """Without the allow-list the host refuses a typed turn before any executor runs."""
    bare = CheckpointStoreProvider()
    with pytest.raises(Exception, match="(?i)blocked|not allowed|allow"):
        bare.validate_checkpoint_value(CountdownRequest(3))
    CheckpointStoreProvider(
        allowed_checkpoint_types=[f"{CountdownRequest.__module__}:{CountdownRequest.__qualname__}"]
    ).validate_checkpoint_value(CountdownRequest(3))


def test_16_03_missing_allowlist_fails_the_hosted_request():
    server = ResponsesHostServer(workflow=build_workflow, parse_response=parse_response)  # no allow-list
    with TestClient(server, raise_server_exceptions=False) as tc:
        r = _post(tc, "3")
    body = r.text
    assert "tick 3" not in body  # executor never ran
    assert r.status_code >= 400 or '"status":"failed"' in body.replace(" ", "")


def test_16_05_steering_is_rejected_at_construction_in_python():
    """Book 16.5: 'the host deliberately rejects steerable_conversations=True at construction'."""
    from azure.ai.agentserver.responses import ResponsesServerOptions

    with pytest.raises(RuntimeError, match="steerable_conversations=True is temporarily unavailable"):
        ResponsesHostServer(agent=_agent(_client(), history=False), options=ResponsesServerOptions(steerable_conversations=True))


def test_16_05_plain_agent_resilient_background_not_available_by_default():
    """Book: 'plain agents recover only best-effort'. 1.21 actually *refuses* resilient_background for a regular agent
    unless history_source='service' + background_source='provider'."""
    from azure.ai.agentserver.responses import ResponsesServerOptions

    with pytest.raises(RuntimeError, match="resilient_background"):
        ResponsesHostServer(agent=_agent(_client(), history=False),
                            options=ResponsesServerOptions(resilient_background=True))


# ------------------------------------------------------------------ 16.3 identifiers
def test_16_03_session_identifiers_exist_on_agent_session():
    from agent_framework import AgentSession
    from agent_framework.foundry import FOUNDRY_HOSTED_AGENT_SESSION_ID_KEY

    s = AgentSession(session_id="local-1", service_session_id="resp_123")
    s.state[FOUNDRY_HOSTED_AGENT_SESSION_ID_KEY] = "runtime-9"
    assert (s.session_id, s.service_session_id) == ("local-1", "resp_123")
    assert s.state[FOUNDRY_HOSTED_AGENT_SESSION_ID_KEY] == "runtime-9"
    restored = AgentSession.from_dict(s.to_dict())
    assert restored.state[FOUNDRY_HOSTED_AGENT_SESSION_ID_KEY] == "runtime-9"
    assert restored.service_session_id == "resp_123"
