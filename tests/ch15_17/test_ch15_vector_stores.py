"""Chapter 15: executes the vector-store layer for real (InMemoryStore + hash embeddings)."""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Annotated, Literal

import pytest
from agent_framework import (
    Agent,
    Filter,
    FilterGroup,
    InMemoryStore,
    Message,
    Param,
    SlidingWindowStrategy,
    VectorCollectionContextProvider,
    VectorStoreField,
    VectorStoreHistoryProvider,
    create_vector_search_tool,
    vectorstoremodel,
)

from support.fake_client import Reply, flatten
from tests.ch15_17.helpers import DIM, HOTELS, HashEmbeddingClient, Hotel, RecordingClient, hash_vector, hotel_collection

pytestmark = pytest.mark.filterwarnings("ignore")


def _results(client, request_index):
    return [t[2] for t in flatten(client.requests[request_index]) if t[1] == "function_result"]


# ---------------------------------------------------------------- 15.2 model (chapter_15_01)
@vectorstoremodel
@dataclass
class BookHotel:
    """chapter_15_01 verbatim."""

    key: Annotated[str, VectorStoreField("key", storage_name="hotel_id")]
    description: Annotated[str, VectorStoreField("data", is_full_text_indexed=True)]
    category: Annotated[str, VectorStoreField("data", is_indexed=True)]
    vector: Annotated[list[float] | None, VectorStoreField("vector", dimensions=3)] = None


def test_15_01_book_model_declares_fields_as_described():
    d = BookHotel.__vectorstoremodel_definition__
    assert d.key_field_storage_name == "hotel_id"
    by = {f.name: f for f in d.fields}
    assert by["description"].is_full_text_indexed is True
    assert by["category"].is_indexed is True
    assert by["vector"].dimensions == 3
    assert [f.field_type for f in d.fields] == ["key", "data", "data", "vector"]


async def test_15_01_precomputed_vectors_with_generate_vectors_false_and_filter():
    col = InMemoryStore().get_collection(BookHotel, collection_name="bh")
    await col.ensure_collection_exists()
    await col.upsert(
        [BookHotel("a", "quiet place", "quiet", [1.0, 0.0, 0.0]), BookHotel("b", "loud place", "loud", [0.0, 1.0, 0.0])],
        generate_vectors=False,
    )
    res = [r async for r in await col.search(vector=[1.0, 0.0, 0.0], filter=Filter("category", "eq", "quiet"))]
    assert [r["record"].key for r in res] == ["a"]
    assert res[0]["record"].description == "quiet place"
    assert "score" in res[0]


async def test_15_01_string_in_vector_field_is_embedded_at_upsert():
    store, col, emb = await hotel_collection()
    assert emb.calls and "luxury riverside palace with pool" in emb.calls[0]
    got = (await col.get(["h1"], include_vectors=True))[0]
    assert got.vector == pytest.approx(hash_vector("luxury riverside palace with pool"))


async def test_15_01_dimension_mismatch_rejected_before_write():
    store = InMemoryStore(embedding_generator=HashEmbeddingClient(dim=5))  # model wants DIM=8
    col = store.get_collection(Hotel, collection_name="bad")
    await col.ensure_collection_exists()
    with pytest.raises(Exception) as ei:
        await col.upsert([copy.deepcopy(HOTELS[0])])
    assert "dimension" in str(ei.value).lower()
    assert not await col.get(["h1"])


async def test_15_01_wrong_length_precomputed_vector_rejected():
    col = InMemoryStore().get_collection(Hotel, collection_name="pre")
    await col.ensure_collection_exists()
    h = copy.deepcopy(HOTELS[0])
    h.vector = [1.0, 0.0]
    with pytest.raises(Exception):
        await col.upsert([h], generate_vectors=False)


# ---------------------------------------------------------------- 15.3 filters (chapter_15_02)
async def _names(col, flt, top=10):
    res = await col.search(vector=hash_vector("pool"), filter=flt, top=top)
    return sorted([r["record"].hotel_name async for r in res])


