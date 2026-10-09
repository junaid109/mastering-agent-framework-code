# from 08-part-7-real-systems\chapter-15-building-a-knowledge-assistant.md:120
from agent_framework import Filter
from agent_framework.azure import AzureAISearchStore
from azure.identity.aio import AzureCliCredential

async with (
    AzureCliCredential() as credential,
    AzureAISearchStore(endpoint=os.environ["AZURE_SEARCH_ENDPOINT"], credential=credential) as store,
):
    collection = store.get_collection(Hotel, collection_name=f"af-vector-sample-{uuid4().hex}")
    await store.index_client.create_index(collection.build_index())

    # Vector search with a portable filter, evaluated natively by Azure AI Search
    async for result in await collection.search(
        vector=[1.0, 0.0, 0.0], filter=Filter("category", "eq", "quiet")):
        print(result["record"].description, result["score"])

    # Keyword + vector in one query, fused with Azure's native reciprocal rank fusion
    async for result in await collection.search(
        "hotel", vector=[1.0, 0.0, 0.0], search_type="keyword_hybrid"):
        print(result["record"].description, result["score"])
