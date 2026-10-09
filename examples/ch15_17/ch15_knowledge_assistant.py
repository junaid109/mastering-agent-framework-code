"""Chapter 15 - a retrieval-augmented agent on the provider-neutral vector store layer.

Runs offline: ScriptedChatClient plays the model, a hash-based embedding client plays the embedding model.
Set BOOK_CLIENT=openai-compatible (+ BOOK_BASE_URL, BOOK_MODEL) to use a real chat model; the embeddings stay
local and deterministic, so retrieval is the same either way.
"""
import asyncio
import hashlib
import math
import os
import sys
from dataclasses import dataclass
from typing import Annotated, Literal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from agent_framework import (  # noqa: E402
    Agent, BaseEmbeddingClient, Embedding, Filter, FilterGroup, GeneratedEmbeddings, InMemoryStore, Param,
    VectorCollectionContextProvider, VectorStoreField, create_vector_search_tool, vectorstoremodel,
)


def make_client(script=None):
    if os.environ.get("BOOK_CLIENT") == "openai-compatible":
        from agent_framework.openai import OpenAIChatCompletionClient

        return OpenAIChatCompletionClient(base_url=os.environ["BOOK_BASE_URL"],
                                          api_key=os.environ.get("BOOK_API_KEY", "not-needed"),
                                          model=os.environ["BOOK_MODEL"])
    from support.fake_client import ScriptedChatClient

    return ScriptedChatClient(script or [])


DIM = 8


class HashEmbeddings(BaseEmbeddingClient[str, list[float], dict]):
    """Deterministic bag-of-words hash embeddings: same text, same vector, no network."""

    async def get_embeddings(self, values, *, options=None):
        def vec(text):
            v = [0.0] * DIM
            for tok in text.lower().split():
                v[int(hashlib.sha256(tok.encode()).hexdigest(), 16) % DIM] += 1.0
            n = math.sqrt(sum(x * x for x in v)) or 1.0
            return [x / n for x in v]

        return GeneratedEmbeddings([Embedding(vector=vec(v)) for v in values])


@vectorstoremodel
@dataclass
class Hotel:
    hotel_id: Annotated[str, VectorStoreField("key")]
    hotel_name: Annotated[str, VectorStoreField("data", is_indexed=True)]
    category: Annotated[str, VectorStoreField("data", is_indexed=True)]
    rating: Annotated[float, VectorStoreField("data", is_indexed=True)]
    internal_cost: Annotated[float, VectorStoreField("data")]          # must never reach the prompt
    description: Annotated[str, VectorStoreField("data", is_full_text_indexed=True)]
    vector: Annotated[list[float] | str | None, VectorStoreField("vector", dimensions=DIM)] = None

    def __post_init__(self):                     # a string in the vector field is embedded at upsert time
        if self.vector is None:
            self.vector = self.description


HOTELS = [
    Hotel("h1", "Alfama Palace", "Luxury", 4.8, 120.0, "luxury riverside palace with pool"),
    Hotel("h2", "Baixa Budget", "Budget", 3.9, 30.0, "cheap clean rooms downtown"),
    Hotel("h3", "Porto Boutique", "Boutique", 4.6, 80.0, "boutique design hotel near the river"),
]


async def main():
    store = InMemoryStore(embedding_generator=HashEmbeddings())
    hotels = store.get_collection(Hotel, collection_name="hotels")
    await hotels.ensure_collection_exists()
    await hotels.upsert(HOTELS)

    # 15.3 portable filter objects (data, never parsed as code)
    flt = FilterGroup("and", (Filter("category", "in", ("Luxury", "Boutique")), Filter("rating", "between", (4.5, 5.0))))
    print("filter hits:", [r["record"].hotel_name async for r in await hotels.search("river pool", filter=flt)])

    # 15.4 search as a tool: the model may vary only `category` and `min_rating`
    category = Param("category", Literal["Boutique", "Budget", "Luxury"], description="Only this category.")
    min_rating = Param("min_rating", float, description="Minimum rating.", minimum=0, maximum=5)
    tool = create_vector_search_tool(
        hotels, description="Search hotels, optionally by category and minimum rating.",
        filter=FilterGroup("and", (Filter("category", "eq", category), Filter("rating", "gte", min_rating))),
        result_mapper=lambda r: f"(hotel_id: {r['record'].hotel_id}) {r['record'].hotel_name} "
                                f"(rating {r['record'].rating}) - {r['record'].description}")
    print("tool schema properties:", sorted(tool.parameters()["properties"]))

    client = make_client(_script_search())
    agent = Agent(client=client, name="HotelAgent", tools=[tool],
                  instructions="Always use the search tool to answer hotel questions. Include the hotel_id.")
    print("agent:", (await agent.run("A luxury hotel with a pool?")).text)

    # 15.5 let the agent manage a collection; delete/upsert default to human approval
    notes = VectorCollectionContextProvider(hotels, scope_filter=None, approval_mode={"upsert": "never_require"})
    print("provider created with tools: upsert/get/delete/search; delete still needs approval:", notes is not None)


def _script_search():
    from support.fake_client import Reply

    return [Reply.tool_call("search", {"query": "river pool", "category": "Luxury", "min_rating": 4.0}),
            Reply.text("Alfama Palace (hotel_id h1), rated 4.8, is a luxury riverside palace with a pool.")]


if __name__ == "__main__":
    asyncio.run(main())
