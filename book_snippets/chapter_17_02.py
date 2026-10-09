# from 08-part-7-real-systems\chapter-17-production-readiness.md:31
session = agent.create_session()
result = await agent.run("Add a dentist appointment on March 15th", session=session)

for request in result.user_input_requests:
    approval = request.to_function_approval_response(approved=True)   # or False
    result = await agent.run(Message("user", [approval]), session=session)
