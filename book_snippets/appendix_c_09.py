# from 09-back-matter\appendix-c-quick-reference.md:113
@vectorstoremodel
@dataclass
class Doc:
    key: Annotated[str, VectorStoreField("key")]
    text: Annotated[str, VectorStoreField("data", is_full_text_indexed=True)]
    vector: Annotated[list[float] | str | None, VectorStoreField("vector", dimensions=1536)] = None

flt = FilterGroup("and", (Filter("site", "eq", "A14"), Filter("severity", "gte", 3)))
