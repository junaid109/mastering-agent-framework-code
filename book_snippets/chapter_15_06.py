# from 08-part-7-real-systems\chapter-15-building-a-knowledge-assistant.md:149
from agent_framework import Agent, InMemoryStore, SlidingWindowStrategy, VectorStoreHistoryProvider

history = VectorStoreHistoryProvider(
    InMemoryStore(),
    application_id="release-planning",
    tenant_id="contoso",
    agent_id="release-assistant",
    collection_name="release_planning_history_text_embedding_3_small",
    contents_format="json",
    embedding_generator=OpenAIEmbeddingClient(model="text-embedding-3-small"),
    compaction_strategy=SlidingWindowStrategy(keep_last_groups=2, preserve_system=True),
    include_search_tool=True,
)
agent = Agent(client=client, name="ReleaseAssistant", context_providers=[history],
              instructions="Help with release planning. Use the history search tool when an "
                           "older detail is not present in the loaded conversation.")
