# ch02_04 results (agent-framework 1.21.0, offline)

Run: `.venv\Scripts\python.exe -m pytest tests/ch02_04 -q` -> 52 passed. Examples: `python examples/ch02_04/NN_*.py` (all 6 run offline).
Helper: `tests/ch02_04/helpers.py` (`RecordingClient` = ScriptedChatClient + records per-request `options`; `support/fake_client.py` untouched).

Book paths relative to `C:\repos\mastering-agent-framework-book\`.

| snippet | book location | status | evidence / notes |
|---|---|---|---|
| chapter_02_01 | 02-part-1-foundations/chapter-02-...md:70 | PASS_STRUCTURE_ONLY | Hello agent run with scripted client, `print(await agent.run())` prints text; instructions sent as system instructions. `FoundryChatClient(credential=AzureCliCredential())` with no env raises `ValueError: Model is required ... FOUNDRY_MODEL`; constructs fine with `project_endpoint`+`model`. Real call = NEEDS_MODEL. |
| chapter_02_02 | same:112 | PASS | `async for chunk in agent.run(..., stream=True)` yields chunks with `.text`. (Fragment relies on `agent` from previous snippet.) |
| chapter_03_01 | 03-part-2-core-architecture/chapter-03-...md:11 | PASS_STRUCTURE_ONLY | Constructs with `OpenAIChatClient(model=, api_key=)`, bare `tools=get_weather` accepted. Snippet omits `import os` and the `get_weather` definition. |
| chapter_03_02 | :28 | PASS_STRUCTURE_ONLY | Same class `OpenAIChatClient` with `azure_endpoint`/`api_version`/`credential=AzureCliCredential()` constructs (claim "same class" verified). Omits `import os`, `Agent`, `get_weather`. |
| chapter_03_03 | :49 | PASS_STRUCTURE_ONLY | `AnthropicClient(model=..., api_key=)` and `GeminiChatClient(api_key=, model=)` construct. `GeminiChatClient()` with no args works only with `GOOGLE_API_KEY`+`GOOGLE_MODEL` env (verified); else `ValueError`. Extra packages `agent-framework-anthropic/-gemini` needed. |
| chapter_03_04 | :93 | PASS | Instructions string is sent as `options["instructions"]` on every request (checked across 2 session turns). |
| chapter_03_05 | :120 | PASS | Session replays prior user/assistant/function_call/function_result messages on the 3rd call. `OpenAIChatClient()` no-arg works only with `OPENAI_API_KEY`+`OPENAI_MODEL` env. |
| chapter_03_06 | :140 | PASS | `CustomHistoryProvider` verbatim works: replays history, per-session isolation. Note: a run without a session still creates a throwaway session and writes it to the provider. |
| chapter_03_07 | :181 | MISMATCH | see below (undefined `FixedTokenizer`). Hierarchy claim (run > agent > client) verified PASS with a defined tokenizer. |
| chapter_03_08 | :228 | PASS | `result.value` is a `OutputStruct` instance; `response_format` forwarded to client; streaming via `AgentResponse.from_update_generator(..., output_format_type=)` works. Caveats: `result.value` is `None` only when no `response_format` was given; if the model output is not valid JSON it **raises pydantic `ValidationError`** (not None). |
| chapter_03_09 | :255 | PASS_STRUCTURE_ONLY | Dict `response_format` passes through unchanged to the client; strict-schema enforcement is provider-side (NEEDS_MODEL). `runtime_schema` is undefined in the snippet. |
| chapter_04_01 | 03-part-2-core-architecture/chapter-04-...md:9 | PASS | name/description/param type/`Field` description derived from signature; `required` correct; end-to-end tool loop works. Body `...` returns None (stub). Also verified: `schema=` override, declaration-only tool (not executed, call returned to caller), bound method as tool. |
| chapter_04_02 | :38 | PASS_STRUCTURE_ONLY | `client.get_code_interpreter_tool()` -> `{'type': 'code_interpreter', ...}`, accepted as bare `tools=`; reaches request. Execution NEEDS_MODEL. |
| chapter_04_03 | :57 | PASS_STRUCTURE_ONLY | `client.client.vector_stores.files.create_and_poll` exists; `get_file_search_tool(vector_store_ids=[...])` is keyword-only, returns `{'type':'file_search',...}`. Upload/search NEEDS_MODEL. (`...` and `file` placeholders.) |
| chapter_04_04 | :76 | PASS_STRUCTURE_ONLY | `get_web_search_tool(user_location={...})` OK; city/country preserved. Search NEEDS_MODEL. |
| chapter_04_05 | :93 | PASS_STRUCTURE_ONLY | `get_mcp_tool(name,url,headers,approval_mode)` returns `type: mcp`, `require_approval: never`; hosted (provider-executed). Real GitHub call NEEDS_MODEL. |
| chapter_04_06 | :110 | MISMATCH | see below (needs a session). |

Prose claims in 4.8 (all PASS): `ctx.add_tools` progressive exposure (tool absent in request 1, present in request 2; experimental warning `PROGRESSIVE_TOOLS`); `max_invocations` caps a tool (2nd call returns `Error:` to model); `max_invocation_exceptions`; tool exceptions returned to model not raised; `function_invocation_configuration["max_iterations"]`.

## MISMATCHes

### 1. chapter_04_06 (chapter-04-tools-and-skills.md:110-125) - approval loop silently never runs the tool
- Book: loop calls `agent.run(query)` / `agent.run(new_inputs)` with no session, "approve it" then continues.
- Actual (1.21.0): logs "Ignored one or more local tool-approval responses because this run has no authoritative AgentSession holding the matching approval request..." The approved tool is **never executed** (`ran == []`) and the model gets no function_result; the loop terminates only because the scripted/real model answers anyway.
- Verified fix: create a session and pass it on both runs:
  ```python
  session = agent.create_session()
  result = await agent.run(query, session=session)
  while len(result.user_input_requests) > 0:
      new_inputs = [query]
      for u in result.user_input_requests:
          new_inputs.append(Message("assistant", [u]))
          new_inputs.append(Message("user", [u.to_function_approval_response(approved)]))
      result = await agent.run(new_inputs, session=session)
  ```
  Approved -> tool runs, `function_result 'sent to a@b.c'`; denied -> result is `Error: Tool call invocation was rejected by user.` Alternative without a session: `client.function_invocation_configuration["disable_approval_response_binding"] = True` (verified). Tests: `test_04_06_*`. Example: `examples/ch02_04/05_tool_approval_loop.py`.
- Also: the book's text (4.7) should mention the session requirement; the book's 4.7 prose says `function_tool_with_approval_and_sessions.py` is a separate combination, implying sessions are optional.

### 2. chapter_03_07 (chapter-03-anatomy-of-an-agent.md:181-205) - `FixedTokenizer` undefined
- Book uses `FixedTokenizer(7)` etc.; not exported from `agent_framework` (`NameError`/ImportError). Also `TruncationStrategy`, `SlidingWindowStrategy` imports are not shown (they are exported from `agent_framework`).
- Verified fix: define a tokenizer implementing `TokenizerProtocol`, or use the built-in `CharacterEstimatorTokenizer`:
  ```python
  from agent_framework import Agent, TruncationStrategy, SlidingWindowStrategy
  class FixedTokenizer:
      def __init__(self, n): self.n = n
      def count_tokens(self, text: str) -> int: return self.n
  ```
  (`agent_framework.CharacterEstimatorTokenizer` exists as a real export.) Also the snippet's `OpenAIChatClient(compaction_strategy=..., tokenizer=...)` constructor kwargs are valid in 1.21.0; with an omitted model/key the client needs `OPENAI_*` env vars.

## Minor notes (not counted as mismatches)
- Several fragments omit imports/definitions (`os`, `get_weather`, `Agent`, `runtime_schema`, `messages`).
- `result.value` raises `ValidationError` on invalid JSON (see chapter_03_08); the `if structured_data := result.value:` idiom does not guard against that.

## NEEDS_MODEL
Real-provider behaviour for 02_01, 03_01-03_03 (calls), 03_09 (strict schema), 04_02-04_05 (hosted code interpreter, file search, web search, GitHub MCP).
