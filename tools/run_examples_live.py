"""Runs every example against a real OpenAI-compatible model and writes LIVE_RESULTS.md.

Usage (after starting any OpenAI-compatible server, e.g. llama.cpp's llama-server, LM Studio or Ollama):
    BOOK_BASE_URL=http://127.0.0.1:8081/v1 BOOK_MODEL=qwen3:8b python tools/run_examples_live.py

Each example is run as a subprocess with BOOK_CLIENT=openai-compatible. The report records the exit
code, the time taken, and the tail of the output, so you can see what a real model actually did.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TIMEOUT = int(os.environ.get("EXAMPLE_TIMEOUT", "240"))


def write_report(env, rows, details) -> None:
    nl = "\n"
    report = (
        f"# Live run against `{env['BOOK_MODEL']}` at `{env['BOOK_BASE_URL']}`" + nl + nl
        + "A real model makes its own decisions, so output differs from the scripted runs and can vary between runs." + nl + nl
        + "| Example | Result | Time |" + nl + "|---|---|---|" + nl
        + nl.join(rows) + nl + nl + nl.join(details)
    )
    (ROOT / "LIVE_RESULTS.md").write_text(report, encoding="utf-8")


def main() -> int:
    env = dict(os.environ, BOOK_CLIENT="openai-compatible", PYTHONIOENCODING="utf-8")
    for key in ("BOOK_BASE_URL", "BOOK_MODEL"):
        if key not in env:
            print(f"Set {key} first.")
            return 2
    only = sys.argv[1:]
    files = sorted(p for p in (ROOT / "examples").rglob("*.py") if not only or any(o in str(p) for o in only))
    rows, details = [], []
    for p in files:
        rel = p.relative_to(ROOT).as_posix()
        t0 = time.time()
        try:
            r = subprocess.run([sys.executable, str(p)], capture_output=True, text=True, timeout=TIMEOUT, env=env, cwd=ROOT, encoding="utf-8", errors="replace")
            code, out = r.returncode, (r.stdout + ("\n[stderr]\n" + r.stderr if r.returncode else ""))
        except subprocess.TimeoutExpired as e:
            code, out = "TIMEOUT", (e.stdout or "")[-1500:] if isinstance(e.stdout, str) else ""
        dt = time.time() - t0
        status = "ok" if code == 0 else f"FAIL ({code})"
        rows.append(f"| `{rel}` | {status} | {dt:.0f}s |")
        details.append(f"### {rel}  ({status}, {dt:.0f}s)\n```text\n{out.strip()[-1800:]}\n```\n")
        print(f"{status:12} {dt:5.0f}s  {rel}", flush=True)
        write_report(env, rows, details)  # save after every example so progress is visible
    write_report(env, rows, details)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
