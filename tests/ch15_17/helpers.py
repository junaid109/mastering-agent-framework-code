"""Shared helpers for the ch15_17 group: deterministic hash embeddings and a hotel model."""
from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Annotated, Any

from agent_framework import (
    BaseEmbeddingClient,
    Embedding,
    GeneratedEmbeddings,
    VectorStoreField,
    vectorstoremodel,
)

DIM = 8


def hash_vector(text: str, dim: int = DIM) -> list[float]:
    """Deterministic bag-of-words hash vector (normalised)."""
    v = [0.0] * dim
    for tok in text.lower().split():
        h = int(hashlib.sha256(tok.encode()).hexdigest(), 16)
        v[h % dim] += 1.0
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


class HashEmbeddingClient(BaseEmbeddingClient[str, list[float], Any]):
    """Offline embedding client: same text -> same vector."""

    OTEL_PROVIDER_NAME = "hash"

    def __init__(self, dim: int = DIM) -> None:
        super().__init__()
        self.dim = dim
        self.calls: list[list[str]] = []

    async def get_embeddings(self, values: Sequence[str], *, options: Any = None):
        self.calls.append(list(values))
        return GeneratedEmbeddings([Embedding(vector=hash_vector(v, self.dim)) for v in values])


@vectorstoremodel
@dataclass
class Hotel:
    hotel_id: Annotated[str, VectorStoreField("key")]
    hotel_name: Annotated[str, VectorStoreField("data", is_indexed=True)]
    category: Annotated[str, VectorStoreField("data", is_indexed=True)]
    rating: Annotated[float, VectorStoreField("data", is_indexed=True)]
    city: Annotated[str, VectorStoreField("data", is_indexed=True)]
    amenities: Annotated[list[str], VectorStoreField("data", is_indexed=True)]
    description: Annotated[str, VectorStoreField("data", is_full_text_indexed=True)]
    cost_internal: Annotated[float, VectorStoreField("data")] = 0.0
    vector: Annotated[list[float] | str | None, VectorStoreField("vector", dimensions=DIM)] = None

    def __post_init__(self):
        if self.vector is None:
            self.vector = self.description


HOTELS = [
    Hotel("h1", "Alfama Palace", "Luxury", 4.8, "Lisbon", ["pool", "spa"], "luxury riverside palace with pool", 120.0),
    Hotel("h2", "Baixa Budget", "Budget", 3.9, "Lisbon", ["wifi"], "cheap clean rooms downtown", 30.0),
    Hotel("h3", "Porto Boutique", "Boutique", 4.6, "Porto", ["pool", "bar"], "boutique design hotel near the river", 80.0),
    Hotel("h4", "Lisbon Suites", "Suite", 4.5, "Lisbon", ["pool", "kitchen"], "spacious suites with kitchen and pool", 90.0),
]


async def hotel_collection(records=HOTELS, name="hotels"):
    from agent_framework import InMemoryStore

    emb = HashEmbeddingClient()
    store = InMemoryStore(embedding_generator=emb)
    col = store.get_collection(Hotel, collection_name=name)
    await col.ensure_collection_exists()
    import copy
    await col.upsert([copy.deepcopy(r) for r in records])
    return store, col, emb


from support.fake_client import Reply, ScriptedChatClient  # noqa: E402


class RecordingClient(ScriptedChatClient):
    """ScriptedChatClient that also records the options (tools etc.) of every model call."""

    def __init__(self, script, **kw):
        super().__init__(script, **kw)
        self.options_seen: list[dict] = []

    def _inner_get_response(self, *, messages, stream, options, **kwargs):
        self.options_seen.append(dict(options or {}))
        return super()._inner_get_response(messages=messages, stream=stream, options=options, **kwargs)

    def tool_names(self, call: int = 0) -> list[str]:
        return [getattr(t, "name", None) or t.get("function", {}).get("name") for t in (self.options_seen[call].get("tools") or [])]

    def tool_schema(self, name: str, call: int = 0) -> dict:
        for t in self.options_seen[call].get("tools") or []:
            if getattr(t, "name", None) == name:
                return t.parameters()
        raise KeyError(name)
