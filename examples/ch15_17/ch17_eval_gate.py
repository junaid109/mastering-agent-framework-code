"""Chapter 17.8 / 17.10 - an offline release gate: LocalEvaluator checks, @evaluator, and a rubric gate.

Corrects the book: EvalResults has raise_for_status(), not assert_passed(); the @evaluator parameter is
`expected_output`, not `expected`.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from agent_framework import (  # noqa: E402
    Agent, EvalItemResult, EvalNotPassedError, EvalResults, EvalScoreResult, LocalEvaluator, RubricScore,
    evaluate_agent, evaluator, keyword_check, tool, tool_called_check,
)


def make_client(script=None):
    if os.environ.get("BOOK_CLIENT") == "openai-compatible":
        from agent_framework.openai import OpenAIChatCompletionClient

        return OpenAIChatCompletionClient(base_url=os.environ["BOOK_BASE_URL"],
                                          api_key=os.environ.get("BOOK_API_KEY", "not-needed"),
                                          model=os.environ["BOOK_MODEL"])
    from support.fake_client import ScriptedChatClient

    return ScriptedChatClient(script or [])


@tool
def score_business(business_id: str) -> str:
    """Call the scoring service for an AI-readiness assessment."""
    return "score 3 of 6; weakest area: data"


@evaluator
def never_scores_without_the_tool(response: str, conversation) -> bool:
    called = any(c.type == "function_call" and c.name == "score_business" for m in conversation for c in m.contents)
    return called or "score" not in response.lower()


SUITE = LocalEvaluator(tool_called_check("score_business"), keyword_check("next steps"), never_scores_without_the_tool)


async def run_suite(label, replies):
    agent = Agent(client=make_client(replies), name="assessor", tools=[score_business])
    (result,) = await evaluate_agent(agent=agent, queries=["We are a five person shop."], evaluators=SUITE)
    print(f"{label:9} {result.passed}/{result.total} passed, per check: "
          f"{ {k: v['passed'] for k, v in result.per_evaluator.items()} }")
    try:
        result.raise_for_status()                 # the build-failing call (the book's assert_passed())
        print("          gate: OPEN")
    except EvalNotPassedError as e:
        print("          gate: CLOSED -", str(e)[:70])


def rubric_gate():
    dims = lambda s: [RubricScore(id="general_quality", score=s, applicable=True, weight=1, reason="")]  # noqa: E731
    items = [EvalItemResult(item_id=str(i), status="pass",
                            scores=[EvalScoreResult(name="rubric", score=s / 5, dimensions=dims(s))])
             for i, s in enumerate([4, 5, 2])]
    results = EvalResults(provider="Foundry", result_counts={"passed": 3, "failed": 0}, items=items)
    try:
        results.assert_dimension_score_at_least("general_quality", min_score=3.0, evaluator="rubric")
    except EvalNotPassedError as e:
        print("rubric gate CLOSED -", e)


async def main():
    from support.fake_client import Reply

    await run_suite("good", [Reply.tool_call("score_business", {"business_id": "b1"}),
                             Reply.text("Your score is 3 of 6. Next steps: fix your data.")])
    await run_suite("bad", [Reply.text("Your score is 6 of 6.")])
    rubric_gate()


if __name__ == "__main__":
    asyncio.run(main())
