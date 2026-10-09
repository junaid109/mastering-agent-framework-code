// Book: chapter-03-anatomy-of-an-agent.md:271-279. CityInfo is not defined in the book snippet; added below.
// The book's `aiProjectClient.AsAIAgent(deploymentName, name:, instructions:)` needs Foundry (see s04b). Here the
// same RunAsync<T> call is exercised offline on an IChatClient-backed agent.
using System.Text.Json.Serialization;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;

var client = new FakeChatClient((_, o) =>
{
    if (o?.ResponseFormat is not ChatResponseFormatJson) throw new Exception("no JSON response format requested");
    return new ChatResponse(new ChatMessage(ChatRole.Assistant, "{\"name\":\"Paris\"}"));
});
AIAgent agent = client.AsAIAgent(name: "HelpfulAssistant", instructions: "You are a helpful assistant.");

AgentResponse<CityInfo> response = await agent.RunAsync<CityInfo>(
    "Provide information about the capital of France.");

CityInfo cityInfo = response.Result;
if (cityInfo.Name != "Paris") throw new Exception("assert failed");
Console.WriteLine("OK structured: " + cityInfo.Name);

public sealed class CityInfo { [JsonPropertyName("name")] public string? Name { get; set; } }
