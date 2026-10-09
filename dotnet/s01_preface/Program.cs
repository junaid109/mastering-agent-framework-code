// Book: 01-front-matter/preface.md:72  (and appendix-c-quick-reference.md:13 uses the same call)
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;

IChatClient client = new FakeChatClient((_, _) => new ChatResponse(new ChatMessage(ChatRole.Assistant, "hello")));

// ---- book snippet with `model:` removed (IChatClient overload has no model parameter; FIX) ----
AIAgent agent = client.AsAIAgent(instructions: "...", name: "MyAgent");
// -------------------------------

var r = await agent.RunAsync("hi");
if (r.Text != "hello" || agent.Name != "MyAgent") throw new Exception("assert failed");
Console.WriteLine("OK: " + r.Text + " / " + agent.Name);
