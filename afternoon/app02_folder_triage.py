"""Afternoon agent 2: sort a folder of files into categories. Read-only, and confined to the folder."""
import asyncio
from pathlib import Path
from typing import Literal

from agent_framework import Agent, tool
from pydantic import BaseModel

from afternoon.common import make_client


class FileTriage(BaseModel):
    name: str
    category: Literal["invoice", "notes", "contract", "other"]
    reason: str


class Triage(BaseModel):
    files: list[FileTriage]


def build_agent(client, root: Path) -> Agent:
    root = root.resolve()

    @tool(approval_mode="never_require")
    def list_files() -> list[str]:
        """List the file names in the folder."""
        return sorted(p.name for p in root.iterdir() if p.is_file())

    @tool(approval_mode="never_require")
    def read_file(name: str) -> str:
        """Read the first 2000 characters of a file in the folder."""
        path = (root / name).resolve()
        if root not in path.parents:  # blocks ../ and absolute paths
            return "Error: only files inside the folder can be read."
        return path.read_text(encoding="utf-8", errors="replace")[:2000]

    return Agent(
        client=client,
        name="Triage",
        instructions="List the files, read each one, and classify it. Answer only with the requested JSON.",
        tools=[list_files, read_file],
        default_options={"response_format": Triage},
    )


async def main():
    import tempfile

    from support.fake_client import Reply

    root = Path(tempfile.mkdtemp())
    (root / "inv-104.txt").write_text("Invoice 104. Amount due: 420 GBP.")
    (root / "standup.txt").write_text("Notes: shipped the login fix.")
    answer = Triage(files=[FileTriage(name="inv-104.txt", category="invoice", reason="amount due"),
                           FileTriage(name="standup.txt", category="notes", reason="meeting notes")])
    script = [Reply.tool_call("list_files"), Reply.tool_call("read_file", {"name": "inv-104.txt"}),
              Reply.tool_call("read_file", {"name": "standup.txt"}), Reply.text(answer.model_dump_json())]
    result = await build_agent(make_client(script), root).run("Triage the folder.")
    for f in result.value.files:
        print(f"{f.name:12} {f.category:9} {f.reason}")


if __name__ == "__main__":
    asyncio.run(main())