async def test_15_02_book_filter_group_and_semantics():
    store, col, _ = await hotel_collection()
    book_filter = FilterGroup("and", (
        Filter("city", "eq", "Lisbon"),
        Filter("rating", "between", (4.5, 5.0)),
        Filter("amenities", "contains", "pool"),
    ))
    assert await _names(col, book_filter) == ["Alfama Palace", "Lisbon Suites"]  # 4.5 inclusive


async def test_15_02_results_carry_record_and_score():
    store, col, _ = await hotel_collection()
    res = [r async for r in await col.search(vector=hash_vector("pool"), top=2)]
    assert len(res) == 2
    for r in res:
        assert isinstance(r["record"], Hotel) and isinstance(r["score"], float)
    # in-memory default metric is cosine *distance*: lower is closer, sorted ascending
    assert res[0]["score"] <= res[1]["score"]


@pytest.mark.parametrize(
    "flt, expected",
    [
        (Filter("city", "eq", "Porto"), ["Porto Boutique"]),
        (Filter("city", "ne", "Lisbon"), ["Porto Boutique"]),
        (Filter("rating", "gt", 4.6), ["Alfama Palace"]),
        (Filter("rating", "gte", 4.6), ["Alfama Palace", "Porto Boutique"]),
        (Filter("rating", "lt", 4.0), ["Baixa Budget"]),
        (Filter("rating", "lte", 3.9), ["Baixa Budget"]),
        (Filter("category", "in", ("Luxury", "Budget")), ["Alfama Palace", "Baixa Budget"]),
        (Filter("category", "not_in", ("Luxury", "Budget")), ["Lisbon Suites", "Porto Boutique"]),
        (Filter("amenities", "contains", "spa"), ["Alfama Palace"]),
        (FilterGroup("or", (Filter("city", "eq", "Porto"), Filter("category", "eq", "Budget"))),
         ["Baixa Budget", "Porto Boutique"]),
        (FilterGroup("not", (Filter("city", "eq", "Lisbon"),)), ["Porto Boutique"]),
    ],
)
async def test_15_02_filter_operators(flt, expected):
    store, col, _ = await hotel_collection()
    assert await _names(col, flt) == expected


async def test_15_02_filters_are_data_not_code():
    store, col, _ = await hotel_collection()
    assert await _names(col, Filter("city", "eq", "Lisbon' or True or '")) == []
    assert await _names(col, Filter("city", "eq", "__import__('os').system('echo pwned')")) == []
    with pytest.raises(Exception):
        await _names(col, Filter("nonexistent", "eq", 1))
    with pytest.raises(Exception):
        await _names(col, Filter("city", "eval", "x"))


# ---------------------------------------------------------------- 15.4 search tool (chapter_15_03)
CATEGORIES = Literal["Boutique", "Budget", "Extended-Stay", "Luxury", "Resort and Spa", "Suite"]


def _book_tool(col):
    category = Param("category", CATEGORIES, description="Only return hotels in this category.")
    min_rating = Param("min_rating", float, description="The minimum guest rating.", minimum=0, maximum=5)
    return create_vector_search_tool(
        col,
        description="Search the hotel dataset, optionally filtering by category and minimum rating.",
        filter=FilterGroup("and", (Filter("category", "eq", category), Filter("rating", "gte", min_rating))),
        result_mapper=lambda r: f"(hotel_id: {r['record'].hotel_id}) {r['record'].hotel_name} "
        f"(rating {r['record'].rating}) - {r['record'].description}",
    )


async def test_15_03_tool_schema_exposes_only_query_category_min_rating():
    store, col, _ = await hotel_collection()
    schema = _book_tool(col).parameters()
    assert set(schema["properties"]) == {"query", "category", "min_rating"}
    assert schema["additionalProperties"] is False
    assert schema["properties"]["category"]["enum"] == [
        "Boutique", "Budget", "Extended-Stay", "Luxury", "Resort and Spa", "Suite"]
    mr = schema["properties"]["min_rating"]
    assert mr["type"] == "number" and mr["minimum"] == 0 and mr["maximum"] == 5
    assert schema["required"] == ["query"]


