"""Snippet chapter_10_02: provider-specific typed options. Uses a mocked HTTP transport (no network)."""
import json
import warnings

import httpx
import pytest
from agent_framework import Message
from agent_framework.openai import OpenAIChatClient, OpenAIChatOptions
from openai import AsyncOpenAI

warnings.filterwarnings("ignore")


def _client():
    seen: list[dict] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(json.loads(req.content))
        body = {
            "id": "resp_1", "object": "response", "created_at": 0, "status": "completed", "model": "m",
            "output": [{"type": "message", "id": "m1", "role": "assistant", "status": "completed",
                        "content": [{"type": "output_text", "text": "Paris", "annotations": []}]}],
            "parallel_tool_calls": True, "tool_choice": "auto", "tools": [],
            "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2,
                      "input_tokens_details": {"cached_tokens": 0}, "output_tokens_details": {"reasoning_tokens": 0}},
        }
        return httpx.Response(200, json=body)

    ac = AsyncOpenAI(api_key="k", base_url="http://x/v1", http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    return OpenAIChatClient(async_client=ac, model="m"), seen


MSG = [Message("user", contents=["What is the capital of France?"])]


async def test_snippet_as_printed_fails_reasoning_effort_rejected_by_sdk():
    """MISMATCH chapter-10:57. reasoning_effort is not a valid key for the Responses-based OpenAIChatClient."""
    client, _ = _client()
    with pytest.raises(Exception, match="reasoning_effort"):
        await client.get_response(MSG, options=OpenAIChatOptions(temperature=0.7, reasoning_effort="medium"))


async def test_corrected_snippet_reasoning_dict_reaches_wire():
    client, seen = _client()
    response = await client.get_response(MSG, options=OpenAIChatOptions(temperature=0.7, reasoning={"effort": "medium"}))
    assert response.text == "Paris"
    assert seen[0]["temperature"] == 0.7
    assert seen[0]["reasoning"] == {"effort": "medium"}


def test_typed_options_are_plain_typeddict_at_runtime():
    opts = OpenAIChatOptions(temperature=0.7, reasoning={"effort": "medium"})
    assert isinstance(opts, dict) and opts["temperature"] == 0.7


def test_openai_chat_client_requires_configuration(monkeypatch):
    """`OpenAIChatClient(...)` (placeholder args) needs configuration; without any it raises, with env it builds."""
    for k in ("OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_BASE_URL"):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(Exception):
        OpenAIChatClient()
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("OPENAI_MODEL", "m")
    OpenAIChatClient()
