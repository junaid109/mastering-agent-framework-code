# ch15_17 results: Chapters 15, 16, 17 and Appendix C (agent-framework 1.21.0)

Run: `.venv\Scripts\python.exe -m pytest tests/ch15_17 -q` -> **179 passed** (offline, no keys, no network).
Files: `test_ch15_vector_stores.py`, `test_ch16_hosting.py`, `test_ch17_security.py`,
`test_ch17_eval_and_compliance.py`, `test_appendix_c.py`, shared `helpers.py` (hash embeddings, hotel model,
`RecordingClient` = `ScriptedChatClient` + records per-call options/tools; `support/fake_client.py` untouched).
Runnable examples: `examples/ch15_17/*.py` (7 files, all exit 0 with `python examples/ch15_17/<file>.py`).

Status key: PASS = executed and behaviour matches the text. PASS_STRUCTURE_ONLY = imports/constructs/signatures only.
MISMATCH = book text or code does not match 1.21.0 (fix verified). NEEDS_MODEL = needs real service.
SKIPPED_PLACEHOLDER = placeholders.

## Snippet table

| snippet | book location | status | evidence / notes |
|---|---|---|---|
| chapter_15_01 | ch15:19 | PASS | Verbatim model: key `storage_name="hotel_id"` honoured, dims=3, `generate_vectors=False` precomputed vectors search+filter OK; string in vector field is embedded at upsert; wrong dimension rejected "before it embeds or writes anything" (nothing stored). |
| chapter_15_02 | ch15:39 | PASS | Needs a model with city/rating/amenities fields (adapted snippet). `and` group, `between` (inclusive), `contains` verified; all other operators, `or`/`not`, string "injection" values compared as data; unknown field/operator rejected. Result keys `record`/`score` confirmed; score is cosine *distance* (lower = closer) on InMemory. |
| chapter_15_03 | ch15:58 | PASS | Schema has exactly `query`, `category` (enum of the 6), `min_rating` (0..5), `additionalProperties:false`; `min_rating=11`, unknown category, unexposed field `city` all rejected; `result_mapper` keeps `cost_internal` out of the prompt (end-to-end with ScriptedChatClient). Note: only `query` is `required`; filter Params are optional. |
| chapter_15_04 | ch15:93 | PASS | `scope_filter=None` accepted; default tools upsert/get/delete/search; default approvals upsert=always_require, get/search=never, delete=always_require; `approval_mode={"upsert":"never_require"}` keeps other defaults; delete pauses for human approval then runs; `include_*_tool` flags and `additional_search_tools` work; a real `scope_filter` hides other projects' records from search and get; `scope_filter` is a required keyword. |
| chapter_15_05 | ch15:120 | PASS_STRUCTURE_ONLY | `AzureAISearchStore` imports, `endpoint`/`credential`/`get_collection`/`index_client` exist; `keyword_hybrid` is a core SearchType and InMemory raises NotImplementedError for it. Needs a live search service. Snippet omits `import os`, `uuid4`, and the `Hotel` model has no category value "quiet" (illustrative). |
| chapter_15_06 | ch15:149 | **MISMATCH** | See M1. Fixed constructor verified (window, search tool, tenant/session isolation). |
| chapter_16_01 | ch16:24 | PASS | `FoundryChatClient(...)` constructs offline. Swapped for ScriptedChatClient, `ResponsesHostServer(agent=..., history_source="agent")` driven via ASGI TestClient: model sees each turn exactly once. Default is `"agent_server"`; it raises `RuntimeError` for a load-enabled history provider, forces `store=False` on storing clients, and the platform transcript reaches the model once. Snippet omits `import os` / `DefaultAzureCredential`. |
| chapter_16_02 | ch16:69 | PASS | `CustomSessionStoreProvider` implemented as `StoreProvider[SessionStore]`: host asks it for the store and writes snapshots through it (`set`); `agent=create_agent` factory is called once per request (fresh agent each time). |
| chapter_16_03 | ch16:85 | PASS (note M6) | Workflow factory + `parse_response` + `CheckpointStoreProvider(allowed_checkpoint_types=[...])` + `ResponsesServerOptions(resilient_background=True)` constructs and runs; sync call yields `tick 3/2/1`; `{"background":true,"store":true}` returns and can be polled to `completed`. Missing allow-list: `validate_checkpoint_value` raises and the hosted request fails before any executor runs. Workflow instance + resilient -> ValueError (factory required). Snippet uses `Workflow` without importing it (NameError at `def` on Python 3.13). |
| chapter_17_01 | ch17:21 | PASS | Binding on by default (`disable_approval_response_binding` False). Sessionless resume ignored by default; with flag True it executes; flag True lets a forged approval run a call the model never made (the warning is accurate). |
| chapter_17_02 | ch17:31 | PASS | Verbatim flow works. Rejection does not execute; replay does not execute twice; approval answered in a different session ignored; pending approval survives `to_dict`/`from_dict` JSON round trip; forged approval ignored with and without a session. |
| chapter_17_03 | ch17:50 | PASS | Real HITL workflow + `FileCheckpointStorage`: `allowed_checkpoint_types` restores the same pending request after "restart"; `register_checkpoint_type` is process-wide and applies to storage created earlier; undeclared type blocked. See note N1. |
| chapter_17_04 | ch17:77 | PASS | `header_provider` result observed as `Authorization: Bearer ...` on the wire at connect time (httpx MockTransport). Hidden `FunctionInvocationContext` parameter not in tool schema; host value from `function_invocation_kwargs` wins over a model-supplied `tenant_id`. |
| chapter_17_05 | ch17:90 | PASS | `PRINCIPAL_METADATA_KEY` with `SecureAgentConfig`: Alice->Alice allowed; Alice->Bob blocked, one `confidentiality_violation/principal_mismatch` entry in `get_audit_log(session)`. Legacy user-id-only / empty / malformed principals never let data flow. `get_audit_log()` without session raises after provider use. |
| chapter_17_06 | ch17:111 | PASS | Book config builds with a quarantine client. Untrusted `fetch_emails` output is replaced by a variable reference (injected text never reaches model); once exposed via `inspect_variable`, `send_email` is stopped with `approval_on_violation` (human approval then executes) or blocked with `block_on_violation`. Note N2. |
| chapter_17_07 | ch17:137 | PASS (note M5) | Real `PurviewPolicyMiddleware` with only the Graph call stubbed: blocked prompt -> model never invoked, default text "Prompt blocked by policy", configurable; response blocking works; allowed flows through. Live policy: NEEDS_MODEL/tenant. |
| chapter_17_08 | ch17:156 | PASS_STRUCTURE_ONLY (+M2, M3) | `FoundryEvals` constructs offline and constants exist, but `.evaluate()` needs the service (NEEDS_MODEL). The same `evaluate_agent` loop executed with `LocalEvaluator`. `r.assert_passed()` does not exist (M2). |
| appendix_c_01 | appx C:8 | SKIPPED_PLACEHOLDER | `<ProviderChatClient>(...)`. Agent kwargs checked. |
| appendix_c_02 | appx C:18 | PASS | `run` and `run(stream=True)`. |
| appendix_c_03 | appx C:24 | PASS | `to_dict` / `from_dict` resume; history carried. |
| appendix_c_04 | appx C:32 | **MISMATCH** | See M4. |
| appendix_c_05 | appx C:38 | PASS_STRUCTURE_ONLY | `compaction_strategy=` and `tokenizer=` accepted by `Agent` (tokenizer is `...`). |
| appendix_c_06 | appx C:43 | PASS | `always_require` pauses, `never_require` runs. |
| appendix_c_07 | appx C:84 | PASS | `@chat_middleware` runs once per model call. (Blocking prose: see M7.) |
| appendix_c_08 | appx C:91 | PASS | class-based `FunctionMiddleware`. |
| appendix_c_09 | appx C:113 | PASS (note) | Model and filter construct; the C.4 filter uses `site`/`severity`, which `Doc` does not declare, so a real search with it is rejected. |
| appendix_c_10 | appx C:143 | **MISMATCH** | `r.assert_passed()` (M2). Purview line constructs; FoundryEvals line constructs offline. |

