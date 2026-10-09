"""Afternoon agent 3: review a diff with read-only tools and a hard cap on how much it may read."""
import asyncio
from pathlib import Path
from typing import Literal

from agent_framework import Agent, tool
from pydantic import BaseModel

from afternoon.common import make_client


class Finding(BaseModel):
    severity: Literal["high", "medium", "low"]
    file: str
    issue: str


class Review(BaseModel):
    findings: list[Finding]


def build_agent(client, diff: str, repo: Path, max_reads: int = 3) -> Agent:
    repo = repo.resolve()

    @tool(approval_mode="never_require")
    def read_diff() -> str:
        """Return the diff under review."""
        return diff

    @tool(approval_mode="never_require", max_invocations=max_reads)  # the hard cap lives on the tool
    def read_file(path: str) -> str:
        """Read a file from the repository for context."""
        target = (repo / path).resolve()
        if repo not in target.parents:
            return "Error: path is outside the repository."
        return target.read_text(encoding="utf-8", errors="replace")[:3000]

    return Agent(
        client=client,
        name="Reviewer",
        instructions="Review the diff for bugs and security problems. Read only what you need. Answer with the JSON.",
        tools=[read_diff, read_file],
        default_options={"response_format": Review},
    )


async def main():
    import tempfile

    from support.fake_client import Reply

    repo = Path(tempfile.mkdtemp())
    (repo / "db.py").write_text("def find(name):\n    return run('select * from users where name=' + name)\n")
    diff = "+    return run('select * from users where name=' + name)"
    found = Review(findings=[Finding(severity="high", file="db.py", issue="SQL built by string concatenation")])
    script = [Reply.tool_call("read_diff"), Reply.tool_call("read_file", {"path": "db.py"}), Reply.text(found.model_dump_json())]
    result = await build_agent(make_client(script), diff, repo).run("Review this pull request.")
    for f in result.value.findings:
        print(f"[{f.severity}] {f.file}: {f.issue}")


if __name__ == "__main__":
    asyncio.run(main())
