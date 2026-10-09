"""Afternoon agent 1: meeting notes in, action list out, written to disk only if a human approves."""
import asyncio
from pathlib import Path

from agent_framework import Agent, tool

from afternoon.common import make_client, run_approved


def build_agent(client, outdir: Path) -> Agent:
    @tool(approval_mode="always_require")  # the only side effect is gated
    def save_actions(markdown: str) -> str:
        """Save the action list as actions.md."""
        (outdir / "actions.md").write_text(markdown, encoding="utf-8")
        return "saved actions.md"

    return Agent(
        client=client,
        name="ActionItems",
        instructions=(
            "Read the meeting notes. Extract every commitment as '- [owner] task (due date)'. "
            "Never invent owners or dates; write 'unassigned' or 'no date'. Then call save_actions once."
        ),
        tools=save_actions,
    )


async def main():
    from support.fake_client import Reply

    notes = "Sam will send the pricing deck by Friday. Priya to book the venue. We should review the budget."
    actions = "- [Sam] send pricing deck (Friday)\n- [Priya] book venue (no date)\n- [unassigned] review budget (no date)"
    client = make_client([Reply.tool_call("save_actions", {"markdown": actions}), Reply.text("Saved 3 actions.")])
    outdir = Path(".")
    result = await run_approved(build_agent(client, outdir), notes, approve=lambda req: True)
    print(result.text)


if __name__ == "__main__":
    asyncio.run(main())
