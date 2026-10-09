"""Afternoon agent 8: pasted emails become tracker rows, and the code (not the model) checks they landed."""
import asyncio
import csv
from pathlib import Path

from agent_framework import Agent, tool

from afternoon.common import make_client


def build_agent(client, csv_path: Path) -> Agent:
    @tool(approval_mode="never_require")
    def add_row(sender: str, subject: str, action: str, due: str) -> str:
        """Append one row to the tracker. Use due='none' if the email gives no date."""
        new = not csv_path.exists()
        with csv_path.open("a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["sender", "subject", "action", "due"])
            w.writerow([sender, subject, action, due])
        return "row added"

    return Agent(client=client, name="Tracker", instructions="Call add_row once per email. Never skip an email.", tools=add_row)


def subjects_in(csv_path: Path) -> set[str]:
    if not csv_path.exists():
        return set()
    with csv_path.open(newline="", encoding="utf-8") as f:
        return {row["subject"] for row in csv.DictReader(f)}


async def process(agent: Agent, csv_path: Path, emails: dict[str, str], retries: int = 2) -> set[str]:
    """Run, then check the file. Re-ask only for the emails whose rows are missing. Returns what is still missing."""
    session = agent.create_session()
    body = "\n\n".join(f"Subject: {s}\n{text}" for s, text in emails.items())
    await agent.run(body, session=session)
    for _ in range(retries):
        missing = set(emails) - subjects_in(csv_path)
        if not missing:
            break
        await agent.run(f"These emails have no row yet: {sorted(missing)}. Add them now.", session=session)
    return set(emails) - subjects_in(csv_path)


async def main():
    import tempfile

    from support.fake_client import Reply

    path = Path(tempfile.mkdtemp()) / "tracker.csv"
    emails = {"Quote 88": "Please approve the quote by Friday.", "Venue": "Can you confirm the venue?"}

    def row(subject, action, due):
        return Reply.tool_call("add_row", {"sender": "inbox", "subject": subject, "action": action, "due": due})

    script = [row("Quote 88", "approve quote", "Friday"), Reply.text("Added both."),  # claims both, wrote one
              row("Venue", "confirm venue", "none"), Reply.text("Done.")]
    still_missing = await process(build_agent(make_client(script), path), path, emails)
    print("still missing:", still_missing or "nothing", "| rows:", sorted(subjects_in(path)))


if __name__ == "__main__":
    asyncio.run(main())
