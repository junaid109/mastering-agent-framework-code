// Book: chapter-03:271-279 verbatim form with AIProjectClient (compile only)
using Azure.AI.Projects;
using Azure.Identity;
using System.Text.Json.Serialization;
using Microsoft.Agents.AI;

AIProjectClient aiProjectClient = new(new Uri("https://example.invalid"), new DefaultAzureCredential());
string deploymentName = "gpt-5.4-mini";

AIAgent agent = aiProjectClient.AsAIAgent(
    deploymentName, name: "HelpfulAssistant", instructions: "You are a helpful assistant.");

AgentResponse<CityInfo> response = await agent.RunAsync<CityInfo>(
    "Provide information about the capital of France.");

CityInfo cityInfo = response.Result;

public sealed class CityInfo { [JsonPropertyName("name")] public string? Name { get; set; } }
