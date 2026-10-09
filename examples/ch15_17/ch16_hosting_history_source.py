"""Chapter 16 - ResponsesHostServer (history_source) and InvocationsHostServer exercised through their ASGI apps.

Nothing binds a port: Starlette's TestClient drives the same app that .run() would serve.
"""
import asyncio
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
_tmp = tempfile.mkdtemp()                      # keep the SDK's local stores out of the home directory
os.environ["HOME"] = os.environ["USERPROFILE"] = _tmp
os.chdir(_tmp)

from agent_framework import Agent, InMemoryHistoryProvider  # noqa: E402
from agent_framework_foundry_hosting import InvocationRun, InvocationsHostServer, ResponsesHostServer  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from support.fake_client import Reply, ScriptedChatClient, flatten  # noqa: E402


def make_client(text="pong"):
    if os.environ.get("BOOK_CLIENT") == "openai-compatible":
        from agent_framework.openai import OpenAIChatCompletionClient

        return OpenAIChatCompletionClient(base_url=os.environ["BOOK_BASE_URL"],
                                          api_key=os.environ.get("BOOK_API_KEY", "not-needed"),
                                          model=os.environ["BOOK_MODEL"])
    return ScriptedChatClient(lambda messages: Reply.text(text))


def seen_by_model(client):
    return [(r, t) for r, k, t in flatten(client.requests[-1]) if k == "text"] if hasattr(client, "requests") else "n/a"


def responses_demo():
    # The agent owns history: InMemoryHistoryProvider + store=False, history_source="agent"
    client = make_client()
    agent = Agent(client=client, instructions="Be concise.", context_providers=[InMemoryHistoryProvider()],
                  default_options={"store": False})
    server = ResponsesHostServer(agent=agent, history_source="agent")
    with TestClient(server) as tc:
        first = tc.post("/responses", json={"model": "x", "input": "My name is Ada", "store": True}).json()
        tc.post("/responses", json={"model": "x", "input": "What is my name?", "store": True,
                                    "previous_response_id": first["id"]})
    print("history_source='agent'        model saw:", seen_by_model(client))

    # The platform owns history (the default). A history provider that LOADS messages is rejected up front.
    try:
        ResponsesHostServer(agent=Agent(client=make_client(), context_providers=[InMemoryHistoryProvider()]))
    except RuntimeError as e:
        print("history_source='agent_server' + InMemoryHistoryProvider ->", str(e)[:70], "...")
    client2 = make_client()
    server2 = ResponsesHostServer(agent=Agent(client=client2, instructions="Be concise."))
    with TestClient(server2) as tc:
        first = tc.post("/responses", json={"model": "x", "input": "My name is Ada", "store": True}).json()
        tc.post("/responses", json={"model": "x", "input": "What is my name?", "store": True,
                                    "previous_response_id": first["id"]})
    print("history_source='agent_server' model saw:", seen_by_model(client2))


def invocations_demo():
    client = make_client("streamed")

    async def parse_request(request):
        body = await request.json()
        return InvocationRun(messages=body["prompt"], options=body.get("options", {}), stream=body.get("stream", False))

    def prepare_options(request, options):            # whitelist caller-controlled options
        return {k: v for k, v in options.items() if k in ("temperature", "max_tokens")}

    server = InvocationsHostServer(Agent(client=client, instructions="x"), parse_request=parse_request,
                                   prepare_options=prepare_options)
    with TestClient(server) as tc:
        r = tc.post("/invocations?agent_session_id=s1", json={"prompt": "hi", "stream": True})
        print("stream frames:", [f.split("\n")[0] for f in r.text.split("\n\n") if f])
        r = tc.post("/invocations?agent_session_id=s1",
                    json={"prompt": "again", "options": {"temperature": 0.2, "top_p": 0.9}})
        print("json reply:", r.json())


async def main():
    responses_demo()
    invocations_demo()


if __name__ == "__main__":
    asyncio.run(main())
