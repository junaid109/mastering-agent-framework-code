# Ten Afternoon Agents

Chapter 19 of *Mastering Microsoft Agent Framework*. Each file is a complete agent under seventy lines with one idea worth stealing.

| File | Idea |
|---|---|
| `app01_meeting_actions.py` | Gate the one irreversible tool behind human approval |
| `app02_folder_triage.py` | Read-only tools confined to a folder; typed output |
| `app03_pr_reviewer.py` | A hard read budget on the tool (`max_invocations`) |
| `app04_chat_with_a_folder.py` | Keyword search, citations, follow-ups through a session |
| `app05_tool_call_bouncer.py` | Deny-by-default middleware that explains every refusal |
| `app06_audit_log.py` | Hash-chained, tamper-evident log of every tool call |
| `app07_claim_check.py` | Check "I saved it" against what actually ran, and retry |
| `app08_inbox_to_tracker.py` | The code, not the model, verifies batch output |
| `app09_budget_guard.py` | Chat middleware that caps model calls |
| `app10_ticket_router.py` | Workflow routing that fails toward a human |

Run one: `python -m afternoon.app05_tool_call_bouncer` (uses a scripted stand-in model, so it works offline).
Run against a real or local model: set `BOOK_CLIENT=openai-compatible`, `BOOK_BASE_URL`, `BOOK_MODEL`.
Tests: `pytest tests/afternoon_agents`.
