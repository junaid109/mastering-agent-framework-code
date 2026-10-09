// Bonus: exercises the tool-calling loop the book describes (ch.4) with a scripted FunctionCallContent.
using System.ComponentModel;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;

int toolRuns = 0;
[Description("Get weather")] string GetWeather([Description("city")] string city) { toolRuns++; return $"Sunny in {city}"; }

var fake = new FakeChatClient(
    (_, _) => new ChatResponse(new ChatMessage(ChatRole.Assistant, [new FunctionCallContent("c1", "GetWeather", new Dictionary<string, object?> { ["city"] = "Paris" })])),
    (msgs, _) =>
    {
        var res = msgs.SelectMany(m => m.Contents).OfType<FunctionResultContent>().Single();
        return new ChatResponse(new ChatMessage(ChatRole.Assistant, "Tool said: " + res.Result));
    });
AIAgent agent = fake.AsAIAgent(instructions: "weather bot", tools: [AIFunctionFactory.Create(GetWeather, "GetWeather")]);
var r = await agent.RunAsync("Weather in Paris?");
if (toolRuns != 1 || r.Text != "Tool said: Sunny in Paris") throw new Exception("assert failed: " + r.Text);
Console.WriteLine("OK tool call: " + r.Text);
