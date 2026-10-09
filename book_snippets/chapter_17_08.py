# from 08-part-7-real-systems\chapter-17-production-readiness.md:156
from agent_framework import evaluate_agent
from agent_framework.foundry import FoundryEvals

results = await evaluate_agent(
    agent=agent,
    queries=["What's the weather like in Seattle?",
             "How much does a flight from Seattle to Paris cost?"],
    evaluators=FoundryEvals(client=chat_client,
                            evaluators=[FoundryEvals.RELEVANCE, FoundryEvals.TOOL_CALL_ACCURACY]),
)
for r in results:
    print(f"{r.passed}/{r.total} passed", r.report_url)
