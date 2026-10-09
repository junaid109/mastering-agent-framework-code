// Book: chapter-03:210-218. Trailing comma after 2nd strategy removed (as written it is CS1525). Namespace Microsoft.Agents.AI.Compaction ships in Microsoft.Agents.AI 1.24.0 itself.
using Microsoft.Agents.AI.Compaction;
using Microsoft.Extensions.AI;

IChatClient summarizerChatClient = new FakeChatClient((_, _) => new ChatResponse(new ChatMessage(ChatRole.Assistant, "summary")));

PipelineCompactionStrategy compactionPipeline = new(
    // 1. Gentle: collapse old tool-call groups into short summaries
    new ToolResultCompactionStrategy(CompactionTriggers.MessagesExceed(7)),
    // 2. Moderate: LLM-summarize older conversation spans
    new SummarizationCompactionStrategy(summarizerChatClient, CompactionTriggers.TokensExceed(0x500))
    // ...continuing to SlidingWindowCompactionStrategy and TruncationCompactionStrategy
);
Console.WriteLine("constructed: " + compactionPipeline.GetType().FullName);
