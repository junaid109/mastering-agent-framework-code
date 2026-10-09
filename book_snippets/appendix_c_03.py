# from 09-back-matter\appendix-c-quick-reference.md:24
session = agent.create_session()
result = await agent.run(query, session=session)
serialized = session.to_dict()
resumed = AgentSession.from_dict(serialized)
