"""Offline tests for the ten afternoon agents (scripted model; the model's decisions are fixed, the code is real)."""
import json

import pytest

from afternoon import (app01_meeting_actions as a1, app02_folder_triage as a2, app03_pr_reviewer as a3,
                       app04_chat_with_a_folder as a4, app05_tool_call_bouncer as a5, app06_audit_log as a6,
                       app07_claim_check as a7, app08_inbox_to_tracker as a8, app09_budget_guard as a9,
                       app10_ticket_router as a10)
from afternoon.common import run_approved
from support.fake_client import Reply, ScriptedChatClient, flatten


def results_seen(client, request_index):
    return [v for (_r, t, v) in flatten(client.requests[request_index]) if t == "function_result"]


# 1 -------------------------------------------------------------------------------------------
@pytest.mark.parametrize("approved", [True, False])
async def test_01_nothing_is_written_unless_a_human_approves(tmp_path, approved):
    client = ScriptedChatClient([Reply.tool_call("save_actions", {"markdown": "- [Sam] deck"}), Reply.text("ok")])
    await run_approved(a1.build_agent(client, tmp_path), "notes", approve=lambda req: approved)
    assert (tmp_path / "actions.md").exists() is approved


# 2 -------------------------------------------------------------------------------------------
async def test_02_triage_is_confined_to_the_folder(tmp_path):
    root = tmp_path / "inbox"
    root.mkdir()
    (tmp_path / "secret.txt").write_text("top secret")
    (root / "a.txt").write_text("Invoice 1")
    answer = a2.Triage(files=[a2.FileTriage(name="a.txt", category="invoice", reason="x")])
    client = ScriptedChatClient([Reply.tool_call("read_file", {"name": "../secret.txt"}),
                                 Reply.tool_call("read_file", {"name": "a.txt"}), Reply.text(answer.model_dump_json())])
    result = await a2.build_agent(client, root).run("go")
    assert results_seen(client, 1)[0].startswith("Error: only files inside")
    assert "top secret" not in " ".join(results_seen(client, 2))
    assert result.value.files[0].category == "invoice"


# 3 -------------------------------------------------------------------------------------------
async def test_03_read_cap_is_enforced_by_the_tool(tmp_path):
    (tmp_path / "f.py").write_text("x = 1")
    calls = [Reply.tool_call("read_file", {"path": "f.py"}) for _ in range(3)]
    done = a3.Review(findings=[])
    client = ScriptedChatClient(calls + [Reply.text(done.model_dump_json())])
    await a3.build_agent(client, "diff", tmp_path, max_reads=2).run("review")
    last = results_seen(client, 3)
    assert last[0] == "x = 1" and last[1] == "x = 1" and last[2].startswith("Error")


# 4 -------------------------------------------------------------------------------------------
async def test_04_search_finds_lines_and_session_carries_history(tmp_path):
    (tmp_path / "n.txt").write_text("Budget approved: 40k.\nHiring freeze.")
    client = ScriptedChatClient([Reply.tool_call("search_notes", {"query": "budget"}), Reply.text("40k [n.txt]"), Reply.text("yes")])
    agent = a4.build_agent(client, tmp_path)
    session = agent.create_session()
    await agent.run("budget?", session=session)
    assert json.loads(results_seen(client, 1)[0]) == ["n.txt: Budget approved: 40k."]  # list results arrive as JSON text
    await agent.run("follow-up", session=session)
    assert any("budget?" in v for (_r, t, v) in flatten(client.requests[2]) if t == "text")  # history was sent again


# 5 -------------------------------------------------------------------------------------------
async def test_05_bouncer_blocks_and_tells_the_model_why():
    asked = []
    bouncer = a5.Bouncer(allow={"read_note", "run_shell"}, ask_human={"run_shell"},
                         approve=lambda n, a: asked.append((n, a)) or False)
    script = [Reply.tool_call("read_note", {"name": "../x"}), Reply.tool_call("run_shell", {"command": "ls"}),
              Reply.tool_call("read_note", {"name": "ok.txt"}), Reply.text("done")]
    client = ScriptedChatClient(script)
    await a5.build_agent(client, bouncer).run("go")
    assert "blocked pattern" in results_seen(client, 1)[0]
    assert "human reviewer declined" in results_seen(client, 2)[-1]
    assert results_seen(client, 3)[-1] == "(contents of ok.txt)"
    assert bouncer.log == [("read_note", "blocked"), ("run_shell", "blocked"), ("read_note", "allowed")]
    assert asked == [("run_shell", {"command": "ls"})]


