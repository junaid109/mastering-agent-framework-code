// Book: chapter-09:53-67 verbatim body, offline. Fake IChatClient returns a ContinuationToken twice, then a final answer,
// exercising the poll loop.
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;

int calls = 0;
var tok = ResponseContinuationToken.FromBytes(new byte[] { 1, 2, 3 });
var fake = new FakeChatClient((msgs, o) =>
{
    calls++;
    if (calls < 3) return new ChatResponse(new ChatMessage(ChatRole.Assistant, "")) { ContinuationToken = tok };
    return new ChatResponse(new ChatMessage(ChatRole.Assistant, "The otters reached Mars."));
});
AIAgent agent = fake.AsAIAgent(instructions: "You are a helpful assistant.");

// ---- verbatim book snippet ----
AgentRunOptions options = new() { AllowBackgroundResponses = true };
AgentSession session = await agent.CreateSessionAsync();

AgentResponse response = await agent.RunAsync("Write a very long novel about otters in space.", session, options);

while (response.ContinuationToken is { } token)
{
    await Task.Delay(TimeSpan.FromSeconds(2));
    options.ContinuationToken = token;
    response = await agent.RunAsync(session, options);
}

Console.WriteLine(response.Text);
// -------------------------------
if (calls != 3 || response.Text != "The otters reached Mars.") throw new Exception($"assert failed calls={calls}");
Console.WriteLine($"OK background: polled, {calls} model calls");
