"""Afternoon agent 7: do not believe "I saved it". Check what actually ran, and make the model retry."""
import asyncio
import re
from collections.abc import Awaitable, Callable
from pathlib import Path

from agent_framework import Agent, FunctionInvocationContext, FunctionMiddleware, tool

from afternoon.common import make_client

CLAIM = re.compile(r"\b(saved|wrote|written|created|stored)\b", re.I)


class Recorder(FunctionMiddleware):
    """Remembers which tools finished without raising."""

    def __init__(self) -> None:
        self.succeeded: list[str] = []

    async def process(self, context: FunctionInvocationContext, call_next: Callable[[], Awaitable[None]]) -> None:
        await call_next()
        self.succeeded.append(context.function.name)


def build_agent(client, folder: Path, recorder: Recorder) -> Agent:
    @tool(approval_mode="never_require")
    def write_file(name: str, content: str) -> str:
        """Write a text file."""
        (folder / name).write_text(content, encoding="utf-8")
        return f"wrote {name}"

    return Agent(client=client, name="Writer", instructions="Do what is asked using write_file.",
                 tools=write_file, middleware=[recorder])


async def run_checked(agent: Agent, recorder: Recorder, query: str, retries: int = 2):
    """Returns (response, how many times a false claim was caught)."""
    session = agent.create_session()
    result = await agent.run(query, session=session)
    caught = 0
    while CLAIM.search(result.text or "") and "write_file" not in recorder.succeeded and caught < retries:
        caught += 1
        result = await agent.run("You said it was saved, but write_file has not run. Call it now, or say plainly that you could not.",
                                 session=session)
    return result, caught


async def main():
    import tempfile

    from support.fake_client import Reply

    folder = Path(tempfile.mkdtemp())
    script = [Reply.text("Done, I saved notes.txt."),  # a false claim: nothing ran
              Reply.tool_call("write_file", {"name": "notes.txt", "content": "hello"}), Reply.text("Saved notes.txt.")]
    recorder = Recorder()
    result, caught = await run_checked(build_agent(make_client(script), folder, recorder), recorder, "Save a note saying hello.")
    print(f"false claims caught: {caught}; file exists: {(folder / 'notes.txt').exists()}; reply: {result.text}")


if __name__ == "__main__":
    asyncio.run(main())
