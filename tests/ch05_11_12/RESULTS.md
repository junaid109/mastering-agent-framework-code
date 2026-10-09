# ch05_11_12 results (agent-framework 1.21.0, offline)

Run: `.venv\Scripts\python.exe -m pytest tests/ch05_11_12 -q` -> 55 passed (see bottom for the exact count at last run).
Files: `test_ch05_middleware.py`, `test_ch11_observability.py`, `test_ch12_security.py`, `helpers.py` (UsageScriptedClient: ScriptedChatClient variant that also returns `usage_details`; `support/fake_client.py` was NOT edited).

## Snippet table

| snippet file | book location | status | evidence / notes |
|---|---|---|---|
| chapter_05_01.py | chapter-05-middleware.md:15 | PASS (client swapped; one caveat, see M2) | `test_5_1_*`: mixed `middleware=[agent_fn, function_fn]` list routes by context type; function logging prints; password message blocks before any model call (`client.requests == []`). Caveat: blocked `run()` returns `None`. |
| chapter_05_02.py | chapter-05-middleware.md:49 | PASS (`detect_attack` stubbed) | `test_5_3_*`: `raise MiddlewareTermination` in `FunctionMiddleware.process` -> tool body never executes, warning logged, tool loop ends (1 model request). Real ATR ruleset engine is an external dependency, not in the venv, so detection logic is a stub; the middleware code itself is verbatim. |
| chapter_05_03.py | chapter-05-middleware.md:67 | PASS | `ContentLabel(integrity=TRUSTED, confidentiality=PRIVATE, metadata=...)` constructs; enums have exactly TRUSTED/UNTRUSTED and PUBLIC/PRIVATE/USER_IDENTITY; `to_dict/from_dict` round-trip. |
| chapter_05_04.py | chapter-05-middleware.md:83 | PASS | `print_usage` with `@chat_middleware`: streaming path (`stream_result_transforms`) prints `Usage: ...`; non-streaming `context.result.usage_details` readable after `call_next()`. Chat middleware ran 3x in a 3-turn tool loop vs agent middleware 1x (book claim confirmed). Needed `UsageScriptedClient` (usage not provided by the stock fake client). |
| chapter_05_05.py | chapter-05-middleware.md:107 | PASS (client swapped; `secure_config = SecureAgentConfig()`) | `SecureAgentConfig` is a `ContextProvider`; injects `quarantined_llm` + `inspect_variable` tools, instructions and label/policy middleware; scripted `quarantined_llm` call resolved. |
| chapter_05_06.py | chapter-05-middleware.md:123 | PASS_STRUCTURE_ONLY | `...` body; decorator form compiles and is accepted. |
| chapter_05_07.py | chapter-05-middleware.md:131 | PASS_STRUCTURE_ONLY | `...` body; `FunctionMiddleware` subclass with `process` valid. Class-form state persistence tested separately (`test_5_7_class_form_keeps_state...`). |
| chapter_11_01.py | chapter-11-observability-and-monitoring.md:9 | PASS | Both forms run in subprocesses: `configure_otel_providers()` with `OTEL_EXPORTER_OTLP_ENDPOINT` set builds an `OTLPSpanExporter`; without env is harmless; `enable_console_exporters=True` prints `invoke_agent` / `chat` spans to stdout. |
| (no chapter_12 snippets) | chapter-12 has no code blocks | n/a | Prose claims tested in `test_ch12_security.py` (see below). |

## Prose claims verified (PASS)
- 11.1 instrumentation on by default (`OBSERVABILITY_SETTINGS.enable_instrumentation is True`), sensitive data off by default.
- 11.1 in-memory span exporter: one trace; `invoke_agent WeatherAgent` root with child `chat` x2 and `execute_tool get_weather`; GenAI attrs (`gen_ai.operation.name`, `gen_ai.agent.name`, `gen_ai.tool.name`, `gen_ai.provider.name`, `gen_ai.request.model`); durations > 0.
- 11.1 default traces contain no prompt text; `OBSERVABILITY_SETTINGS.enable_sensitive_data = True` puts content in `gen_ai.input.messages`.
- 11.2 token usage on chat span (`gen_ai.usage.input_tokens/output_tokens`), metrics `gen_ai.client.token.usage` and `gen_ai.client.operation.duration` exported; failing tool span has ERROR status.
- 11.4 logger provider configured by the same call.
- 12.1/12.6 FIDES: private read then public post -> approval request, tool not run; untrusted tool output hidden from the next model request.
- 12.2 `approval_mode="always_require"` blocks until approval (needs the same `AgentSession` passed back), rejection does not execute; `LocalShellTool` defaults to `always_require` and has `acknowledge_unsafe`; `ShellPolicy` allow-list accepts `echo $(whoami)`, `` echo `id` ``, `ls; curl .. | sh` (text-only filtering claim confirmed); Monty/Hyperlight CodeAct providers import.

