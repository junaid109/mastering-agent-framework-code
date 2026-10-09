# from 08-part-7-real-systems\chapter-17-production-readiness.md:111
config = SecureAgentConfig(
    auto_hide_untrusted=True,
    approval_on_violation=True,
    enable_policy_enforcement=True,
    allow_untrusted_tools={"fetch_emails"},
    quarantine_chat_client=quarantine_client,
)
agent = Agent(client=main_client, tools=[fetch_emails, send_email], context_providers=[config])
