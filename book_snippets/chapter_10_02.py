# from 05-part-4-language-specific\chapter-10-python-ecosystem.md:57
from agent_framework.openai import OpenAIChatClient, OpenAIChatOptions

client = OpenAIChatClient(...)
response = await client.get_response(
    [Message("user", contents=["What is the capital of France?"])],
    options=OpenAIChatOptions(temperature=0.7, reasoning_effort="medium"),  # provider-specific fields, IDE-checked
)
