# from 08-part-7-real-systems\chapter-16-shipping-to-production.md:24
from agent_framework import Agent, InMemoryHistoryProvider
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer

agent = Agent(
    client=FoundryChatClient(
        project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
        credential=DefaultAzureCredential(),
    ),
    instructions="Be concise.",
    context_providers=[InMemoryHistoryProvider()],
    default_options={"store": False},
)
ResponsesHostServer(agent=agent, history_source="agent").run()
