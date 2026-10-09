"""Afternoon agent 4: ask questions about a folder of notes. Keyword search, citations, follow-ups."""
import asyncio
from pathlib import Path

from agent_framework import Agent, tool

from afternoon.common import make_client


def build_agent(client, root: Path) -> Agent:
    @tool(approval_mode="never_require")
    def search_notes(query: str) -> list[str]:
        """Find notes containing every word in the query. Returns 'file: matching line' strings."""
        words = query.lower().split()
        hits = []
        for path in sorted(root.glob("*.txt")):
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                if all(w in line.lower() for w in words):
                    hits.append(f"{path.name}: {line.strip()}")
        return hits[:5] or ["No matching notes."]

    return Agent(
        client=client,
        name="NotesChat",
        instructions="Answer only from search_notes results. Cite the file name in brackets. If nothing matches, say so.",
        tools=search_notes,
    )


async def main():
    import tempfile

    from support.fake_client import Reply

    root = Path(tempfile.mkdtemp())
    (root / "q3.txt").write_text("Budget approved: 40k for the venue.\nHiring freeze until October.")
    script = [Reply.tool_call("search_notes", {"query": "budget"}), Reply.text("The budget is 40k for the venue [q3.txt]."),
              Reply.text("Yes, hiring is frozen until October [q3.txt].")]
    agent = build_agent(make_client(script), root)
    session = agent.create_session()  # the session is what makes the follow-up work
    for question in ("What budget was approved?", "And is hiring affected?"):
        print((await agent.run(question, session=session)).text)


if __name__ == "__main__":
    asyncio.run(main())
