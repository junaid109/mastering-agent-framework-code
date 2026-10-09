# from 03-part-2-core-architecture\chapter-05-middleware.md:107
agent = Agent(
    client=FoundryChatClient(credential=credential),
    instructions="You triage inbound support email.",
    context_providers=[secure_config],  # injects security tools, instructions, and middleware automatically
)
