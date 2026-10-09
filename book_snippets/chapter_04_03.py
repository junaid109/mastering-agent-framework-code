# from 03-part-2-core-architecture\chapter-04-tools-and-skills.md:57
vector_store = await client.client.vector_stores.create(name="knowledge_base", ...)
await client.client.vector_stores.files.create_and_poll(vector_store_id=vector_store.id, file_id=file.id)

agent = Agent(
    client=client,
    instructions="You are a helpful assistant that can search through files to find information.",
    tools=[client.get_file_search_tool(vector_store_ids=[vector_store.id])],
)
