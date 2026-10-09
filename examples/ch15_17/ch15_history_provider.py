"""Chapter 15.7 - VectorStoreHistoryProvider: full transcript stored, compacted window loaded, search tool on demand.

Corrects the book snippet: embedding_generator requires embedding_options={"dimensions": N} (ValueError otherwise).
"""
import asyncio
import hashlib
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from agent_framework import (  # noqa: E402
    Agent, BaseEmbeddingClient, Embedding, GeneratedEmbeddings, InMemoryStore, SlidingWindowStrategy,
    VectorStoreHistoryProvider,
)

DIM = 8


def make_client(script=None):
    if os.environ.get("BOOK_CLIENT") == "openai-compatible":
        from agent_framework.openai import OpenAIChatCompletionClient

        return OpenAIChatCompletionClient(base_url=os.environ["BOOK_BASE_URL"],
                                          api_key=os.environ.get("BOOK_API_KEY", "not-needed"),
                                          model=os.environ["BOOK_MODEL"])
    from support.fake_client import ScriptedChatClient

    return ScriptedChatClient(script or [])


class HashEmbeddings(BaseEmbeddingClient[str, list[float], dict]):
    async def get_embeddings(self, values, *, options=None):
        def vec(t):
            v = [0.0] * DIM
            for tok in t.lower().split():
                v[int(hashlib.sha256(tok.encode()).hexdigest(), 16) % DIM] += 1.0
            n = math.sqrt(sum(x * x for x in v)) or 1.0
            return [x / n for x in v]

        return GeneratedEmbeddings([Embedding(vector=vec(v)) for v in values])


async def main():
    from support.fake_client import Reply, flatten

    history = VectorStoreHistoryProvider(
        InMemoryStore(),
        application_id="release-planning", tenant_id="contoso", agent_id="release-assistant",
        collection_name="release_planning_history", contents_format="json",
        embedding_generator=HashEmbeddings(),
        embedding_options={"dimensions": DIM},            # <- missing from the book snippet
        compaction_strategy=SlidingWindowStrategy(keep_last_groups=2, preserve_system=True),
        include_search_tool=True,
    )
    script = [Reply.text(f"Noted ({i}).") for i in range(4)] + [
        Reply.tool_call("search_history", {"query": "deployment region"}),
        Reply.text("You chose westeurope.")]
    client = make_client(script)
    agent = Agent(client=client, name="ReleaseAssistant", context_providers=[history],
                  instructions="Help with release planning. Use the history search tool for older details.")
    session = agent.create_session()
    for fact in ["Remember the deployment region is westeurope.", "Remember the team is blue.",
                 "Remember the budget is 5k.", "Remember the owner is Bob."]:
        await agent.run(fact, session=session)
    if hasattr(client, "requests"):
        print("last window sent to the model:", [t for r, k, t in flatten(client.requests[3]) if k == "text"])
    print("answer:", (await agent.run("Which deployment region did I choose?", session=session)).text)


if __name__ == "__main__":
    asyncio.run(main())
