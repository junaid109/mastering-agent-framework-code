# from 09-back-matter\appendix-c-quick-reference.md:18
result = await agent.run(query)                         # single response
async for chunk in agent.run(query, stream=True): ...    # streaming
