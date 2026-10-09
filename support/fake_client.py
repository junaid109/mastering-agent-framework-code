"""A scripted chat client so book examples run offline and deterministically.

It is composed from the same layers as the framework's real clients (function invocation,
chat middleware, telemetry), so tools, middleware, sessions and approvals behave as they do
against a real model. Only the model's *decisions* are scripted.

Usage:
    client = ScriptedChatClient([
        Reply.tool_call("get_weather", {"city": "Seattle"}),   # model asks for a tool
        Reply.text("It is sunny in Seattle."),                 # then answers
    ])
"""
from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from agent_framework import (
    BaseChatClient,
    ChatMiddlewareLayer,
    ChatResponse,
    ChatResponseUpdate,
    Content,
    FunctionInvocationLayer,
    Message,
    ResponseStream,
)
from agent_framework.observability import ChatTelemetryLayer


@dataclass
class Reply:
    """One scripted model turn: plain text and/or tool calls."""

    text: str | None = None
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    @staticmethod
    def text_reply(text: str) -> "Reply":
        return Reply(text=text)

    @staticmethod
    def tool_call(name: str, arguments: dict[str, Any] | None = None) -> "Reply":
        return Reply(calls=[(name, arguments or {})])

    # convenient alias
    text = None  # replaced below


def _text(text: str) -> Reply:
    return Reply(text=text)


def _tool(name: str, arguments: dict[str, Any] | None = None) -> Reply:
    return Reply(calls=[(name, arguments or {})])


class _Reply(Reply):
    pass


class ScriptedRaw(BaseChatClient):
    """Raw client: returns the next scripted reply (or calls a function to decide)."""

    OTEL_PROVIDER_NAME = "scripted"

    def __init__(self, *, script: Sequence[Reply] | Callable[[Sequence[Message]], Reply], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._script = script
        self._i = 0
        self.requests: list[list[Message]] = []  # every request the "model" received

    def _next(self, messages: Sequence[Message]) -> Reply:
        self.requests.append(list(messages))
        if callable(self._script):
            return self._script(messages)
        if self._i >= len(self._script):
            return Reply(text="(script exhausted)")
        r = self._script[self._i]
        self._i += 1
        return r

    def _contents(self, r: Reply) -> list[Content]:
        out: list[Content] = []
        if r.text:
            out.append(Content.from_text(r.text))
        for n, (name, args) in enumerate(r.calls):
            out.append(Content.from_function_call(call_id=f"call_{self._i}_{n}", name=name, arguments=json.dumps(args)))
        return out

    def _inner_get_response(self, *, messages, stream, options, **kwargs):  # type: ignore[override]
        reply = self._next(messages)
        contents = self._contents(reply)
        if stream:
            async def _gen():
                yield ChatResponseUpdate(role="assistant", contents=contents)

            def _final(updates):
                return ChatResponse.from_updates(updates)

            return ResponseStream(_gen(), finalizer=_final)

        async def _respond() -> ChatResponse:
            return ChatResponse(messages=[Message(role="assistant", contents=contents)], response_id="scripted")

        return _respond()


class ScriptedChatClient(FunctionInvocationLayer, ChatMiddlewareLayer, ChatTelemetryLayer, ScriptedRaw):
    """Full-featured scripted client (tools + middleware + telemetry)."""

    def __init__(self, script: Sequence[Reply] | Callable[[Sequence[Message]], Reply], **kwargs: Any) -> None:
        super().__init__(script=script, **kwargs)


# Friendly constructors used by the tests
Reply.text = staticmethod(_text)  # type: ignore[method-assign]
Reply.tool_call = staticmethod(_tool)  # type: ignore[method-assign]


def flatten(messages) -> list[tuple[str, str, str]]:
    """(role, content type, text/name/result) for each content item, for easy assertions."""
    out = []
    for m in messages:
        for c in m.contents:
            val = getattr(c, "text", None) or getattr(c, "result", None) or getattr(c, "name", None) or ""
            out.append((str(m.role), c.type, str(val)))
    return out
