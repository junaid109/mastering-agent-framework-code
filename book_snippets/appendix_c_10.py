# from 09-back-matter\appendix-c-quick-reference.md:143
results = await evaluate_agent(agent=agent, queries=queries,
    evaluators=FoundryEvals(client=client, evaluators=[FoundryEvals.RELEVANCE, FoundryEvals.TOOL_CALL_ACCURACY]))
for r in results: r.assert_passed()

Agent(client=client, middleware=[PurviewPolicyMiddleware(credential, PurviewSettings(app_name="MyApp"))])
