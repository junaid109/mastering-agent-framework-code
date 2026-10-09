# from 08-part-7-real-systems\chapter-17-production-readiness.md:137
from agent_framework import Agent
from agent_framework.microsoft import PurviewPolicyMiddleware, PurviewSettings

agent = Agent(
    client=client,
    name="Joker",
    middleware=[PurviewPolicyMiddleware(credential, PurviewSettings(app_name="Sample App"))],
)
