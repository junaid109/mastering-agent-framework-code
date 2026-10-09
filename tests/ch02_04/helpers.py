"""Helpers local to group ch02_04 (does not modify support/fake_client.py)."""
from __future__ import annotations

from typing import Any

from support.fake_client import Reply, ScriptedChatClient, flatten  # noqa: F401


class RecordingClient(ScriptedChatClient):
    """ScriptedChatClient that also records the per-request `options` and kwargs.

    Needed to assert on things the base fake does not expose, e.g. response_format
    or the hosted-tool dicts that reach the model.
    """

    def __init__(self, script, **kwargs: Any) -> None:
        super().__init__(script, **kwargs)
        self.options_seen: list[dict[str, Any]] = []

    def _inner_get_response(self, *, messages, stream, options, **kwargs):  # type: ignore[override]
        snap = dict(options or {})
        if isinstance(snap.get('tools'), list):
            snap['tools'] = list(snap['tools'])  # snapshot: the framework mutates this list in place
        self.options_seen.append(snap)
        return super()._inner_get_response(messages=messages, stream=stream, options=options, **kwargs)


def texts(messages) -> list[str]:
    return [t for (_r, ty, t) in flatten(messages) if ty == "text"]
