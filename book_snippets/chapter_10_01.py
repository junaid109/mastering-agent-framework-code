# from 05-part-4-language-specific\chapter-10-python-ecosystem.md:9
from fastapi import FastAPI

app = FastAPI()

@app.post("/responses", response_model=None)
async def responses(request: Request) -> Response:
    ...  # agent-framework-hosting-responses converts the payload to/from a run