async def test_15_03_model_cannot_exceed_the_controls_it_was_given():
    store, col, _ = await hotel_collection()
    tool = _book_tool(col)
    with pytest.raises(Exception):
        await tool.func(query="pool", min_rating=11)
    with pytest.raises(Exception):
        await tool.func(query="pool", category="Castle")
    with pytest.raises(TypeError):
        await tool.func(query="pool", city="Lisbon")
    ok = await tool.func(query="pool", category="Luxury", min_rating=4.0)
    assert [c.text for c in ok] == ["(hotel_id: h1) Alfama Palace (rating 4.8) - luxury riverside palace with pool"]


async def test_15_03_result_mapper_hides_internal_columns_end_to_end():
    store, col, _ = await hotel_collection()
    client = RecordingClient([
        Reply.tool_call("search", {"query": "pool", "category": "Luxury", "min_rating": 4}),
        Reply.text("Alfama Palace (h1)."),
    ])
    agent = Agent(client=client, name="HotelAgent", tools=[_book_tool(col)],
                  instructions="Always use the search tool to answer hotel questions. Include the hotel_id in the answer.")
    result = await agent.run("Any luxury hotel with a pool?")
    assert "h1" in result.text
    tool_result = _results(client, 1)[0]
    assert "hotel_id: h1" in tool_result
    assert "120" not in tool_result and "cost" not in tool_result
    assert client.tool_names(0) == ["search"]


async def test_15_03_omitting_optional_params_still_searches():
    store, col, _ = await hotel_collection()
    out = await _book_tool(col).func(query="pool")
    assert len(out) >= 1


# ---------------------------------------------------------------- 15.5 context provider (chapter_15_04)
@vectorstoremodel
@dataclass
class Note:
    id: Annotated[str, VectorStoreField("key")]
    title: Annotated[str, VectorStoreField("data", is_indexed=True)]
    body: Annotated[str, VectorStoreField("data")]
    project: Annotated[str, VectorStoreField("data", is_indexed=True)] = "p1"
    vector: Annotated[list[float] | str | None, VectorStoreField("vector", dimensions=DIM)] = None


async def _notes():
    store = InMemoryStore(embedding_generator=HashEmbeddingClient())
    col = store.get_collection(Note, collection_name="notes")
    await col.ensure_collection_exists()
    return col


async def test_15_04_default_tools_and_approval_modes():
    col = await _notes()
    client = RecordingClient([Reply.text("ok")])
    provider = VectorCollectionContextProvider(col, scope_filter=None)
    async with Agent(client=client, name="n", instructions="x", context_providers=[provider]) as agent:
        await agent.run("hi")
    assert client.tool_names() == ["upsert", "get", "delete", "search"]
    modes = {t.name: t.approval_mode for t in client.options_seen[0]["tools"]}
    assert modes == {"upsert": "always_require", "get": "never_require",
                     "delete": "always_require", "search": "never_require"}


async def test_15_04_book_snippet_approval_override_and_scripted_conversation():
    col = await _notes()
    collection_context = VectorCollectionContextProvider(
        col, scope_filter=None, approval_mode={"upsert": "never_require"})
    note = {"id": "release-checklist", "title": "Release checklist",
            "body": "Verify rollback, monitoring, and owner sign-off.", "project": "p1",
            "vector": "Release checklist Verify rollback monitoring owner sign-off"}
    client = RecordingClient([
        Reply.tool_call("upsert", {"records": [note]}), Reply.text("Saved."),
        Reply.tool_call("search", {"query": "release readiness checks"}), Reply.text("Found the checklist."),
    ])
    async with Agent(
        client=client, name="ProjectNotesAssistant",
        instructions="Use the collection tools to manage project notes. Do not invent stored notes.",
        context_providers=[collection_context],
    ) as agent:
        session = agent.create_session()
        r1 = await agent.run("Save a note ...", session=session)
        assert not r1.user_input_requests  # upsert ran unattended
        r2 = await agent.run("Search the project notes for release readiness checks.", session=session)
    assert r2.text == "Found the checklist."
    stored = await col.get(["release-checklist"])
    assert stored[0].title == "Release checklist"
    assert "release-checklist" in _results(client, -1)[-1]
    modes = {t.name: t.approval_mode for t in client.options_seen[0]["tools"]}
    assert modes["upsert"] == "never_require" and modes["delete"] == "always_require"


