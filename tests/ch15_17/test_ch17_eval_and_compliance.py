"""Chapter 17 (evaluation, compliance, observability) + 17.10 release-gate design, executed offline."""
import inspect

import pytest
from agent_framework import (
    Agent,
    EvalNotPassedError,
    EvalItemResult,
    EvalResults,
    EvalScoreResult,
    ExpectedToolCall,
    LocalEvaluator,
    RubricScore,
    evaluate_agent,
    evaluator,
    keyword_check,
    tool,
    tool_called_check,
)

from support.fake_client import Reply, ScriptedChatClient

pytestmark = pytest.mark.filterwarnings("ignore")


@tool
def get_weather(city: str) -> str:
    """Weather for a city."""
    return f"Sunny in {city}"


@tool
def get_flight_price(origin: str, destination: str) -> str:
    """Flight price."""
    return "EUR 420"


def _weather_agent(replies=None):
    replies = replies or [Reply.tool_call("get_weather", {"city": "Seattle"}), Reply.text("It is sunny in Seattle.")]
    return Agent(client=ScriptedChatClient(replies), name="weather", tools=[get_weather, get_flight_price],
                 instructions="x")


QUERIES = ["What's the weather like in Seattle?"]


# ------------------------------------------------------------------ chapter_17_08 shape with LocalEvaluator
async def test_17_08_evaluate_agent_returns_one_result_per_provider_with_documented_fields():
    agent = _weather_agent()
    results = await evaluate_agent(agent=agent, queries=QUERIES,
                                   evaluators=LocalEvaluator(keyword_check("sunny"), tool_called_check("get_weather")))
    assert isinstance(results, list) and len(results) == 1
    r = results[0]
    # passed / failed / total / all_passed / report_url, as in the book's print loop
    assert (r.passed, r.failed, r.total, r.all_passed) == (1, 0, 1, True)
    assert r.report_url is None
    assert f"{r.passed}/{r.total} passed" == "1/1 passed"
    assert set(r.per_evaluator) == {"keyword_check", "tool_called"}


async def test_17_08_one_result_object_per_evaluator_provider():
    agent = _weather_agent([Reply.text("Sunny.")] * 2)
    a = LocalEvaluator(keyword_check("sunny"))
    b = LocalEvaluator(keyword_check("rain"))
    results = await evaluate_agent(agent=agent, queries=["q"], evaluators=[a, b])
    assert len(results) == 2 and [r.all_passed for r in results] == [True, False]


def test_17_08_assert_passed_does_not_exist_in_1_21_0():
    """MISMATCH: book 17.8 and Appendix C.4 call r.assert_passed()."""
    r = EvalResults(provider="x", result_counts={"passed": 1, "failed": 0})
    assert not hasattr(r, "assert_passed")
    assert not hasattr(EvalResults, "assert_passed")


async def test_17_08_raise_for_status_is_the_build_failing_call():
    """Verified fix for the book's assert_passed(): EvalResults.raise_for_status() -> EvalNotPassedError."""
    agent = _weather_agent([Reply.text("No idea.")])
    results = await evaluate_agent(agent=agent, queries=QUERIES, evaluators=LocalEvaluator(tool_called_check("get_weather")))
    for r in results:
        with pytest.raises(EvalNotPassedError, match="0 passed, 1 failed"):
            r.raise_for_status()
    good = await evaluate_agent(agent=_weather_agent(), queries=QUERIES,
                                evaluators=LocalEvaluator(tool_called_check("get_weather")))
    for r in good:
        r.raise_for_status()  # passes silently


async def test_17_08_evaluate_agent_accepts_existing_responses_instead_of_running_agent():
    agent = _weather_agent([Reply.text("Sunny and warm.")])
    resp = await agent.run("What's the weather?")
    n_requests = len(agent.client.requests)
    results = await evaluate_agent(agent=agent, responses=resp, queries="What's the weather?",
                                   evaluators=LocalEvaluator(keyword_check("sunny")))
    assert results[0].all_passed and len(agent.client.requests) == n_requests  # agent not re-run


async def test_17_08_responses_without_queries_is_rejected():
    agent = _weather_agent([Reply.text("Sunny.")])
    resp = await agent.run("q")
    with pytest.raises(ValueError, match="queries"):
        await evaluate_agent(agent=agent, responses=resp, evaluators=LocalEvaluator(keyword_check("x")))


