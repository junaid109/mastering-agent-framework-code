# ch09_10_app results (agent-framework 1.21.0, Python 3.13, offline)

Run: `.venv\Scripts\python.exe -m pytest tests/ch09_10_app` -> 74 passed, 5 skipped.
Extra packages installed in venv for these tests: fastapi, httpx, flask, agent-framework-hosting, agent-framework-hosting-responses (pre-release).
Chapter 9 is .NET only: it has no Python blocks (no `chapter_09_*.py` snippets exist).

## Snippet table

| Snippet | Book location | Status | Evidence / notes |
|---|---|---|---|
| chapter_10_01.py | chapter-10:9 (FastAPI route skeleton) | MISMATCH (minor) + PASS once fixed | As printed raises `NameError: name 'Request' is not defined` (no `Request`/`Response` import). With `from fastapi import FastAPI, Request, Response` it registers `POST /responses`. Body is `...` (placeholder); a complete working route using `responses_to_run` / `AgentState` / `responses_from_run` is in `examples/ch09_10_app/fastapi_responses.py` and exercised with TestClient and httpx ASGITransport (round trip, session continuity via `conversation`, 400 on invalid continuation fields, tenant partitioning). `test_ch10_hosting.py` |
| chapter_10_02.py | chapter-10:57 (typed options) | MISMATCH | `OpenAIChatOptions(temperature=0.7, reasoning_effort="medium")` -> request fails: `AsyncResponses.create() got an unexpected keyword argument 'reasoning_effort'` (verified over a mock HTTP transport). `OpenAIChatOptions` has no `reasoning_effort` key. Also `Message` is not imported and `OpenAIChatClient(...)` needs config (placeholder). Verified fix below. `test_ch10_openai_options.py` |
| chapter_10_03.py | chapter-10:73 (test double) | PASS with caveat | Runs as an `Agent` client (`Summary for 1 messages.`). Caveat/MISMATCH (minor): `isinstance(LocalSummaryClient(), SupportsChatGetResponse)` is False; the runtime protocol also requires an `additional_properties: dict` attribute. Imports (`Message`, `ChatResponse`) missing in snippet. |
| appendix_a_01.py | appendix-a:9 | PASS (AF half) / SKIPPED_PLACEHOLDER (SK half) | AF half executed with ScriptedChatClient: `Agent(client=..., name, instructions)`, `.run(...)`, `.text`. `OpenAIChatClient()` with env `OPENAI_API_KEY` + `OPENAI_MODEL` constructs; with no env it raises `SettingNotFoundError`. SK half not run. |

## Prose claims (non-snippet)

| Claim | Location | Status | Evidence |
|---|---|---|---|
| FastAPI native async route; Flask possible with bridging | ch10 10.1 | PASS | Flask `test_client` + `asyncio.run(agent.run(...))` works |
| previous_response_id/conversation_id are untrusted; partition storage by tenant | ch10 10.1 | PASS | Without partition a second tenant sees the first tenant's history via the same conversation id; with `tenant:id` key it does not |
| `asyncio.gather` fan-out; plain async function pipelines; `functional/` workflows | ch10 10.2 | PASS | 3 x 0.3s agents finish in <0.75s; branching/loop pipeline; `@workflow` decorator (experimental) works |
| Package layout (foundry, anthropic, gemini, orchestrations, azure-ai-search, declarative, monty, hyperlight) | ch10 10.3 | PASS | all import |
| AF Labs | ch10 10.4 | SKIPPED_PLACEHOLDER (pointer only) | not installed, no code |
| DevUI in-memory mode, OpenAI-compatible endpoints | ch10 10.5 | PASS_STRUCTURE_ONLY | `DevServer.register_entities([agent])`, `/health`, `/v1/entities`, `POST /v1/responses` return the scripted reply (TestClient with localhost Host header). Ports 8080/8090 and the `python in_memory_mode.py` sample scripts (Foundry-backed) are not run -> NEEDS_MODEL |
| Pydantic `response_format` gives typed output | ch10 10.6 | PASS | `result.value` is the model instance. Note: on bad JSON, `.value` raises pydantic `ValidationError` (not `None`) |
| Fake clients test instructions, tools, sessions without a network | ch10 10.7 | PASS | tool loop + session history verified |

## MISMATCHES with verified fixes

1. **chapter-10:9 (snippet chapter_10_01)** - undefined `Request`/`Response`. Fix: `from fastapi import FastAPI, Request, Response`. Verified.
2. **chapter-10:57 (chapter_10_02)** - `reasoning_effort="medium"` is rejected by `OpenAIChatClient` (Responses API). Fix, verified on the wire (`{"reasoning": {"effort": "medium"}, "temperature": 0.7}`):
   ```python
   options=OpenAIChatOptions(temperature=0.7, reasoning={"effort": "medium"})
   ```
   Also add `from agent_framework import Message`.
