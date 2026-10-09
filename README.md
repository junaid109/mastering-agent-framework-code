# Mastering Microsoft Agent Framework: companion code

Runnable examples and an offline test suite for the book **Mastering Microsoft Agent Framework: The Definitive Guide** by Junaid Malik.

Tested against **Microsoft Agent Framework Python 1.21.0** and **.NET 1.24.0** (October 2026).

> An independent project, not affiliated with or endorsed by Microsoft. Code adapted from
> [microsoft/agent-framework](https://github.com/microsoft/agent-framework) (MIT) is credited in [NOTICE](NOTICE).

## What is here

| Folder | What it holds |
|---|---|
| `examples/` | 26 small, runnable programs grouped by chapter. Each runs offline in seconds. |
| `tests/` | The test suite: **422 passing**, 5 skipped. Each chapter group has a `RESULTS.md` listing every book snippet and its status. |
| `support/fake_client.py` | A scripted chat client used by the tests and examples (see below). |
| `dotnet/` | C# projects: each book snippet compiled and, where possible, run offline; plus 14 official samples built against the 1.24.0 NuGet packages. See `dotnet/RESULTS.md`. |
| `book_snippets/` | Every Python code block in the book, extracted verbatim (the first line says where it came from), for reference. |

## Run it

```bash
python -m venv .venv
.venv/Scripts/activate        # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
pytest                        # offline, ~20 seconds
python examples/ch02_04/01_hello_and_streaming.py
```

Python 3.10 or newer. `requirements-lock.txt` is the exact environment the tests passed in.

For .NET: `cd dotnet/<project> && dotnet run` (SDK 10 was used).

## Why a scripted model?

Most agent code is plumbing around a model call: tools, middleware, sessions, workflows, approvals, checkpoints, hosting, security switches. All of that is deterministic and testable without a live model, so the tests use a *scripted* chat client built from the same layers as the framework's real clients (function invocation, middleware, telemetry). Only the model's *decisions* are scripted, for example "call `get_weather` with Seattle, then answer".

**What this proves:** the code runs, the calls and parameters exist in the released packages, and the behaviours the book describes are true of them.

**What it does not prove:** how a real model behaves, or anything that needs a live service (Azure AI Search, Redis, Foundry, Purview). Those are marked `NEEDS_MODEL` in the `RESULTS.md` files.

## Run an example against a real model

Every example picks its client with a small `make_client()` function. By default it returns the scripted client. To use any OpenAI-compatible server (a hosted API, LM Studio, Ollama, llama.cpp, vLLM and so on):

```bash
export BOOK_CLIENT=openai-compatible
export BOOK_BASE_URL=http://localhost:1234/v1
export BOOK_MODEL=<your-model-name>
export BOOK_API_KEY=not-needed        # or your key
python examples/ch02_04/01_hello_and_streaming.py
```

Never commit keys. `.env` files are git-ignored.

## What testing found

Running the book's code against the real packages found and fixed more than thirty errors in the book's text and snippets: missing imports, parameter names that do not exist, behaviour that changed in the October releases (for example tool approvals now require a session), and defaults the prose described wrongly. Those corrections are in the book and the per-chapter `RESULTS.md` files record each one with the verified fix.

## License

MIT, see [LICENSE](LICENSE) and [NOTICE](NOTICE).
