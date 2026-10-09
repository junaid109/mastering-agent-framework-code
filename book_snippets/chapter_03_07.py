# from 03-part-2-core-architecture\chapter-03-anatomy-of-an-agent.md:181
shared_client = OpenAIChatClient(
    compaction_strategy=TruncationStrategy(max_n=3, compact_to=2),
    tokenizer=FixedTokenizer(7),
)

# Uses the client's defaults
default_agent = Agent(client=shared_client, name="ClientDefaultAgent")

# Overrides the client's defaults for this agent specifically
override_agent = Agent(
    client=shared_client,
    name="AgentOverrideAgent",
    compaction_strategy=SlidingWindowStrategy(keep_last_groups=3),
    tokenizer=FixedTokenizer(11),
)

# Overrides both, for this single run only
await override_agent.run(
    messages,
    compaction_strategy=TruncationStrategy(max_n=2, compact_to=1),
    tokenizer=FixedTokenizer(23),
)