async def test_15_04_upsert_default_requires_approval_unattended_run_pauses():
    col = await _notes()
    provider = VectorCollectionContextProvider(col, scope_filter=None)
    client = RecordingClient([Reply.tool_call("upsert", {"records": [
        {"id": "x", "title": "t", "body": "b", "vector": "t b"}]}), Reply.text("saved")])
    async with Agent(client=client, name="n", instructions="x", context_providers=[provider]) as agent:
        r = await agent.run("save x")
    assert len(r.user_input_requests) == 1
    assert not await col.get(["x"])


async def test_15_04_delete_requires_human_approval_then_runs():
    col = await _notes()
    await col.upsert([Note("n1", "t", "b", vector="t b")])
    provider = VectorCollectionContextProvider(col, scope_filter=None, approval_mode={"upsert": "never_require"})
    client = RecordingClient([Reply.tool_call("delete", {"keys": ["n1"]}), Reply.text("deleted")])
    async with Agent(client=client, name="n", instructions="x", context_providers=[provider]) as agent:
        session = agent.create_session()
        r = await agent.run("delete n1", session=session)
        assert len(r.user_input_requests) == 1
        assert r.user_input_requests[0].function_call.name == "delete"
        assert await col.get(["n1"])
        resp = r.user_input_requests[0].to_function_approval_response(approved=True)
        await agent.run(Message("user", [resp]), session=session)
    assert not await col.get(["n1"])


async def test_15_04_include_flags_strip_tools_and_additional_search_tools():
    col = await _notes()
    extra = create_vector_search_tool(col, name="details")
    provider = VectorCollectionContextProvider(
        col, scope_filter=None, include_upsert_tool=False, include_delete_tool=False,
        include_get_tool=False, additional_search_tools=[extra])
    client = RecordingClient([Reply.text("ok")])
    async with Agent(client=client, name="n", instructions="x", context_providers=[provider]) as agent:
        await agent.run("hi")
    assert sorted(client.tool_names()) == ["details", "search"]


async def test_15_04_scope_filter_is_required_and_restricts_operations():
    col = await _notes()
    with pytest.raises(TypeError):
        VectorCollectionContextProvider(col)  # type: ignore[call-arg]
    await col.upsert([Note("a1", "alpha", "x", project="p1", vector="alpha x"),
                      Note("b1", "beta", "x", project="p2", vector="alpha x")])
    provider = VectorCollectionContextProvider(col, scope_filter=Filter("project", "eq", "p1"))
    client = RecordingClient([Reply.tool_call("search", {"query": "alpha x"}), Reply.text("ok"),
                              Reply.tool_call("get", {"keys": ["b1"]}), Reply.text("ok")])
    async with Agent(client=client, name="n", instructions="x", context_providers=[provider]) as agent:
        await agent.run("find")
        res = _results(client, 1)[0]
        assert "a1" in res and "b1" not in res
        await agent.run("get b1", session=agent.create_session())
        assert "beta" not in _results(client, 3)[0]


# ---------------------------------------------------------------- 15.6 Azure AI Search (chapter_15_05): structure only
def test_15_05_structure_only_imports_and_api_surface():
    import inspect

    from agent_framework.azure import AzureAISearchStore
    assert hasattr(AzureAISearchStore, "get_collection")
    params = inspect.signature(AzureAISearchStore.__init__).parameters
    assert "endpoint" in params and "credential" in params
    assert "index_client" in inspect.getsource(AzureAISearchStore)
    from agent_framework import _vectors
    assert "keyword_hybrid" in inspect.getsource(_vectors)


async def test_15_05_in_memory_rejects_keyword_hybrid():
    store, col, _ = await hotel_collection()
    with pytest.raises(NotImplementedError):
        await col.search("hotel", vector=hash_vector("hotel"), search_type="keyword_hybrid")


# ---------------------------------------------------------------- 15.7 history provider (chapter_15_06)
def _history(store, emb, tenant="contoso", **kw):
    args = dict(
        application_id="release-planning", tenant_id=tenant, agent_id="release-assistant",
        collection_name="release_planning_history", contents_format="json",
        embedding_generator=emb, embedding_options={"dimensions": DIM},
        compaction_strategy=SlidingWindowStrategy(keep_last_groups=2, preserve_system=True),
        include_search_tool=True)
    args.update(kw)
    return VectorStoreHistoryProvider(store, **args)


