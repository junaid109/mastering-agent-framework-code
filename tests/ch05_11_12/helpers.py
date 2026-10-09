"""Local helpers for ch05/11/12 tests (does not modify support/fake_client.py).

UsageScriptedClient: same as ScriptedChatClient, but every model reply carries usage_details,
so chapter 5.5's usage-tracking middleware has something to observe (streaming and non-streaming).
"""
from __future__ import annotations

from agent_framework import (
    ChatMiddlewareLayer,
    ChatResponse,
    ChatResponseUpdate,
    Content,
    FunctionInvocationLayer,
    Message,
    ResponseStream,
)
from agent_framework.observability import ChatTelemetryLayer

from support.fake_client import Reply, ScriptedChatClient, ScriptedRaw  # noqa: F401

USAGE = {"input_token_count": 11, "output_token_count": 7, "total_token_count": 18}


class UsageRaw(ScriptedRaw):
    def _inner_get_response(self, *, messages, stream, options, **kwargs):  # type: ignore[override]
        reply = self._next(messages)
        contents = self._contents(reply)
        if stream:
            async def _gen():
                yield ChatResponseUpdate(role="assistant", contents=contents)
                yield ChatResponseUpdate(role="assistant", contents=[Content.from_usage(dict(USAGE))])

            return ResponseStream(_gen(), finalizer=lambda updates: ChatResponse.from_updates(updates))

        async def _respond() -> ChatResponse:
            return ChatResponse(
                messages=[Message(role="assistant", contents=contents)],
                response_id="scripted",
                usage_details=dict(USAGE),
            )

        return _respond()


class UsageScriptedClient(FunctionInvocationLayer, ChatMiddlewareLayer, ChatTelemetryLayer, UsageRaw):
    def __init__(self, script, **kwargs):
        super().__init__(script=script, **kwargs)
