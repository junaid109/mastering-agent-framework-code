# ch06_08 results (Chapters 6, 7, 8) - agent-framework 1.21.0, agent-framework-orchestrations 1.3.1

Run: `.venv\Scripts\python.exe -m pytest tests/ch06_08` -> **60 passed**. Examples: `python examples/ch06_08/0N_*.py` (all 4 run offline).
No real model/credentials were needed anywhere. Workflows, edges, switch/multi-select, fan-out/in, checkpoints, request_info,
resume, time-travel, Sequential/Concurrent/GroupChat/Handoff/Magentic were all executed for real with scripted agents.

## Snippet table

| snippet | book location | status | evidence / notes |
|---|---|---|---|
| chapter_06_01.py | ch06:15 | PASS | `UpperCase(Executor)` runs; NB `UpperCase()` raises TypeError, `Executor.__init__` needs `id=` (snippet never shows instantiation). test_ch06_02_..., test_executor_requires_explicit_id |
| chapter_06_02.py | ch06:24 | PASS | `@executor(id=...)` keeps id; `WorkflowContext[Never, str]` -> `output_types==[]`, `workflow_output_types==[str]` |
| chapter_06_03.py | ch06:32 | PASS | `get_outputs() == ['DLROW OLLEH']` (matches inline comment); factory-vs-singleton state-leak claim verified |
| chapter_06_04.py | ch06:49 | PASS | `event.type=="output"` + `AgentResponseUpdate.author_name` yields `[writer]`, `[reviewer]` in order; reviewer saw writer text |
| chapter_06_05.py | ch06:67 | PASS | non-spam -> email branch, spam -> spam branch, unparseable -> neither branch fires (fail closed); `response_format` gives `.value`. Switch-case and multi-selection prose also verified |
| chapter_06_06.py | ch06:93 | PASS | aggregator fires exactly once, only after all 3 branches `executor_completed`; every branch got the same prompt |
| chapter_07_01.py | ch07:13 | PASS | `get_latest(workflow_name=workflow.name)`, `.checkpoint_id`, `.iteration_count`; `run(checkpoint_id=..., stream=True)` works. Caveat below (workflow name) |
| chapter_07_02.py | ch07:37 | PASS | `...` body filled in; `request_info` event emitted, state `IDLE_WITH_PENDING_REQUESTS`, `responses={request_id: "approve"}` resumes; pending request stored in checkpoint; survives "restart" with `FileCheckpointStorage`. Caveat below (allowed types) |
| chapter_08_01.py | ch08:9 | PASS | triage -> refund via auto `handoff_to_refund` tool (HandoffSentEvent), termination_condition ends run with no user prompt. Needs `require_per_service_call_history_persistence=True` on every agent (not in book) |
| chapter_08_02.py | ch08:31 | PASS | Magentic with scripted manager: plan -> delegate -> ledger satisfied -> final answer; `max_round_count`, stall->replan, `max_reset_count` caps all verified |

Prose claims also executed: sub-workflows (`WorkflowExecutor`), `output_from` / `intermediate_output_from`, WorkflowViz mermaid export, list_checkpoints +
resume from an earlier checkpoint (worker re-runs; newest checkpoint does not), `on_checkpoint_save/restore` hooks, `executor_invoked/completed` events,
Sequential (growing shared context), Concurrent (independent context, custom aggregator), GroupChat (function selector, `max_rounds`, LLM manager via
`orchestrator_agent`), Handoff autonomous mode, `workflow.as_agent()`, `agent.as_mcp_server()`, `CosmosCheckpointStorage` import (no Azure call).

## MISMATCHES

