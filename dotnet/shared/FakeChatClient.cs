using Microsoft.Extensions.AI;

/// <summary>Scripted offline IChatClient. Each call pops the next scripted response.</summary>
public sealed class FakeChatClient(params Func<IEnumerable<ChatMessage>, ChatOptions?, ChatResponse>[] script) : IChatClient
{
    private int _i;
    public List<List<ChatMessage>> Calls { get; } = new();
    public Task<ChatResponse> GetResponseAsync(IEnumerable<ChatMessage> messages, ChatOptions? options = null, CancellationToken cancellationToken = default)
    {
        var list = messages.ToList();
        Calls.Add(list);
        var step = script[Math.Min(_i++, script.Length - 1)];
        return Task.FromResult(step(list, options));
    }
    public async IAsyncEnumerable<ChatResponseUpdate> GetStreamingResponseAsync(IEnumerable<ChatMessage> messages, ChatOptions? options = null, [System.Runtime.CompilerServices.EnumeratorCancellation] CancellationToken cancellationToken = default)
    {
        var r = await GetResponseAsync(messages, options, cancellationToken);
        foreach (var u in r.ToChatResponseUpdates()) yield return u;
    }
    public object? GetService(Type serviceType, object? serviceKey = null) => serviceType.IsInstanceOfType(this) ? this : null;
    public void Dispose() { }
}
