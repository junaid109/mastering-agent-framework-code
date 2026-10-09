# from 08-part-7-real-systems\chapter-16-shipping-to-production.md:69
server = ResponsesHostServer(
    agent=create_agent,
    history_source="agent_server",
    agent_session_store_provider=CustomSessionStoreProvider(),
)