# ------------------------------------------------------------------ LocalEvaluator / @evaluator prose
async def test_17_08_keyword_and_tool_called_checks_detect_failures():
    agent = _weather_agent([Reply.text("I do not know.")])
    results = await evaluate_agent(agent=agent, queries=QUERIES,
                                   evaluators=LocalEvaluator(keyword_check("sunny"), tool_called_check("get_weather")))
    r = results[0]
    assert (r.passed, r.failed, r.all_passed) == (0, 1, False)
    assert r.per_evaluator["keyword_check"]["failed"] == 1 and r.per_evaluator["tool_called"]["failed"] == 1


@pytest.mark.parametrize("ret,expected", [
    (True, True), (False, False), (0.5, True), (0.49, False), (1.0, True),
    ({"score": 0.9}, True), ({"score": 0.1}, False), ({"passed": True}, True),
])
async def test_17_08_evaluator_decorator_return_types(ret, expected):
    @evaluator
    def check(response: str):
        return ret

    results = await evaluate_agent(agent=_weather_agent([Reply.text("Sunny.")]), queries=["q"],
                                   evaluators=LocalEvaluator(check))
    assert results[0].all_passed is expected


async def test_17_08_evaluator_check_result_return():
    from agent_framework import CheckResult

    @evaluator(name="mine")
    def check(response: str):
        return CheckResult(passed=True, reason="because", check_name="mine")

    results = await evaluate_agent(agent=_weather_agent([Reply.text("x")]), queries=["q"], evaluators=LocalEvaluator(check))
    assert results[0].all_passed and "mine" in results[0].per_evaluator


async def test_17_08_evaluator_injects_by_parameter_name_documented_names():
    seen = {}

    @evaluator
    def check(query, response, expected_output, expected_tool_calls, conversation, tools, context):
        seen.update(query=query, response=response, expected_output=expected_output,
                    expected_tool_calls=expected_tool_calls, conversation=conversation, tools=tools, context=context)
        return True

    agent = _weather_agent()
    await evaluate_agent(
        agent=agent, queries=QUERIES, expected_output=["sunny"], context="ctx doc",
        expected_tool_calls=[[ExpectedToolCall("get_weather", {"city": "Seattle"})]],
        evaluators=LocalEvaluator(check))
    assert seen["query"] == QUERIES[0] and seen["response"] == "It is sunny in Seattle."
    assert seen["expected_output"] == "sunny" and seen["context"] == "ctx doc"
    assert seen["expected_tool_calls"][0].name == "get_weather"
    assert [t.name for t in seen["tools"]] == ["get_weather", "get_flight_price"]
    assert len(seen["conversation"]) >= 3


def test_17_08_book_parameter_name_expected_is_wrong_it_is_expected_output():
    """MISMATCH: book lists `expected` among injected parameter names."""
    with pytest.raises(TypeError, match="unknown required parameter"):
        @evaluator
        def bad(response: str, expected: str):
            return True

    @evaluator
    def good(response: str, expected_output: str):
        return True


async def test_17_08_async_evaluator_supported():
    @evaluator
    async def judge(query: str, response: str) -> float:
        return 0.9

    results = await evaluate_agent(agent=_weather_agent([Reply.text("x")]), queries=["q"], evaluators=LocalEvaluator(judge))
    assert results[0].all_passed


async def test_17_08_item_with_no_checks_fails_rather_than_vacuously_passing():
    results = await evaluate_agent(agent=_weather_agent([Reply.text("x")]), queries=["q"], evaluators=LocalEvaluator())
    assert results[0].all_passed is False


# ------------------------------------------------------------------ rubric gates
def _rubric_results(scores):
    items = []
    for i, s in enumerate(scores):
        dims = [RubricScore(id="general_quality", score=s, applicable=s is not None, weight=1, reason="r")]
        items.append(EvalItemResult(item_id=str(i), status="pass", scores=[
            EvalScoreResult(name="my_rubric", score=(s or 0) / 5, passed=True, dimensions=dims)]))
    return EvalResults(provider="Foundry", result_counts={"passed": len(items), "failed": 0}, items=items)


def test_17_08_rubric_gate_assert_dimension_score_at_least():
    """Book: assert_dimension_score_at_least("general_quality", min_score=3.0, evaluator=rubric_name)."""
    rubric_name = "my_rubric"
    _rubric_results([3, 4, 5]).assert_dimension_score_at_least("general_quality", min_score=3.0, evaluator=rubric_name)
    with pytest.raises(EvalNotPassedError, match="general_quality"):
        _rubric_results([3, 2, 5]).assert_dimension_score_at_least("general_quality", min_score=3.0, evaluator=rubric_name)
    # non-applicable dimensions are skipped by default, fail with require_applicable
    _rubric_results([None, 4]).assert_dimension_score_at_least("general_quality", min_score=3.0)
    with pytest.raises(EvalNotPassedError):
        _rubric_results([None, 4]).assert_dimension_score_at_least("general_quality", min_score=3.0, require_applicable=True)
    # other evaluator names are ignored
    _rubric_results([1]).assert_dimension_score_at_least("general_quality", min_score=3.0, evaluator="someone_else")


