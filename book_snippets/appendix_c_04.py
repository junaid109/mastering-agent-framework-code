# from 09-back-matter\appendix-c-quick-reference.md:32
result = await agent.run(query, options={"response_format": MyPydanticModel})
data = result.value  # typed instance, or None if parsing failed