3. **chapter-10:73 (chapter_10_03)** - doc says the plain class satisfies `SupportsChatGetResponse`; `isinstance` is False. Fix: add class attribute `additional_properties: dict = {}` (verified isinstance True). Works with `Agent` either way.
4. **appendix-b B.2 (HandoffBuilder "default `max_turns` limit")** - no such parameter/default exists. A two-agent handoff cycle without a termination condition runs until the workflow runner raises `WorkflowConvergenceException: Runner did not converge after 100 iterations` (observed after ~100 handoff events). The only turn limit is `autonomous_mode_turn_limit` (default 50), which applies to autonomous mode only. Fix: pass `termination_condition=lambda conv: len(conv) >= N` (constructor kwarg or `.with_termination_condition`); verified it stops the cycle at 10 handoffs.
5. **appendix-b B.2 (MagenticBuilder "max_round_count, max_stall_count, max_reset_count")** - `max_round_count` and `max_stall_count + max_reset_count` terminate; `max_stall_count` alone does NOT (a stall triggers a reset and re-plan, loop continues until the 100-superstep guard raises). Fix: always set `max_round_count` or pair stall with `max_reset_count`. Verified.
6. **appendix-b B.3 (`max_invocations` "within one run")** - the counter is on the `FunctionTool` object and persists across runs: a second run on the same tool gets zero real calls. Fix: create a fresh tool per run, or reset `tool.invocation_count = 0`. Verified.
7. **appendix-b B.1 (`TruncationStrategy`)** - book names it without arguments; it requires `max_n` and `compact_to`, which are message counts unless a `tokenizer` is given. `TruncationStrategy(max_n=6, compact_to=4)` verified to bound history. Caveat: `ToolResultCompactionStrategy` collapses old tool-call groups into one `[Tool results: ...]` text message (message count drops) but keeps the payload text, so byte size is not reduced in 1.21.

## Appendix A table (AF side)

| Mapping | Status | Evidence |
|---|---|---|
| ChatCompletionAgent -> Agent | PASS | see appendix_a_01 |
| SK Team -> SequentialBuilder | PASS | runs, last agent's response is output |
| SK Process fan-out/fan-in, nested -> WorkflowBuilder / WorkflowExecutor | PASS | add_fan_out_edges/add_fan_in_edges run; WorkflowExecutor wraps a workflow |
| AssistantAgent -> Agent | PASS | |
| RoundRobinGroupChat -> GroupChatBuilder (selection_func) | PASS | order a,b,a,b |
| SelectorGroupChat -> GroupChatBuilder with a selector | PASS | |
| Swarm -> HandoffBuilder | PASS | triage -> billing handoff event. Requires `require_per_service_call_history_persistence=True` on each agent (not in the book) |
| MagenticOne -> MagenticBuilder | PASS | builds; see Appendix B for run behaviour |
| agent-as-tool (`as_tool`) | PASS | |
| LangChain mappings (@tool schema, add_edge/add_chain, HistoryProvider + compaction) | PASS_STRUCTURE_ONLY | conceptual section; mappings verified to exist |
| All "before" halves (semantic_kernel, autogen, langchain) | SKIPPED_PLACEHOLDER | libraries not installed |

## Appendix B (pitfall reproduced AND fix proven) - `test_appendix_b.py`

| Pitfall | Status | Evidence |
|---|---|---|
| B.1 unbounded history | PASS | request size 1,3,5..15 messages; SlidingWindowStrategy caps at 2; TruncationStrategy, SummarizationStrategy (summary message injected), ToolResultCompactionStrategy (older tool groups collapsed), client-level strategy all verified |
| B.2 infinite loops | PASS with MISMATCHes 4, 5 | see above |
| B.3 tool limits | PASS with MISMATCH 6 | `max_invocations`, `max_invocation_exceptions` cap executions; slow tool bounded by `asyncio.wait_for` (generic, not the book's fix); `background`/`continuation_token` options exist on `OpenAIChatOptions` (PASS_STRUCTURE_ONLY, .NET `AllowBackgroundResponses` itself not tested) |
| B.3 MCP SEP-2663 long-running task | NEEDS_MODEL (needs MCP server) | skipped |
| B.4 context window quality | tight window and "store exact facts in session state" PASS (`session.state` survives `to_dict`/`from_dict`); effective-attention degradation is NEEDS_MODEL |

## Examples (`examples/ch09_10_app/`, all verified to run offline)
`fastapi_responses.py`, `concurrent_agents.py`, `typed_output_and_options.py`, `testing_with_fakes.py`, `bounded_agents.py`.
