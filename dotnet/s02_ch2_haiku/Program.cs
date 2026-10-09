// Book: chapter-02-introduction-to-agent-framework.md:93-106 (verbatim)
using Azure.AI.Projects;
using Azure.Identity;
using Microsoft.Agents.AI;

string endpoint = Environment.GetEnvironmentVariable("AZURE_AI_PROJECT_ENDPOINT")!;
string deploymentName = Environment.GetEnvironmentVariable("AZURE_AI_MODEL_DEPLOYMENT_NAME") ?? "gpt-5.4-mini";

AIAgent agent =
    new AIProjectClient(new Uri(endpoint), new DefaultAzureCredential())
    .AsAIAgent(model: deploymentName, instructions: "You are an upbeat assistant that writes beautifully.", name: "HaikuAgent");

Console.WriteLine(await agent.RunAsync("Write a haiku about Microsoft Agent Framework."));
