# from 08-part-7-real-systems\chapter-15-building-a-knowledge-assistant.md:58
from typing import Literal
from agent_framework import (Agent, Filter, FilterGroup, Param,
                             create_vector_search_tool)

category = Param(
    "category",
    Literal["Boutique", "Budget", "Extended-Stay", "Luxury", "Resort and Spa", "Suite"],
    description="Only return hotels in this category.",
)
min_rating = Param("min_rating", float,
                   description="The minimum guest rating.", minimum=0, maximum=5)

tool = create_vector_search_tool(
    collection,
    description="Search the hotel dataset, optionally filtering by category and minimum rating.",
    filter=FilterGroup("and", (
        Filter("category", "eq", category),
        Filter("rating", "gte", min_rating),
    )),
    result_mapper=lambda r: f"(hotel_id: {r['record'].hotel_id}) {r['record'].hotel_name} "
                            f"(rating {r['record'].rating}) - {r['record'].description}",
)

agent = Agent(client=client, name="HotelAgent", tools=[tool],
              instructions="Always use the search tool to answer hotel questions. "
                           "Include the hotel_id in the answer.")
