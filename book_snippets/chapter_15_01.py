# from 08-part-7-real-systems\chapter-15-building-a-knowledge-assistant.md:19
from dataclasses import dataclass
from typing import Annotated
from agent_framework import VectorStoreField, vectorstoremodel

@vectorstoremodel
@dataclass
class Hotel:
    key: Annotated[str, VectorStoreField("key", storage_name="hotel_id")]
    description: Annotated[str, VectorStoreField("data", is_full_text_indexed=True)]
    category: Annotated[str, VectorStoreField("data", is_indexed=True)]
    vector: Annotated[list[float] | None, VectorStoreField("vector", dimensions=3)] = None