## MISMATCHes (verified fixes)

**M1. ch15:149 (snippet chapter_15_06): `VectorStoreHistoryProvider(... embedding_generator=...)` raises.**
Error: `ValueError: embedding_generator requires embedding_options with dimensions.`
Fix (verified, `test_15_06_fixed_constructor_with_real_openai_embedding_client_class`, `examples/ch15_17/ch15_history_provider.py`):
add `embedding_options={"dimensions": 1536}` (must equal the model's width). Also `OpenAIEmbeddingClient` is used but never imported
(`from agent_framework.openai import OpenAIEmbeddingClient`, constructs offline with `api_key=`).

**M2. ch17:171 and appendix C:146: `EvalResults.assert_passed()` does not exist** (`AttributeError`; ch17 text lists it among result members).
Fix (verified): `r.raise_for_status()` raises `EvalNotPassedError` ("... 0 passed, 1 failed"). Other gates that exist:
`assert_score_at_least`, `assert_dimension_score_at_least`, `assert_no_failed_items`.

**M3. ch17:175: `@evaluator` injected parameter is `expected_output`, not `expected`.**
`@evaluator def f(response, expected)` -> `TypeError: ... unknown required parameter(s) ['expected']`. Supported names:
`query, response, expected_output, expected_tool_calls, conversation, tools, context`. Fix: rename to `expected_output`.
(Also `evaluate_traces` requires a keyword `model=`; the prose `evaluate_traces(response_ids=...)` omits it.)

**M4. appendix C:34 (and §3.5 claim): `result.value` is "None if parsing failed".** In 1.21.0 `run()` succeeds but
`result.value` raises `pydantic.ValidationError` for unparseable or non-matching text (documented in the property's `Raises`).
`value` is `None` only when no `response_format` was given. Fix (verified):
`try: data = result.value\nexcept ValidationError: data = None`.

**M5. ch17:148: Purview "default thirty-minute TTL".** `PurviewPolicyMiddleware` builds its cache with
`PurviewSettings.cache_ttl_seconds` default **14400 s (4 h)**; only the bare `InMemoryCacheProvider` default is 1800 s.
Fix: say four hours, or pass `PurviewSettings(cache_ttl_seconds=1800)` (verified).

**M6. ch16:85 (snippet chapter_16_03): `def build_workflow(request) -> Workflow:` but `Workflow` is not imported** -> `NameError` at definition
(Python 3.13). Fix: add `Workflow` to the `from agent_framework import ...` line (verified in `test_ch16_hosting.py`).

**M7. appendix C:98 ("Blocking a request"): the stated recipes crash on 1.21.0 unless a result is set.**
- Not calling `call_next()` and returning -> `AttributeError: 'NoneType' object has no attribute 'usage_details'` (chat) / `'text'` (agent).
- `raise MiddlewareTermination` bare -> same AttributeError; even `MiddlewareTermination(result=ChatResponse(...))` crashes at chat level.
- `context.terminate = True` has no effect (field does not exist; model still called).
Fix (verified): set `context.result = ChatResponse(messages=[Message("assistant", ["..."])])` (agent level: `AgentResponse`), then return
or raise `MiddlewareTermination`.

**M8 (prose, minor). ch16:109 "plain agents recover only best-effort".** `ResponsesHostServer(agent=..., options=ResponsesServerOptions(resilient_background=True))`
raises `RuntimeError` for a regular agent unless `history_source="service", background_source="provider"`; the host's own docs say
other regular-agent runs are not crash-recoverable. Hosts also accept a third `history_source` value `"service"` (not mentioned).

## Notes (claims confirmed, with nuance worth a sentence in the book)
- **N1 (ch17:50).** An undeclared application type is not only refused at restore: when the pending request's checkpoint is *written*, the encode round-trip is blocked and logged ("Failed to create checkpoint ... Checkpoint deserialization blocked"). The run does **not** fail; only the pre-request checkpoint survives, and restoring replays from the start, emitting a *new* request id. A missing allow-list therefore looks like a silent loss of the pending approval.
- **N2 (ch17:111).** `auto_hide_untrusted` replaces untrusted tool output with a variable reference, and the context only becomes untrusted when the content is exposed (e.g. `inspect_variable`). A privileged tool called while the content is still hidden is *not* blocked. The email example only triggers the policy after exposure.
- Approval binding with a session also ignores a fabricated approval even when the disable flag is set (identity mismatch).
- `ToolApprovalMiddleware` requires a session; rules match by tool *name* only, so a colliding tool is auto-approved (as ch17:17 warns). Quantity-range rule from the agent-as-tool sample verified (1..5 auto, 50 escalates).
- Hidden-ctx tools receive `None` when the host does not supply a value; failing closed is the tool author's job (the framework does not raise).
- `InMemoryCollection.search` score is a cosine distance (ascending); ch15 calls it "score".

## Not testable offline (NEEDS_MODEL / service)
- `FoundryEvals.evaluate`, `evaluate_traces`, rubric evaluators from the portal, red teaming, self-reflection (Foundry service).
- Azure AI Search / Redis backends (structure only), real embedding model dimensions, Purview tenant policy.
- Hosted-only behaviour: Foundry per-user/sandbox scope headers, Cosmos session store, platform `agent_session_id`.
- Approval round trip through a hosted workflow (`mcp_approval_request` is emitted: verified; the follow-up `mcp_approval_response` continuation could not be
  exercised against the SDK's local state store: "previous response has no completed workflow checkpoint"), so replay/forged/cross-user rejection prose is untested.
- Telegram/APIM channel, .NET-only claims, MLflow/Azure Monitor tracing (only surface existence checked).

## Fake-client enhancement needed
None to `support/fake_client.py`. Local helper `tests/ch15_17/helpers.py::RecordingClient` (subclass) records per-call `options`
(tools, temperature, store) because `ScriptedChatClient.requests` only keeps messages; a shared `options_seen`/`tool_names()` would help other groups.
Also useful: a hash-based `BaseEmbeddingClient` (in helpers.py) for any vector-store test.