def test_17_08_all_passed_semantics():
    assert EvalResults(provider="x", result_counts={"passed": 2, "failed": 0}).all_passed
    assert not EvalResults(provider="x", result_counts={"passed": 2, "failed": 1}).all_passed
    assert not EvalResults(provider="x", result_counts={"passed": 2, "failed": 0, "errored": 1}).all_passed
    assert not EvalResults(provider="x", status="timeout", result_counts={"passed": 2, "failed": 0}).all_passed


# ------------------------------------------------------------------ Foundry evaluators: structure only
def test_17_08_foundry_evals_structure():
    from agent_framework.foundry import FoundryEvals, evaluate_traces

    params = inspect.signature(FoundryEvals.__init__).parameters
    assert {"client", "evaluators", "project_client", "model"} <= set(params)
    assert (FoundryEvals.RELEVANCE, FoundryEvals.TOOL_CALL_ACCURACY) == ("relevance", "tool_call_accuracy")
    # families named in the book
    for name in ("INTENT_RESOLUTION", "TASK_ADHERENCE", "TASK_COMPLETION", "TASK_NAVIGATION_EFFICIENCY",
                 "TOOL_CALL_ACCURACY", "TOOL_SELECTION", "TOOL_INPUT_ACCURACY", "TOOL_OUTPUT_UTILIZATION",
                 "TOOL_CALL_SUCCESS", "COHERENCE", "FLUENCY", "RELEVANCE", "GROUNDEDNESS", "RESPONSE_COMPLETENESS",
                 "SIMILARITY", "VIOLENCE", "SEXUAL", "SELF_HARM", "HATE_UNFAIRNESS"):
        assert hasattr(FoundryEvals, name), name
    tp = inspect.signature(evaluate_traces).parameters
    assert "response_ids" in tp and "agent_id" in tp  # 'by agent ID' / response_ids
    assert tp["model"].default is inspect.Parameter.empty  # NOTE: model is required, book snippet omits


def test_17_08_foundry_evals_constructs_offline_with_real_client_class():
    from agent_framework.foundry import FoundryChatClient, FoundryEvals
    from azure.identity import DefaultAzureCredential

    chat_client = FoundryChatClient(project_endpoint="https://example.services.ai.azure.com/api/projects/p",
                                    model="gpt-4o", credential=DefaultAzureCredential())
    ev = FoundryEvals(client=chat_client, evaluators=[FoundryEvals.RELEVANCE, FoundryEvals.TOOL_CALL_ACCURACY])
    assert ev is not None  # constructing does no I/O; .evaluate() would need the service (NEEDS_MODEL)


async def test_17_08_foundry_evals_can_be_mixed_with_local_in_one_call_shape():
    """evaluate_agent accepts a list of providers (LocalEvaluator + cloud); here two local ones stand in."""
    results = await evaluate_agent(
        agent=_weather_agent(), queries=QUERIES,
        evaluators=[LocalEvaluator(keyword_check("sunny")), LocalEvaluator(tool_called_check("get_weather"))])
    assert [r.all_passed for r in results] == [True, True]


# ------------------------------------------------------------------ 17.10 release-gate design (local-checks tier)
async def test_17_10_local_check_suite_for_scoring_assistant():
    calls = []

    @tool
    def score_business(business_id: str) -> str:
        """Score an AI-readiness assessment."""
        calls.append(business_id)
        return "score: 3 of 6; weakest area: data"

    @evaluator
    def never_scores_without_the_tool(response: str, conversation) -> bool:
        called = any(c.type == "function_call" and c.name == "score_business" for m in conversation for c in m.contents)
        return called or "score:" not in response.lower()

    good = Agent(client=ScriptedChatClient([Reply.tool_call("score_business", {"business_id": "b1"}),
                                            Reply.text("Your score: 3 of 6. Next steps: fix data.")]),
                 name="scorer", tools=[score_business])
    bad = Agent(client=ScriptedChatClient([Reply.text("Your score: 6 of 6.")]), name="scorer", tools=[score_business])
    suite = LocalEvaluator(tool_called_check("score_business"), keyword_check("next steps"), never_scores_without_the_tool)
    ok = await evaluate_agent(agent=good, queries=["We are a 5 person shop."], evaluators=suite)
    ko = await evaluate_agent(agent=bad, queries=["We are a 5 person shop."], evaluators=suite)
    ok[0].raise_for_status()
    assert calls == ["b1"]
    assert ko[0].failed == 1 and ko[0].per_evaluator["never_scores_without_the_tool"]["failed"] == 1
    with pytest.raises(EvalNotPassedError):
        ko[0].raise_for_status()


