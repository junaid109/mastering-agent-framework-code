# from 08-part-7-real-systems\chapter-17-production-readiness.md:21
# WARNING: this sample resumes approvals without a session, so it turns off approval
# response binding. ... Turning that off means any approval response present in the
# inbound messages is honored as-is, so whatever can put messages into the conversation
# can approve a privileged tool call -- including one the model never requested.
client.function_invocation_configuration["disable_approval_response_binding"] = True
