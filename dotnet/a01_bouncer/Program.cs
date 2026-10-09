// Afternoon agent (C#): a bouncer in front of every tool call. Deny by default, explain every refusal.
using System.ComponentModel;
using System.Text.RegularExpressions;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;

var allow = new HashSet<string> { "ReadNote", "RunShell" };
var askHuman = new HashSet<string> { "RunShell" };
var denyArgs = new[] { new Regex(@"rm\s+-rf"), new Regex(@"\.\./"), new Regex("api[_-]?key|password|secret", RegexOptions.IgnoreCase) };
var log = new List<(string Tool, string Decision)>();
Func<string, string, bool> approve = (_, _) => false; // a real app would ask a person here

string? Verdict(string name, string args)
{
    if (!allow.Contains(name)) return $"The tool {name} is not on this agent's allow-list. Allowed: {string.Join(", ", allow.Order())}.";
    foreach (var rule in denyArgs)
        if (rule.IsMatch(args)) return $"Arguments matched the blocked pattern {rule}.";
    if (askHuman.Contains(name) && !approve(name, args)) return "A human reviewer declined this call.";
    return null;
}

async ValueTask<object?> Bouncer(AIAgent agent, FunctionInvocationContext context,
    Func<FunctionInvocationContext, CancellationToken, ValueTask<object?>> next, CancellationToken ct)
{
    var args = string.Join(" ", context.Arguments.Select(a => a.Value?.ToString()));
    var reason = Verdict(context.Function.Name, args);
    log.Add((context.Function.Name, reason is null ? "allowed" : "blocked"));
    if (reason is not null) return $"BLOCKED: {reason}"; // the model reads this as the tool's result; the tool never runs
    return await next(context, ct);
}

[Description("Read a note")] string ReadNote([Description("note name")] string name) => $"(contents of {name})";
[Description("Run a shell command")] string RunShell([Description("command")] string command) => $"ran: {command}";

FunctionCallContent Call(string id, string tool, string key, string value) => new(id, tool, new Dictionary<string, object?> { [key] = value });
ChatResponse Reply(params AIContent[] contents) => new(new ChatMessage(ChatRole.Assistant, contents));

var fake = new FakeChatClient(
    (_, _) => Reply(Call("c1", "ReadNote", "name", "../secrets.txt")),
    (_, _) => Reply(Call("c2", "RunShell", "command", "ls")),
    (_, _) => Reply(Call("c3", "ReadNote", "name", "ok.txt")),
    (_, _) => Reply(new TextContent("done")));

var agent = fake.AsAIAgent(instructions: "Use tools to do the task.",
        tools: [AIFunctionFactory.Create(ReadNote, "ReadNote"), AIFunctionFactory.Create(RunShell, "RunShell")])
    .AsBuilder().Use(Bouncer).Build();

await agent.RunAsync("Tidy up.");
Console.WriteLine(string.Join(", ", log.Select(l => $"{l.Tool}={l.Decision}")));

string Result(int call) => fake.Calls[call].SelectMany(m => m.Contents).OfType<FunctionResultContent>().Last().Result?.ToString() ?? "";
if (!Result(1).Contains("blocked pattern") || !Result(2).Contains("human reviewer declined") || Result(3) != "(contents of ok.txt)")
    throw new Exception("assert failed");
Console.WriteLine("OK bouncer: blocked path, declined shell, allowed note; reasons reached the model");