# ------------------------------------------------------------------ chapter_17_07 Purview
class _FakeTokenCredential:
    def get_token(self, *scopes, **kw):  # pragma: no cover - never called when processor is stubbed
        raise AssertionError("no network in tests")


def _purview_agent(client, block_prompt=False, block_response=False, settings_extra=None):
    from agent_framework.microsoft import PurviewPolicyMiddleware, PurviewSettings

    settings = PurviewSettings(app_name="Sample App", **(settings_extra or {}))
    mw = PurviewPolicyMiddleware(_FakeTokenCredential(), settings)

    async def process_messages(messages, activity, session_id=None, user_id=None):
        blocked = block_prompt if "upload" in str(activity).lower() else block_response
        return blocked, "user-1"

    mw._processor.process_messages = process_messages  # stub the Graph call only; middleware logic is real
    return Agent(client=client, name="Joker", middleware=[mw]), mw


async def test_17_07_book_snippet_constructs_with_default_blocked_prompt_message():
    from agent_framework.microsoft import PurviewPolicyMiddleware, PurviewSettings

    mw = PurviewPolicyMiddleware(_FakeTokenCredential(), PurviewSettings(app_name="Sample App"))
    assert mw is not None


async def test_17_07_blocked_prompt_never_reaches_the_model_and_default_message_is_returned():
    client = ScriptedChatClient([Reply.text("joke")])
    agent, _ = _purview_agent(client, block_prompt=True)
    result = await agent.run("my card is 4111 1111 1111 1111")
    assert result.text == "Prompt blocked by policy"
    assert client.requests == []  # model never invoked


async def test_17_07_blocked_prompt_message_is_configurable():
    client = ScriptedChatClient([Reply.text("joke")])
    agent, _ = _purview_agent(client, block_prompt=True, settings_extra={"blocked_prompt_message": "Nope."})
    assert (await agent.run("x")).text == "Nope."


async def test_17_07_allowed_prompt_flows_through():
    client = ScriptedChatClient([Reply.text("joke")])
    agent, _ = _purview_agent(client)
    assert (await agent.run("tell a joke")).text == "joke"
    assert len(client.requests) == 1


async def test_17_07_responses_can_be_evaluated_and_blocked_too():
    client = ScriptedChatClient([Reply.text("here is a secret card number")])
    agent, _ = _purview_agent(client, block_response=True)
    result = await agent.run("tell a joke")
    assert result.text == "Response blocked by policy"
    assert len(client.requests) == 1  # model WAS called; only the response was replaced


def test_17_07_chat_level_variant_and_cache_provider_exist():
    from agent_framework.microsoft import PurviewChatPolicyMiddleware, PurviewSettings

    assert PurviewChatPolicyMiddleware is not None
    sig = inspect.signature(PurviewChatPolicyMiddleware.__init__)
    assert "cache_provider" in sig.parameters


def test_17_07_default_protection_scope_cache_ttl_is_four_hours_not_thirty_minutes():
    """MISMATCH (minor): book 17.7 says a default thirty-minute TTL. InMemoryCacheProvider's own default is 1800 s
    but PurviewPolicyMiddleware always builds it with PurviewSettings' default of 14400 s (4 h)."""
    from agent_framework.microsoft import PurviewPolicyMiddleware, PurviewSettings

    mw = PurviewPolicyMiddleware(_FakeTokenCredential(), PurviewSettings(app_name="Sample App"))
    assert mw._processor._cache._default_ttl == 14400
    mw30 = PurviewPolicyMiddleware(_FakeTokenCredential(), PurviewSettings(app_name="x", cache_ttl_seconds=1800))
    assert mw30._processor._cache._default_ttl == 1800  # the 30-minute behaviour needs an explicit setting


# ------------------------------------------------------------------ 17.9 observability additions (structure only)
def test_17_09_observability_surface_exists():
    from agent_framework import observability as obs
    from agent_framework.foundry import FoundryAgent

    assert callable(obs.enable_sensitive_telemetry)
    assert hasattr(FoundryAgent, "configure_azure_monitor")
    params = inspect.signature(FoundryAgent.configure_azure_monitor).parameters
    assert "kwargs" in params  # enable_live_metrics is forwarded through **kwargs
    assert hasattr(obs, "configure_otel_providers")