1. **ch06:108 (section 6.6)** - "Omitting both selections still works today but emits a deprecation warning."
   Actual: no warning at build or run (checked with `warnings.simplefilter("always")`). In 1.21.0 omitting both is the documented default ("every
   `yield_output` emits `output`"). Only the alias `output_executors=` is deprecated. Test: `test_omitting_both_selections_does_NOT_warn_in_1_21_0`.
   Fix: reword to "By default every `yield_output` is workflow output; pass `output_from` to restrict it (`output_executors` is the deprecated alias)."
   Related (worth stating): agent nodes' `AgentResponse` are also workflow outputs by default, so `get_outputs()` in 6.4/6.5 workflows includes them unless `output_from=[...]` is set; an empty `output_from=[]` raises WorkflowValidationError.

2. **ch07:57 (section 7.3)** - "SequentialBuilder, ConcurrentBuilder, GroupChatBuilder, and HandoffBuilder ... all expose `.with_request_info()`".
   Actual: `HandoffBuilder` has no `with_request_info` (AttributeError). It already pauses for the user itself (`HandoffAgentUserRequest`, answered with
   `HandoffAgentUserRequest.create_response("...")`). Sequential/Concurrent/GroupChat do have it (verified; responses are `AgentRequestInfoResponse.approve()/from_strings([...])`).
   Test: `test_ch07_03_MISMATCH_handoffbuilder_has_no_with_request_info`. Fix: drop HandoffBuilder from the list; mention `HandoffAgentUserRequest`.

3. **ch08:27 and ch08:57 (sections 8.1, 8.4)** - `GroupChatBuilder ... .with_orchestrator(agent=manager)`.
   Actual: no `with_orchestrator` method (AttributeError). Verified fix: `GroupChatBuilder(participants=[...], orchestrator_agent=manager).build()`
   (manager must emit JSON `{terminate, reason, next_speaker, final_message}`); function selector is `selection_func=` (also constructor kwarg). Test: `test_ch08_01_MISMATCH_groupchat_has_no_with_orchestrator_method`
   and `test_ch08_01_groupchat_llm_manager_via_orchestrator_agent_picks_speakers_and_terminates`.

4. **ch08:55 (section 8.4)** - Handoff without a termination_condition "keeps requesting user input until a configured `max_turns` is hit".
   Actual: there is no `max_turns` anywhere in HandoffBuilder / orchestrations (TypeError on `max_turns=`). Without a termination_condition the workflow
   just keeps pausing for user input indefinitely (3 turns verified, still asking). Only autonomous mode has a turn limit (`with_autonomous_mode(turn_limits=...)`).
   Test: `test_ch08_04_MISMATCH_no_max_turns_setting_exists`.

5. **ch08:63 (section 8.5)** - human review in a Magentic team via "`with_request_info()`".
   Actual: `MagenticBuilder` has no `with_request_info`; the mechanism is `enable_plan_review=True` / `.with_plan_review()`, which emits a
   `MagenticPlanReviewRequest` (answer with `request.data.approve()`); verified that no participant runs before sign-off.

## Undocumented gotchas (book silent, not counted as mismatches)

- `HandoffBuilder.build()` raises ValueError unless every agent sets `require_per_service_call_history_persistence=True`.
- `FileCheckpointStorage` refuses to deserialize your own request types (e.g. `HumanApprovalRequest`) unless listed in `allowed_checkpoint_types=["module:Class"]`.
  The run does NOT fail: the pending-approval checkpoint is silently skipped (warning in logs only). Test: `test_ch07_02_GOTCHA_file_storage_silently_drops_...`.
- `get_latest(workflow_name=workflow.name)` after a real restart needs a stable `WorkflowBuilder(name="...")`; unnamed workflows get a random name per instance.
- Orchestration builders return an `AgentResponse` as output (not a list of messages): Sequential -> last stage only, GroupChat -> orchestrator's closing message unless `output_from="all"`.

## Status counts

PASS 10 / PASS_STRUCTURE_ONLY 0 / NEEDS_MODEL 0 / SKIPPED_PLACEHOLDER 0 / MISMATCH 0 at snippet level; 5 prose MISMATCHES (above).
