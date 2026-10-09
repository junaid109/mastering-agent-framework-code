"""Runs the ten afternoon agents against a real OpenAI-compatible model and writes AFTERNOON_LIVE_RESULTS.md.

Usage:
    BOOK_BASE_URL=http://127.0.0.1:8081/v1 BOOK_MODEL=qwen3:8b python tools/run_afternoon_live.py
The scripted answers are ignored in this mode: the model decides for itself, so results vary between runs.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TIMEOUT = int(os.environ.get("EXAMPLE_TIMEOUT", "900"))


def main() -> int:
    env = dict(os.environ, BOOK_CLIENT="openai-compatible", PYTHONIOENCODING="utf-8")
    for key in ("BOOK_BASE_URL", "BOOK_MODEL"):
        if key not in env:
            print(f"Set {key} first.")
            return 2
    nl = "\n"
    rows, details = [], []
    for p in sorted((ROOT / "afternoon").glob("app*.py")):
        module = f"afternoon.{p.stem}"
        t0 = time.time()
        try:
            r = subprocess.run([sys.executable, "-m", module], capture_output=True, text=True, timeout=TIMEOUT,
                               env=env, cwd=ROOT, encoding="utf-8", errors="replace")
            code, out = r.returncode, r.stdout + (nl + "[stderr]" + nl + r.stderr[-1500:] if r.returncode else "")
        except subprocess.TimeoutExpired as e:
            code, out = "TIMEOUT", (e.stdout or "")[-1500:] if isinstance(e.stdout, str) else ""
        dt = time.time() - t0
        status = "ran" if code == 0 else f"FAIL ({code})"
        rows.append(f"| `{p.name}` | {status} | {dt:.0f}s |")
        details.append(f"### {p.name}  ({status}, {dt:.0f}s){nl}```text{nl}{out.strip()[-1800:]}{nl}```{nl}")
        print(f"{status:12} {dt:5.0f}s  {p.name}", flush=True)
        report = (f"# Afternoon agents against `{env['BOOK_MODEL']}` at `{env['BOOK_BASE_URL']}`" + nl + nl
                  + "A real model makes its own decisions, so output differs from the scripted runs. 'ran' means the program finished without an error, not that the model did the right thing; read the output." + nl + nl
                  + "| Agent | Result | Time |" + nl + "|---|---|---|" + nl + nl.join(rows) + nl + nl + nl.join(details))
        (ROOT / "AFTERNOON_LIVE_RESULTS.md").write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
