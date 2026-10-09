"""Afternoon agent 6: a tamper-evident log of every tool call. Each entry hashes the one before it."""
import asyncio
import hashlib
import json
from collections.abc import Awaitable, Callable
from pathlib import Path

from agent_framework import Agent, FunctionInvocationContext, FunctionMiddleware, tool

from afternoon.common import make_client

GENESIS = "0" * 64


def _digest(prev: str, record: dict) -> str:
    return hashlib.sha256((prev + json.dumps(record, sort_keys=True)).encode()).hexdigest()


def _as_text(result) -> str:
    """After call_next(), context.result is a list of Content items, not the tool's raw return value."""
    return "".join(getattr(c, "text", "") or "" for c in result) if isinstance(result, list) else str(result)


class AuditLog(FunctionMiddleware):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.last = GENESIS

    async def process(self, context: FunctionInvocationContext, call_next: Callable[[], Awaitable[None]]) -> None:
        await call_next()
        record = {"tool": context.function.name, "args": dict(context.arguments or {}), "result": _as_text(context.result)[:200]}
        self.last = _digest(self.last, record)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"record": record, "hash": self.last}) + "\n")


def verify(path: Path) -> tuple[bool, int | None]:
    """Replay the chain. Returns (True, None) if intact, else (False, index of the first bad entry)."""
    prev = GENESIS
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        entry = json.loads(line)
        prev = _digest(prev, entry["record"])
        if prev != entry["hash"]:
            return False, i
    return True, None


@tool(approval_mode="never_require")
def lookup_price(item: str) -> str:
    """Look up a price."""
    return {"widget": "4.50", "gadget": "9.00"}.get(item, "unknown")


async def main():
    import tempfile

    from support.fake_client import Reply

    log = Path(tempfile.mkdtemp()) / "audit.jsonl"
    script = [Reply.tool_call("lookup_price", {"item": "widget"}), Reply.tool_call("lookup_price", {"item": "gadget"}),
              Reply.text("A widget is 4.50 and a gadget is 9.00.")]
    agent = Agent(client=make_client(script), instructions="Quote prices.", tools=lookup_price, middleware=[AuditLog(log)])
    print((await agent.run("Price a widget and a gadget.")).text)
    print("intact:", verify(log))
    log.write_text(log.read_text().replace("4.50", "0.50"))  # someone edits history
    print("after tampering:", verify(log))


if __name__ == "__main__":
    asyncio.run(main())
