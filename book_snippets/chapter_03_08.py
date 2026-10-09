# from 03-part-2-core-architecture\chapter-03-anatomy-of-an-agent.md:228
from pydantic import BaseModel
from agent_framework import Agent

class OutputStruct(BaseModel):
    city: str
    description: str

agent = Agent(
    client=OpenAIChatClient(),
    name="CityAgent",
    instructions="You are a helpful agent that describes cities in a structured format.",
)

result = await agent.run(
    "Tell me about Paris, France",
    options={"response_format": OutputStruct},
)

if structured_data := result.value:
    print(structured_data.city, structured_data.description)
