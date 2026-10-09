"""Afternoon agent 5: a bouncer in front of every tool call. Allow-list, argument rules, human queue, reasons."""
import asyncio
import re
from collections.abc import Awaitable, Callable

from agent_framework import Agent, FunctionInvocationContext, FunctionMiddleware, tool

from afternoon.common import make_client

DENY_ARGS = [re.compile(p) for p in (r"rm\s+-rf", r"\.\./", r"(?i)api[_-]?key|password|secret")]


class Bouncer(FunctionMiddleware):
    """Deny by default. Every refusal tells the model why, so it can recover instead of retrying blindly."""

    def __init__(self, allow: set[str], ask_human: set[str], approve: Callable[[str, dict], bool]) -> None:
        self.allow, self.ask_human, self.approve = allow, ask_human, approve
        self.log: list[tuple[str, str]] = []  # (tool, decision)

    def _verdict(self, name: str, args: dict) -> str | None:
        if name not in self.allow:
            return f"'{name}' is not on this agent's allow-list. Allowed: {sorted(self.allow)}."
        text = " ".join(str(v) for v in args.values())
        for rule in DENY_ARGS:
            if rule.search(text):
                return f"Arguments matched the blocked pattern {rule.pattern!r}."
        if name in self.ask_human and not self.approve(name, args):
            return "A human reviewer declined this call."
        return None

    async def process(self, context: FunctionInvocationContext, call_next: Callable[[], Awaitable[None]]) -> None:
        name, args = context.function.name, dict(context.arguments or {})
        reason = self._verdict(name, args)
        self.log.append((name, "blocked" if reason else "allowed"))
        if reason:
            context.result = f"BLOCKED: {reason}"  # the model reads this as the tool's result
            return  # skipping call_next() means the tool never runs
        await call_next()


@tool(approval_mode="never_require")
def read_note(name: str) -> str:
    """Read a note."""
    return f"(contents of {name})"


@tool(approval_mode="never_require")
def run_shell(command: str) -> str:
    """Run a shell command."""
    return f"ran: {command}"


def build_agent(client, bouncer: Bouncer) -> Agent:
    return Agent(client=client, name="Guarded", instructions="Use tools to do the task.",
                 tools=[read_note, run_shell], middleware=[bouncer])


async def main():
    from support.fake_client import Reply

    bouncer = Bouncer(allow={"read_note", "run_shell"}, ask_human={"run_shell"}, approve=lambda n, a: False)
    script = [Reply.tool_call("read_note", {"name": "../secrets.txt"}), Reply.tool_call("run_shell", {"command": "ls"}),
              Reply.text("I could not complete that.")]
    print((await build_agent(make_client(script), bouncer).run("Tidy up.")).text)
    print(bouncer.log)


if __name__ == "__main__":
    asyncio.run(main())
