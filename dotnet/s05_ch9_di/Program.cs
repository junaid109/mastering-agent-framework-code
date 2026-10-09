// Book: chapter-09:15-37; elided "// ..." replaced by StopAsync + RunAsync stubs (as written: CS0535 then CS1929)
using Azure.AI.Projects;
using Azure.Identity;
using Microsoft.Agents.AI;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;

string endpoint = "https://example.invalid";
string deploymentName = "gpt-5.4-mini";
args = Array.Empty<string>();

HostApplicationBuilder builder = Host.CreateApplicationBuilder(args);

AIProjectClient aiProjectClient = new(new Uri(endpoint), new DefaultAzureCredential());
AIAgent agent = aiProjectClient.AsAIAgent(model: deploymentName, name: "Joker", instructions: "You are good at telling jokes.");
builder.Services.AddSingleton(agent);
builder.Services.AddHostedService<SampleService>();

using IHost host = builder.Build();
await host.RunAsync().ConfigureAwait(false);

internal sealed class SampleService(AIAgent agent, IHostApplicationLifetime appLifetime) : IHostedService
{
    private AgentSession? _session;

    public async Task StartAsync(CancellationToken cancellationToken)
    {
        this._session = await agent.CreateSessionAsync(cancellationToken);
        _ = this.RunAsync(appLifetime.ApplicationStopping);
    }
    public Task StopAsync(CancellationToken cancellationToken) => Task.CompletedTask;
    public Task RunAsync(CancellationToken cancellationToken) => Task.CompletedTask; // elided body in book
}
