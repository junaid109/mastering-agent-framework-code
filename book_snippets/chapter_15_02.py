# from 08-part-7-real-systems\chapter-15-building-a-knowledge-assistant.md:39
from agent_framework import Filter, FilterGroup

search_filter = FilterGroup("and", (
    Filter("city", "eq", "Lisbon"),
    Filter("rating", "between", (4.5, 5.0)),
    Filter("amenities", "contains", "pool"),
))
results = await collection.search(vector=[1.0, 0.0], filter=search_filter, top=5)
async for result in results:
    print(result["record"], result["score"])