## MISMATCHes

**M1. `context.terminate` does not exist** -- chapter-05-middleware.md:41 (pre/post-termination paragraph) and :99 (spending-cap sentence).
- Book: `middleware_termination.py` "sets a `context.terminate` flag" before/after `call_next()`; chat middleware "can stop the pipeline ... via `context.terminate`".
- Actual (1.21.0): `hasattr(context, "terminate")` is False for Agent/Chat/FunctionInvocation contexts (`test_5_2_context_terminate_flag_does_not_exist_in_1_21`). Termination is `raise MiddlewareTermination(...)` (exported from `agent_framework`).
- Verified fix (pre-termination, agent layer): set a result then raise, so callers get a response:
  ```python
  async def pre_term(context: AgentContext, call_next):
      context.result = AgentResponse(messages=[Message(role="assistant", contents=["denied"])])
      raise MiddlewareTermination("policy")
  ```
  Spending cap at chat layer (verified, second model call never fires, `run()` returns the budget message):
  ```python
  class Cap(ChatMiddleware):
      async def process(self, context: ChatContext, call_next):
          if total["tokens"] >= LIMIT:
              context.result = ChatResponse(messages=[Message(role="assistant", contents=["Budget exhausted."])])
              raise MiddlewareTermination("budget exhausted")
          await call_next()
          total["tokens"] += context.result.usage_details["total_token_count"]
  ```
  Without setting `context.result`, a chat-layer termination crashes the tool loop with `AttributeError: 'NoneType' object has no attribute 'usage_details'` (`_tools.py:5474`), and at the agent layer `run()` returns `None`.
- Related nuance: "post-termination" does not stop later work. Raising `MiddlewareTermination` after `call_next()` in chat middleware keeps the response but the tool loop still fires the next model call (2 requests; `test_5_2_post_termination_at_chat_layer_does_not_stop_tool_loop`).

**M2. Blocking by not calling `call_next()` returns `None`** -- chapter-05-middleware.md:19-20 (snippet chapter_05_01). Book comment says "not calling call_next() stops execution here". True, but `agent.run()` then returns `None`, so `result.text` raises `AttributeError` (`test_5_1_blocked_run_returns_None_not_a_response`). Verified fix: `context.result = AgentResponse(messages=[Message(role="assistant", contents=["Request blocked."])])` before `return` (`test_5_1_blocked_run_with_explicit_result`).

**M3. `HistoryProvider.clear(session_id)` is not on every backend** -- chapter-12-security-and-responsible-ai.md:21 ("available on every HistoryProvider backend ... file, Cosmos DB, Redis, or a custom implementation -- because clear is part of the same abstraction").
- Actual: no `clear` on `HistoryProvider`, `InMemoryHistoryProvider` or `FileHistoryProvider`. It exists (async, `clear(self, session_id)`) only on `CosmosHistoryProvider`, `RedisHistoryProvider` and `VectorStoreHistoryProvider` (`test_12_4_MISMATCH_clear_is_not_part_of_the_HistoryProvider_abstraction`; Cosmos/Redis behaviour itself needs a live service, signature only checked).
- Verified workarounds: in-memory -> `session.state.clear()`; file -> delete the per-session file(s) in `storage_path` (names are encoded, e.g. `~session-<...>.jsonl`, so delete the directory contents/glob `*.jsonl`); negative controls confirm history is otherwise remembered.

## Unverified / NEEDS_MODEL / other
- chapter-05:117 "`X-MCP-Features: ifc_labels` header opts into a server emitting trust labels": string `ifc_labels` / `X-MCP-Features` appears nowhere in the installed packages (security.py has `apply_mcp_security_labels` mapping MCP tool *annotations* to labels, and `SecureMCPToolProxy`). Could live only in the GitHub sample; UNVERIFIED, not marked a mismatch.
- Real `FoundryChatClient`, real ATR ruleset (`detect_attack`), `github_mcp_example.py`, DevUI and Graphviz export (11.3: only `WorkflowViz` existence checked) were not executed (NEEDS_MODEL / external service).
- Chapter 5 claim that `context.messages[-1].text` exists, `context.stream`, `stream_update_transforms`, `stream_result_transforms`: PASS.
- Untyped middleware functions without a decorator raise `MiddlewareException: Cannot determine middleware type` (annotate the first param or use `@agent_middleware/@function_middleware/@chat_middleware`); consistent with chapter 5.7 but worth knowing.
- `ENABLE_INSTRUMENTATION=false` is overridden when `configure_otel_providers()` is called (spans still emitted); not a chapter claim, so no test kept.
