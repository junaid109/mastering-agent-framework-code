"""Chapter 17.4 - identity-scoped data flow with PRINCIPAL_METADATA_KEY and SecureAgentConfig.

Alice's profile may flow to a destination whose principals include Alice, and is blocked (and audited) for Bob's.
Principals come from the authenticated request, never from model arguments.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from agent_framework import Agent, tool  # noqa: E402
from agent_framework.security import PRINCIPAL_METADATA_KEY, SecureAgentConfig  # noqa: E402


def make_client(script=None):
    if os.environ.get("BOOK_CLIENT") == "openai-compatible":
        from agent_framework.openai import OpenAIChatCompletionClient

        return OpenAIChatCompletionClient(base_url=os.environ["BOOK_BASE_URL"],
                                          api_key=os.environ.get("BOOK_API_KEY", "not-needed"),
                                          model=os.environ["BOOK_MODEL"])
    from support.fake_client import ScriptedChatClient

    return ScriptedChatClient(script or [])


# derived from the authenticated request BEFORE the tools are built
authenticated_principals = [{"tenant_id": "contoso", "user_id": "alice"}]
other_principals = [{"tenant_id": "contoso", "user_id": "bob"}]
sent: list[tuple[str, str]] = []


@tool(description="Read the authenticated user's profile.",
      additional_properties={"source_integrity": "trusted", "confidentiality": "user_identity",
                             PRINCIPAL_METADATA_KEY: authenticated_principals})
async def read_my_profile() -> str:
    return "Alice Smith <alice@contoso.example>"


@tool(description="Save a note to the authenticated user's own account.",
      additional_properties={"max_allowed_confidentiality": "user_identity",
                             PRINCIPAL_METADATA_KEY: authenticated_principals})
async def save_to_my_account(note: str) -> str:
    sent.append(("alice", note))
    return "saved"


@tool(description="Send a note to another user's account.",
      additional_properties={"max_allowed_confidentiality": "user_identity",
                             PRINCIPAL_METADATA_KEY: other_principals})
async def send_to_other_account(note: str) -> str:
    sent.append(("bob", note))
    return "sent"


async def attempt(destination: str):
    from support.fake_client import Reply

    sent.clear()
    security = SecureAgentConfig(auto_hide_untrusted=True, block_on_violation=True)
    client = make_client([Reply.tool_call("read_my_profile", {}),
                          Reply.tool_call(destination, {"note": "Alice Smith <alice@contoso.example>"}),
                          Reply.text("Done.")])
    agent = Agent(client=client, name="assistant", tools=[read_my_profile, save_to_my_account, send_to_other_account],
                  context_providers=[security])
    session = agent.create_session()
    await agent.run("Copy my profile to the destination.", session=session)
    audit = [(e["type"], e.get("subtype"), e["function"]) for e in security.get_audit_log(session)]
    print(f"{destination:22} delivered={sent}  audit={audit}")


async def main():
    await attempt("save_to_my_account")
    await attempt("send_to_other_account")


if __name__ == "__main__":
    asyncio.run(main())