async def test_05_unlisted_tool_is_denied_by_default():
    bouncer = a5.Bouncer(allow={"read_note"}, ask_human=set(), approve=lambda n, a: True)
    client = ScriptedChatClient([Reply.tool_call("run_shell", {"command": "ls"}), Reply.text("x")])
    await a5.build_agent(client, bouncer).run("go")
    assert "not on this agent's allow-list" in results_seen(client, 1)[0]


# 6 -------------------------------------------------------------------------------------------
async def test_06_audit_chain_detects_edits_and_deletions(tmp_path):
    log = tmp_path / "audit.jsonl"
    client = ScriptedChatClient([Reply.tool_call("lookup_price", {"item": "widget"}),
                                 Reply.tool_call("lookup_price", {"item": "gadget"}), Reply.text("done")])
    from agent_framework import Agent
    await Agent(client=client, instructions="x", tools=a6.lookup_price, middleware=[a6.AuditLog(log)]).run("go")
    assert a6.verify(log) == (True, None)
    entries = log.read_text().splitlines()
    assert json.loads(entries[0])["record"]["result"] == "4.50"
    log.write_text(log.read_text().replace("4.50", "0.50"))
    assert a6.verify(log) == (False, 0)
    log.write_text("\n".join(entries[1:]) + "\n")  # drop the first entry
    assert a6.verify(log)[0] is False


# 7 -------------------------------------------------------------------------------------------
async def test_07_false_claim_is_caught_and_retried(tmp_path):
    rec = a7.Recorder()
    client = ScriptedChatClient([Reply.text("I saved it."), Reply.tool_call("write_file", {"name": "n.txt", "content": "hi"}),
                                 Reply.text("Saved.")])
    result, caught = await a7.run_checked(a7.build_agent(client, tmp_path, rec), rec, "save hi")
    assert caught == 1 and (tmp_path / "n.txt").read_text() == "hi"


async def test_07_true_claim_is_not_challenged(tmp_path):
    rec = a7.Recorder()
    client = ScriptedChatClient([Reply.tool_call("write_file", {"name": "n.txt", "content": "hi"}), Reply.text("Saved n.txt.")])
    _, caught = await a7.run_checked(a7.build_agent(client, tmp_path, rec), rec, "save hi")
    assert caught == 0


async def test_07_gives_up_after_the_retry_limit(tmp_path):
    rec = a7.Recorder()
    client = ScriptedChatClient(lambda m: Reply.text("I saved it."))  # never actually calls the tool
    _, caught = await a7.run_checked(a7.build_agent(client, tmp_path, rec), rec, "save hi", retries=2)
    assert caught == 2 and not (tmp_path / "n.txt").exists()


# 8 -------------------------------------------------------------------------------------------
async def test_08_code_checks_the_file_not_the_model(tmp_path):
    path = tmp_path / "t.csv"
    emails = {"A": "do a", "B": "do b"}

    def row(s):
        return Reply.tool_call("add_row", {"sender": "x", "subject": s, "action": "do", "due": "none"})

    client = ScriptedChatClient([row("A"), Reply.text("Added both."), row("B"), Reply.text("Done.")])
    assert await a8.process(a8.build_agent(client, path), path, emails) == set()
    assert a8.subjects_in(path) == {"A", "B"}
    retry_prompt = [v for (_r, t, v) in flatten(client.requests[2]) if t == "text"][-1]
    assert retry_prompt == "These emails have no row yet: ['B']. Add them now."  # only the missing email is re-asked


async def test_08_reports_what_is_still_missing(tmp_path):
    path = tmp_path / "t.csv"
    client = ScriptedChatClient(lambda m: Reply.text("Added."))  # never writes a row
    assert await a8.process(a8.build_agent(client, path), path, {"A": "x"}, retries=1) == {"A"}


# 9 -------------------------------------------------------------------------------------------
async def test_09_budget_stops_a_looping_model():
    from agent_framework import Agent
    guard = a9.budget(max_calls=3)
    client = ScriptedChatClient(lambda m: Reply.tool_call("poll_status"))
    result = await Agent(client=client, instructions="x", tools=a9.poll_status, middleware=[guard]).run("go")
    assert guard.state["calls"] == 3 and len(client.requests) == 3
    assert "budget is used up" in result.text


# 10 ------------------------------------------------------------------------------------------
@pytest.mark.parametrize("answer, expected", [
    ('{"category": "billing", "urgency": "low"}', "billing team"),
    ('{"category": "technical", "urgency": "high"}', "on-call engineer"),
    ('{"category": "other", "urgency": "low"}', "human triage"),
    ("probably billing?", "human triage"),  # unparseable -> a person, never a guess
])
async def test_10_router(answer, expected):
    result = await a10.build_workflow(ScriptedChatClient([Reply.text(answer)])).run("ticket")
    outputs = result.get_outputs()
    assert len(outputs) == 1 and expected in outputs[0]
