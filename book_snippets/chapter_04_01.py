# from 03-part-2-core-architecture\chapter-04-tools-and-skills.md:9
from typing import Annotated
from pydantic import Field
from agent_framework import tool

@tool(approval_mode="never_require")
def get_weather(
    location: Annotated[str, Field(description="The location to get the weather for.")],
) -> str:
    """Get the weather for a given location."""
    ...
