# .NET verification results

Toolchain: .NET SDK 10.0.302, net10.0. Packages (nuget.org stable): Microsoft.Agents.AI 1.24.0, Microsoft.Agents.AI.Foundry 1.5.0
(brings Azure.AI.Projects 2.x), Microsoft.Agents.AI.Workflows 1.24.0, Azure.Identity 1.x. No API keys, no model calls.
Offline runs use `shared/FakeChatClient.cs` (scripted `IChatClient`, incl. `FunctionCallContent` and `ResponseContinuationToken`).
Common build note: `MAAI001`/`MEAI001` (experimental API) diagnostics are suppressed in `Directory.Build.props`; without it the
background-response snippet fails with MEAI001 (the book does not mention this).

## Book snippets (8 csharp blocks in chapters; build/ copies are duplicates)

| Project | Book location | Status | Evidence |
|---|---|---|---|
| s01_preface | 01-front-matter/preface.md:72 (and 09-back-matter/appendix-c-quick-reference.md:13, same call) | MISMATCH (fixed) / PASS_RUNS_OFFLINE for fix | `client.AsAIAgent(model: ..., instructions:, name:)` on an `IChatClient` -> CS1739 "no parameter named 'model'". `model:` only exists on `AIProjectClient.AsAIAgent` (Foundry). Fixed form `chatClient.AsAIAgent(instructions: "...", name: "MyAgent")` ran: `OK: hello / MyAgent` |
| s02_ch2_haiku | chapter-02-introduction-to-agent-framework.md:93 | PASS_COMPILES (NEEDS_MODEL to run) | verbatim, Build succeeded, 0 errors |
| s03_ch3_compaction | chapter-03-anatomy-of-an-agent.md:210 | MISMATCH (fixed) / PASS_RUNS_OFFLINE for fix | verbatim = CS1525 (trailing comma before the `// ...` comment and `)`). Without the comma it builds and constructs `PipelineCompactionStrategy` |
| s04_ch3_structured | chapter-03...md:271 | PASS_RUNS_OFFLINE | `RunAsync<CityInfo>` on IChatClient-backed agent; JSON response format requested, result "Paris". Book omits `CityInfo` definition (add a class with `[JsonPropertyName("name")] string? Name`) |
| s04b_ch3_structured_foundry | chapter-03...md:271 (AIProjectClient form) | PASS_COMPILES (NEEDS_MODEL) | Build succeeded |
| s05_ch9_di | chapter-09-production-dotnet-agents.md:15 | MISMATCH (fixed) | verbatim = CS0535 (no `StopAsync`) then CS1929 (no `RunAsync(CancellationToken)`); the `// ...` elision hides both members. With stubs: Build succeeded |
| s05b_ch9_di_offline | chapter-09:15 | PASS_RUNS_OFFLINE | host starts, singleton fake-backed agent, session created, one turn: `OK DI: knock knock session=True` |
| s06_ch9_background | chapter-09:53 | PASS_RUNS_OFFLINE | verbatim body; fake returns continuation token twice then final text; 3 model calls, loop terminates, text asserted. Needs MEAI001 suppression |
| samples/cosmos_mem | chapter-15-building-a-knowledge-assistant.md:174 | PASS_COMPILES (NEEDS_MODEL) | snippet is a fragment (needs `databaseResponse`, `aiProjectClient`, `userId`, `embeddingDimensions`, and sits inside `ChatClientAgentOptions`); the full cited sample compiles, using `CosmosVectorStore`, `ChatHistoryMemoryProvider(... State(storageScope, searchScope))` exactly as the snippet |
| s08_toolcall_offline (bonus) | n/a (ch.4 tool concept) | PASS_RUNS_OFFLINE | scripted FunctionCallContent -> tool executed once -> final text `Tool said: Sunny in Paris`. (`AIFunctionFactory.Create` on a local function needs an explicit name) |

## Official samples (cited in the book), built from `reference/.../dotnet-samples`
Upstream csproj files use `ProjectReference` into `src/`, which is NOT in the snapshot, so each sample's source was copied to
`dotnet/samples/<name>` with the csproj rewritten to NuGet PackageReferences (versions above). Sample source unchanged.
`dotnet build` result: all PASS_COMPILES, 0 warnings.

| Sample | Upstream path | Status |
|---|---|---|
| hello_agent | 01-get-started/01_hello_agent | PASS_COMPILES |
| add_tools | 01-get-started/02_add_tools | PASS_COMPILES |
| multi_turn | 01-get-started/03_multi_turn | PASS_COMPILES |
| memory | 01-get-started/04_memory | PASS_COMPILES |
| first_workflow | 01-get-started/05_first_workflow | PASS_COMPILES |
| fn_approvals | 02-agents/Agents/Agent_Step01_UsingFunctionToolsWithApprovals | PASS_COMPILES |
| structured | .../Agent_Step02_StructuredOutput | PASS_COMPILES |
| persisted | .../Agent_Step03_PersistedConversations | PASS_COMPILES |
| di | .../Agent_Step06_DependencyInjection | PASS_COMPILES |
| middleware | .../Agent_Step11_Middleware | PASS_COMPILES |
| background | .../Agent_Step14_BackgroundResponses | PASS_COMPILES |
| compaction | .../Agent_Step18_CompactionPipeline | PASS_COMPILES |
| cosmos_mem | 02-agents/AgentWithMemory/AgentWithMemory_Step08_MemoryUsingCosmosNoSql | PASS_COMPILES |
| loop_wf | 03-workflows/Loop | PASS_COMPILES |

## MISMATCH list with fixes
1. preface.md:72 and appendix-c-quick-reference.md:13: `client.AsAIAgent(model: ..., ...)` is only valid when `client` is an `AIProjectClient` (needs Microsoft.Agents.AI.Foundry). For an `IChatClient` drop `model:` (model is set on the client). Say which client type `client` is.
2. chapter-03-anatomy-of-an-agent.md:215: remove trailing comma after `CompactionTriggers.TokensExceed(0x500))` (or replace the comment with a real strategy), otherwise CS1525.
3. chapter-09-production-dotnet-agents.md:35: `// ...` hides required members; add `public Task StopAsync(CancellationToken ct) => Task.CompletedTask;` and a `RunAsync(CancellationToken)` method, else CS0535/CS1929.
4. chapter-03 snippet at :271: define `CityInfo` (not shown).
5. chapter-09.md:43 (section 9.3) names `Microsoft.Agents.AI.Compaction` as a NuGet package; no such package exists on nuget.org (exact search returns none). The `Microsoft.Agents.AI.Compaction` namespace ships inside `Microsoft.Agents.AI` (verified: compiled with only that package).
6. chapter-09.md:53 snippet: add note that `ContinuationToken`/`AllowBackgroundResponses` raise MEAI001 (experimental) and need `<NoWarn>MEAI001</NoWarn>`.

## Not verified
All snippets needing a live model (Foundry/Azure OpenAI, Cosmos DB) are compile-only (NEEDS_MODEL). Foundry package stable is 1.5.0 (preview 1.24.0-preview exists); book text citing "1.24.0" applies to Microsoft.Agents.AI core only.
