// Afternoon agent (C#): a tamper-evident log of every tool call; each entry hashes the one before it.
using System.ComponentModel;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;

const string Genesis = "0000000000000000000000000000000000000000000000000000000000000000";
var path = Path.Combine(Path.GetTempPath(), $"audit-{Guid.NewGuid():N}.jsonl");
var last = Genesis;

string Digest(string prev, string record) => Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(prev + record))).ToLowerInvariant();

async ValueTask<object?> AuditLog(AIAgent agent, FunctionInvocationContext context,
    Func<FunctionInvocationContext, CancellationToken, ValueTask<object?>> next, CancellationToken ct)
{
    var result = await next(context, ct);
    var record = JsonSerializer.Serialize(new { tool = context.Function.Name, args = context.Arguments.ToDictionary(a => a.Key, a => a.Value?.ToString()), result = result?.ToString() });
    last = Digest(last, record);
    File.AppendAllText(path, JsonSerializer.Serialize(new { record, hash = last }) + "\n");
    return result;
}

(bool Ok, int? BadIndex) Verify()
{
    var prev = Genesis;
    var lines = File.ReadAllLines(path);
    for (var i = 0; i < lines.Length; i++)
    {
        using var doc = JsonDocument.Parse(lines[i]);
        prev = Digest(prev, doc.RootElement.GetProperty("record").GetString()!);
        if (prev != doc.RootElement.GetProperty("hash").GetString()) return (false, i);
    }
    return (true, null);
}

[Description("Look up a price")] string LookupPrice([Description("item")] string item) => item == "widget" ? "4.50" : "9.00";

FunctionCallContent Call(string id, string item) => new(id, "LookupPrice", new Dictionary<string, object?> { ["item"] = item });
var fake = new FakeChatClient(
    (_, _) => new ChatResponse(new ChatMessage(ChatRole.Assistant, [Call("c1", "widget")])),
    (_, _) => new ChatResponse(new ChatMessage(ChatRole.Assistant, [Call("c2", "gadget")])),
    (_, _) => new ChatResponse(new ChatMessage(ChatRole.Assistant, "A widget is 4.50 and a gadget is 9.00.")));

var agent = fake.AsAIAgent(instructions: "Quote prices.", tools: [AIFunctionFactory.Create(LookupPrice, "LookupPrice")])
    .AsBuilder().Use(AuditLog).Build();
await agent.RunAsync("Price a widget and a gadget.");

var intact = Verify();
File.WriteAllText(path, File.ReadAllText(path).Replace("4.50", "0.50")); // someone edits history
var tampered = Verify();
Console.WriteLine($"intact: {intact}; after tampering: {tampered}");
if (!intact.Ok || tampered.Ok || tampered.BadIndex != 0) throw new Exception("assert failed");
Console.WriteLine("OK audit log: chain verified, then tampering detected at entry 0");
