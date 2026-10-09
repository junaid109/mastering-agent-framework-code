// Afternoon agent (C#): do not believe "I saved it". Check what actually ran, and make the model retry.
using System.ComponentModel;
using System.Text.RegularExpressions;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;

var succeeded = new List<string>();
var folder = Directory.CreateTempSubdirectory().FullName;
var claim = new Regex(@"\b(saved|wrote|written|created|stored)\b", RegexOptions.IgnoreCase);

async ValueTask<object?> Recorder(AIAgent agent, FunctionInvocationContext context,
    Func<FunctionInvocationContext, CancellationToken, ValueTask<object?>> next, CancellationToken ct)
{
    var result = await next(context, ct); // an exception here means the tool did not succeed
    succeeded.Add(context.Function.Name);
    return result;
}

[Description("Write a text file")]
string WriteFile([Description("file name")] string name, [Description("content")] string content)
{
    File.WriteAllText(Path.Combine(folder, name), content);
    return $"wrote {name}";
}

var fake = new FakeChatClient(
    (_, _) => new ChatResponse(new ChatMessage(ChatRole.Assistant, "Done, I saved notes.txt.")), // a false claim: nothing ran
    (_, _) => new ChatResponse(new ChatMessage(ChatRole.Assistant, [new FunctionCallContent("c1", "WriteFile",
        new Dictionary<string, object?> { ["name"] = "notes.txt", ["content"] = "hello" })])),
    (_, _) => new ChatResponse(new ChatMessage(ChatRole.Assistant, "Saved notes.txt.")));

var agent = fake.AsAIAgent(instructions: "Do what is asked using WriteFile.", tools: [AIFunctionFactory.Create(WriteFile, "WriteFile")])
    .AsBuilder().Use(Recorder).Build();

var session = await agent.CreateSessionAsync();
var result = await agent.RunAsync("Save a note saying hello.", session);
var caught = 0;
while (claim.IsMatch(result.Text) && !succeeded.Contains("WriteFile") && caught < 2)
{
    caught++;
    result = await agent.RunAsync("You said it was saved, but WriteFile has not run. Call it now, or say plainly that you could not.", session);
}
Console.WriteLine($"false claims caught: {caught}; file exists: {File.Exists(Path.Combine(folder, "notes.txt"))}; reply: {result.Text}");
if (caught != 1 || File.ReadAllText(Path.Combine(folder, "notes.txt")) != "hello") throw new Exception("assert failed");
Console.WriteLine("OK claim check");