def test_15_06_book_constructor_as_written_fails_without_embedding_options():
    """MISMATCH evidence: the book snippet omits embedding_options={'dimensions': N}."""
    with pytest.raises(ValueError, match="embedding_options with dimensions"):
        VectorStoreHistoryProvider(
            InMemoryStore(), application_id="release-planning", tenant_id="contoso",
            agent_id="release-assistant", collection_name="release_planning_history_text_embedding_3_small",
            contents_format="json", embedding_generator=HashEmbeddingClient(),
            compaction_strategy=SlidingWindowStrategy(keep_last_groups=2, preserve_system=True),
            include_search_tool=True)


def test_15_06_fixed_constructor_with_real_openai_embedding_client_class():
    from agent_framework.openai import OpenAIEmbeddingClient
    c = OpenAIEmbeddingClient(model="text-embedding-3-small", api_key="sk-test")
    h = VectorStoreHistoryProvider(
        InMemoryStore(), application_id="release-planning", tenant_id="contoso", agent_id="release-assistant",
        collection_name="release_planning_history_text_embedding_3_small", contents_format="json",
        embedding_generator=c, embedding_options={"dimensions": 1536},
        compaction_strategy=SlidingWindowStrategy(keep_last_groups=2, preserve_system=True),
        include_search_tool=True)
    assert h.application_id == "release-planning" and h.include_search_tool


async def test_15_06_full_transcript_stored_window_loaded_search_tool_recalls_old_detail():
    emb, store = HashEmbeddingClient(), InMemoryStore()
    history = _history(store, emb)
    script = [Reply.text(f"ack{i}") for i in range(4)] + [
        Reply.tool_call("search_history", {"query": "region westeurope"}), Reply.text("You chose westeurope.")]
    client = RecordingClient(script)
    agent = Agent(client=client, name="ReleaseAssistant", context_providers=[history],
                  instructions="Help with release planning.")
    session = agent.create_session()
    for t in ["remember region is westeurope", "remember team is blue", "remember budget 5", "remember owner bob"]:
        await agent.run(t, session=session)
    last_prompt = " ".join(x[2] for x in flatten(client.requests[3]))
    assert "westeurope" not in last_prompt and "owner bob" in last_prompt  # only a compacted window is loaded
    assert "search_history" in client.tool_names(3)
    r = await agent.run("Which deployment region did I choose?", session=session)
    assert r.text == "You chose westeurope."
    assert "westeurope" in _results(client, -1)[0]  # answered from stored full history
    assert await store.list_collection_names() == ["release_planning_history"]


async def test_15_06_scoping_by_session_and_tenant():
    emb, store = HashEmbeddingClient(), InMemoryStore()
    client = RecordingClient([Reply.text("a"), Reply.text("b"), Reply.text("c")])
    a1 = Agent(client=client, name="A", context_providers=[_history(store, emb, "contoso")], instructions="x")
    s = a1.create_session()
    await a1.run("secret contoso fact", session=s)
    await a1.run("hello", session=a1.create_session())
    assert "secret" not in " ".join(x[2] for x in flatten(client.requests[1]))
    a2 = Agent(client=client, name="A", context_providers=[_history(store, emb, "fabrikam")], instructions="x")
    await a2.run("hello again", session=s)  # same session id, different tenant
    assert "secret" not in " ".join(x[2] for x in flatten(client.requests[2]))
    c3 = RecordingClient([Reply.text("z")])
    a3 = Agent(client=c3, name="A", context_providers=[_history(store, emb, "contoso")], instructions="x")
    await a3.run("again", session=s)  # same tenant + same session id
    assert "secret contoso fact" in " ".join(x[2] for x in flatten(c3.requests[0]))


def test_15_06_constructor_validation():
    store = InMemoryStore()
    with pytest.raises(ValueError):
        VectorStoreHistoryProvider(store, application_id="")
    with pytest.raises(ValueError):
        VectorStoreHistoryProvider(store, application_id="a", include_search_tool=True)
    with pytest.raises(ValueError):
        VectorStoreHistoryProvider(store, application_id="a", contents_format="xml")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        VectorStoreHistoryProvider(store)  # type: ignore[call-arg]
