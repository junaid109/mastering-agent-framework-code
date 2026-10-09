"""Chapter 10.1: a FastAPI route hosting an Agent through the Responses protocol.

Fills in the book's `...` body using agent-framework-hosting-responses + agent-framework-hosting.
Run: python examples/ch09_10_app/fastapi_responses.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from agent_framework import Agent
from agent_framework_hosting import AgentState
from agent_framework_hosting_responses import (
    create_response_id,
    responses_from_run,
    responses_session_id,
    responses_to_run,
)
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from support.fake_client import Reply, ScriptedChatClient


def make_client():
    if os.environ.get("BOOK_CLIENT") == "openai-compatible":
        from agent_framework.openai import OpenAIChatCompletionClient

        return OpenAIChatCompletionClient(
            base_url=os.environ["BOOK_BASE_URL"],
            api_key=os.environ.get("BOOK_API_KEY", "not-needed"),
            model=os.environ["BOOK_MODEL"],
        )
    return ScriptedChatClient([Reply.text("Paris."), Reply.text("It is the capital of France.")])


def build_app(client=None) -> FastAPI:
    agent = Agent(client=client or make_client(), name="Geo", instructions="Answer briefly.")
    state = AgentState(agent)
    app = FastAPI()
    app.state.agent_state = state

    @app.post("/responses", response_model=None)
    async def responses(request: Request) -> Response:
        body = await request.json()
        try:
            session_id, _is_conversation = responses_session_id(body)
            run_args = responses_to_run(body)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        # session_id came from the client: authorize the caller here before trusting it.
        new_id = session_id or f"conv_{uuid.uuid4().hex}"
        session = await state.get_or_create_session(new_id)
        target = await state.get_target()
        result = await target.run(run_args["messages"], session=session)
        await state.set_session(new_id, session)
        payload = responses_from_run(result, response_id=create_response_id(), conversation_id=new_id)
        return JSONResponse(payload)

    return app


async def main() -> None:
    import httpx

    app = build_app()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as http:
        r = await http.post("/responses", json={"input": "Capital of France?"})
        print(r.status_code, r.json()["output"][0]["content"][0]["text"])


if __name__ == "__main__":
    asyncio.run(main())
