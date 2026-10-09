# from 08-part-7-real-systems\chapter-15-building-a-knowledge-assistant.md:93
from agent_framework import Agent, InMemoryCollection, VectorCollectionContextProvider

collection_context = VectorCollectionContextProvider(
    collection,
    scope_filter=None,                       # only safe: process-local, single-purpose collection
    approval_mode={"upsert": "never_require"},
)

async with Agent(
    client=client,
    name="ProjectNotesAssistant",
    instructions="Use the collection tools to manage project notes. Do not invent stored notes.",
    context_providers=[collection_context],
) as agent:
    session = agent.create_session()
    await agent.run("Save a note with id release-checklist, title Release checklist, "
                    "and body Verify rollback, monitoring, and owner sign-off.", session=session)
    await agent.run("Search the project notes for release readiness checks.", session=session)
