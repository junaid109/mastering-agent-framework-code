"""Chapter 10.1 - FastAPI / Flask integration (snippet chapter_10_01)."""
import importlib.util
import os
import pathlib
import warnings

import httpx
import pytest
from fastapi.testclient import TestClient

warnings.filterwarnings("ignore")
ROOT = pathlib.Path(__file__).resolve().parents[2]


def _load_example():
    spec = importlib.util.spec_from_file_location("ch10_fastapi_responses", ROOT / "examples/ch09_10_app/fastapi_responses.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ex = _load_example()
from support.fake_client import Reply, ScriptedChatClient, flatten  # noqa: E402


def test_book_snippet_as_printed_has_undefined_names():
    """MISMATCH (minor): the snippet uses Request/Response without importing them."""
    src = (ROOT / "book_snippets/chapter_10_01.py").read_text()
    with pytest.raises(NameError, match="Request"):
        exec(compile(src, "chapter_10_01.py", "exec"), {})


def test_book_snippet_with_imports_registers_route():
    """With `from fastapi import Request, Response` added the book's skeleton is a valid route."""
    src = (ROOT / "book_snippets/chapter_10_01.py").read_text()
    src = src.replace("from fastapi import FastAPI", "from fastapi import FastAPI, Request, Response")
    ns: dict = {}
    exec(compile(src, "chapter_10_01.py", "exec"), ns)
    paths = {(r.path, tuple(r.methods)) for r in ns["app"].routes if hasattr(r, "methods")}
    assert ("/responses", ("POST",)) in paths


def test_filled_in_route_roundtrip():
    client = ScriptedChatClient([Reply.text("Paris.")])
    http = TestClient(ex.build_app(client))
    r = http.post("/responses", json={"input": "Capital of France?"})
    assert r.status_code == 200
    body = r.json()
    assert body["output"][0]["content"][0]["text"] == "Paris."
    assert body["id"].startswith("resp_")
    assert ("user", "text", "Capital of France?") in flatten(client.requests[0])


def test_session_continues_with_conversation_id():
    client = ScriptedChatClient([Reply.text("Paris."), Reply.text("France.")])
    http = TestClient(ex.build_app(client))
    first = http.post("/responses", json={"input": "Capital of France?"}).json()
    conv = first["conversation"]["id"] if isinstance(first.get("conversation"), dict) else first["conversation"]
    http.post("/responses", json={"input": "Which country?", "conversation": conv})
    texts = [t for _, _, t in flatten(client.requests[1])]
    assert "Capital of France?" in texts and "Paris." in texts and "Which country?" in texts


def test_invalid_continuation_rejected():
    http = TestClient(ex.build_app(ScriptedChatClient([Reply.text("x")])))
    r = http.post("/responses", json={"input": "hi", "previous_response_id": "resp_a", "conversation": "conv_b"})
    assert r.status_code == 400


def test_untrusted_session_id_leaks_history_without_authz_and_partitioning_fixes_it():
    """Book 10.1: previous_response_id/conversation_id are untrusted; partition by tenant."""
    from fastapi import FastAPI, Header, HTTPException, Request
    from agent_framework import Agent
    from agent_framework_hosting import AgentState
    from agent_framework_hosting_responses import responses_session_id, responses_to_run

    def make(partition: bool):
        client = ScriptedChatClient(lambda m: Reply.text("ok"))
        state = AgentState(Agent(client=client, name="a", instructions="x"))
        app = FastAPI()

        @app.post("/r")
        async def r(request: Request, x_tenant: str = Header()):
            body = await request.json()
            sid, _ = responses_session_id(body)
            key = f"{x_tenant}:{sid}" if partition else sid
            session = await state.get_or_create_session(key)
            args = responses_to_run(body)
            await (await state.get_target()).run(args["messages"], session=session)
            await state.set_session(key, session)
            return {}

        return TestClient(app), client

    for partition, leaks in [(False, True), (True, False)]:
        http, client = make(partition)
        http.post("/r", json={"input": "alice secret", "conversation": "conv_shared"}, headers={"x-tenant": "alice"})
        http.post("/r", json={"input": "mallory asks", "conversation": "conv_shared"}, headers={"x-tenant": "mallory"})
        seen = [t for _, _, t in flatten(client.requests[-1])]
        assert ("alice secret" in seen) is leaks


def test_flask_bridge_runs_async_agent():
    """Book: Flask is possible if you bridge the async call yourself."""
    import asyncio

    flask = pytest.importorskip("flask")
    from agent_framework import Agent

    agent = Agent(client=ScriptedChatClient([Reply.text("from flask")]), name="a", instructions="x")
    app = flask.Flask(__name__)

    @app.post("/ask")
    def ask():
        result = asyncio.run(agent.run(flask.request.json["q"]))
        return {"text": result.text}

    r = app.test_client().post("/ask", json={"q": "hi"})
    assert r.get_json() == {"text": "from flask"}


@pytest.mark.asyncio
async def test_asgi_transport_streaming_free_call():
    app = ex.build_app(ScriptedChatClient([Reply.text("async ok")]))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as h:
        r = await h.post("/responses", json={"input": "hi"})
    assert r.json()["output"][0]["content"][0]["text"] == "async ok"
