# from 03-part-2-core-architecture\chapter-03-anatomy-of-an-agent.md:28
from agent_framework.openai import OpenAIChatClient
from azure.identity import AzureCliCredential

agent = Agent(
    client=OpenAIChatClient(
        model=os.getenv("AZURE_OPENAI_MODEL"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        credential=AzureCliCredential(),
    ),
    name="WeatherAgent",
    instructions="You are a helpful weather agent.",
    tools=get_weather,
)
