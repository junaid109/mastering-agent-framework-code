// Book: chapter-09:15-37 pattern, offline: IChatClient-backed agent registered as singleton, hosted service creates a session.
// The elided "// ..." (RunAsync) is supplied minimally: SampleService.RunAsync runs one turn.
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;

HostApplicationBuilder builder = Host.CreateApplicationBuilder(args);
AIAgent agent = new FakeChatClient((_, _) => new ChatResponse(new ChatMessage(ChatRole.Assistant, "knock knock")))
    .AsAIAgent(name: "Joker", instructions: "You are good at telling jokes.");
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
    private async Task RunAsync(CancellationToken ct)
    {
        var r = await agent.RunAsync("joke", this._session, cancellationToken: ct);
        Console.WriteLine("OK DI: " + r.Text + " session=" + (this._session is not null));
        appLifetime.StopApplication();
    }
}
