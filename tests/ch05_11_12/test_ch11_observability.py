"""Chapter 11 - Observability. Uses OpenTelemetry's in-memory span exporter (no network)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
from agent_framework import Agent, tool
from agent_framework.observability import OBSERVABILITY_SETTINGS, configure_otel_providers
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from support.fake_client import Reply, ScriptedChatClient
from tests.ch05_11_12.helpers import UsageScriptedClient

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def exporter():
    # Chapter 11.1: configure_otel_providers(...) is the one call the reader makes. We hand it nothing but an
    # in-memory exporter so nothing leaves the process.
    exp = InMemorySpanExporter()
    configure_otel_providers(exporters=[exp])
    provider = trace.get_tracer_provider()
    if not isinstance(provider, TracerProvider):  # another test module won the global race: attach anyway
        pytest.skip("global tracer provider is not the SDK provider")
    provider.add_span_processor(SimpleSpanProcessor(InMemorySpanExporter()))  # keep API symmetrical
    sync = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(sync))
    return sync


@pytest.fixture(autouse=True)
def _reset(exporter):
    exporter.clear()
    yield
    OBSERVABILITY_SETTINGS.enable_sensitive_data = False


@tool
def get_weather(city: str) -> str:
    """Get the weather for a city."""
    return f"Sunny in {city}"


async def _run_weather(client=None):
    client = client or ScriptedChatClient([Reply.tool_call("get_weather", {"city": "Seattle"}), Reply.text("Sunny.")])
    agent = Agent(client=client, name="WeatherAgent", instructions="be brief", tools=get_weather)
    return await agent.run("Weather in Seattle? my secret is hunter2")


# ---------------------------------------------------------------- 11.1 ----
def test_11_1_instrumentation_enabled_by_default_and_sensitive_off():
    assert OBSERVABILITY_SETTINGS.enable_instrumentation is True
    assert OBSERVABILITY_SETTINGS.enable_sensitive_data is False


async def test_11_1_spans_for_agent_model_and_tool(exporter):
    await _run_weather()
    spans = exporter.get_finished_spans()
    by_op = {}
    for s in spans:
        by_op.setdefault(s.attributes.get("gen_ai.operation.name"), []).append(s)
    # "emit ... traces throughout agent invocation, model calls, and tool execution"
    assert len(by_op["invoke_agent"]) == 1
    assert len(by_op["chat"]) == 2  # tool-call turn + final answer
    assert len(by_op["execute_tool"]) == 1
    agent_span = by_op["invoke_agent"][0]
    assert agent_span.name == "invoke_agent WeatherAgent"
    assert agent_span.attributes["gen_ai.agent.name"] == "WeatherAgent"
    tool_span = by_op["execute_tool"][0]
    assert tool_span.attributes["gen_ai.tool.name"] == "get_weather"
    # "a trace spans not just one agent call but the whole graph": single trace, children under agent span
    assert {s.context.trace_id for s in spans} == {agent_span.context.trace_id}
    for child in by_op["chat"] + by_op["execute_tool"]:
        assert child.parent.span_id == agent_span.context.span_id
    # timing is present ("shape and timing")
    assert all(s.end_time > s.start_time for s in spans)


async def test_11_1_genai_semantic_convention_attribute_names(exporter):
    await _run_weather()
    chat = next(s for s in exporter.get_finished_spans() if s.attributes.get("gen_ai.operation.name") == "chat")
    for key in ("gen_ai.operation.name", "gen_ai.provider.name", "gen_ai.request.model"):
        assert key in chat.attributes, key


async def test_11_1_default_traces_carry_no_conversation_content(exporter):
    await _run_weather()
    blob = json.dumps({s.name: {k: str(v) for k, v in s.attributes.items()} for s in exporter.get_finished_spans()})
    assert "hunter2" not in blob
    assert "gen_ai.input.messages" not in blob and "gen_ai.output.messages" not in blob


async def test_11_1_enable_sensitive_data_puts_content_in_traces(exporter):
    OBSERVABILITY_SETTINGS.enable_sensitive_data = True
    await _run_weather()
    blob = json.dumps({s.name: {k: str(v) for k, v in s.attributes.items()} for s in exporter.get_finished_spans()})
    assert "hunter2" in blob
    assert "gen_ai.input.messages" in blob


async def test_11_2_token_usage_recorded_on_span(exporter):
    """11.2: cost/usage is read from the same GenAI instrumentation (usage_details -> span attributes)."""
    await _run_weather(UsageScriptedClient([Reply.text("hi")]))
    chat = next(s for s in exporter.get_finished_spans() if s.attributes.get("gen_ai.operation.name") == "chat")
    assert chat.attributes["gen_ai.usage.input_tokens"] == 11
    assert chat.attributes["gen_ai.usage.output_tokens"] == 7


async def test_11_2_failing_tool_span_marked_error(exporter):
    """11.2: 'which tool is failing' is answerable from span status."""

    @tool
    def boom(x: str) -> str:
        """Always fails."""
        raise RuntimeError("kaput")

    client = ScriptedChatClient([Reply.tool_call("boom", {"x": "1"}), Reply.text("sorry")])
    await Agent(client=client, name="A", instructions="i", tools=boom).run("go")
    tool_span = next(s for s in exporter.get_finished_spans() if s.attributes.get("gen_ai.operation.name") == "execute_tool")
    assert tool_span.status.status_code == trace.StatusCode.ERROR


# ---- configuration forms in the snippet (chapter_11_01) run in isolated subprocesses ----
def _run_py(code: str, env_extra: dict[str, str] | None = None, timeout=60):
    env = {**os.environ, "PYTHONPATH": str(ROOT), "PYTHONWARNINGS": "ignore"}
    for k in list(env):
        if k.startswith("OTEL_") or k in ("ENABLE_INSTRUMENTATION", "ENABLE_SENSITIVE_DATA"):
            env.pop(k)
    env.update(env_extra or {})
    return subprocess.run([sys.executable, "-W", "ignore", "-c", textwrap.dedent(code)], capture_output=True, text=True, env=env, timeout=timeout, cwd=ROOT)


def _join(*parts: str) -> str:
    return chr(10).join(textwrap.dedent(p) for p in parts)


AGENT_RUN = """
import asyncio
from agent_framework import Agent
from support.fake_client import Reply, ScriptedChatClient
async def main():
    await Agent(client=ScriptedChatClient([Reply.text("hi")]), name="A", instructions="i").run("x")
asyncio.run(main())
"""


def test_11_1_snippet_no_args_reads_otlp_env_vars():
    code = """
    from agent_framework.observability import configure_otel_providers
    configure_otel_providers()
    from opentelemetry import trace
    p = trace.get_tracer_provider()
    procs = p._active_span_processor._span_processors
    print("EXPORTERS", [type(pr.span_exporter).__name__ for pr in procs])
    """
    r = _run_py(code, {"OTEL_EXPORTER_OTLP_ENDPOINT": "http://127.0.0.1:9", "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf"})
    assert r.returncode == 0, r.stderr
    assert "OTLPSpanExporter" in r.stdout, r.stdout


def test_11_1_snippet_no_args_without_env_is_harmless():
    r = _run_py("from agent_framework.observability import configure_otel_providers\nconfigure_otel_providers()\nprint('OK')")
    assert r.returncode == 0 and "OK" in r.stdout, r.stderr


def test_11_1_snippet_console_exporters_print_spans():
    code = """
    from agent_framework.observability import configure_otel_providers
    configure_otel_providers(enable_console_exporters=True)
    """
    r = _run_py(_join(code, AGENT_RUN))
    assert r.returncode == 0, r.stderr
    assert "invoke_agent A" in r.stdout
    assert '"gen_ai.operation.name": "chat"' in r.stdout


def test_11_2_genai_metrics_emitted_for_token_usage():
    code = """
    import asyncio
    from opentelemetry.sdk.metrics.export import MetricExporter, MetricExportResult
    from opentelemetry.sdk.metrics.export import AggregationTemporality
    from agent_framework.observability import configure_otel_providers
    from opentelemetry import metrics
    seen = []
    class Mem(MetricExporter):
        def __init__(self): super().__init__(preferred_temporality={}, preferred_aggregation={})
        def export(self, metrics_data, timeout_millis=10000, **kw):
            for rm in metrics_data.resource_metrics:
                for sm in rm.scope_metrics:
                    for m in sm.metrics: seen.append(m.name)
            return MetricExportResult.SUCCESS
        def force_flush(self, timeout_millis=10000): return True
        def shutdown(self, timeout_millis=30000, **kw): pass
    configure_otel_providers(exporters=[Mem()])
    from agent_framework import Agent
    from tests.ch05_11_12.helpers import UsageScriptedClient
    from support.fake_client import Reply
    async def main():
        await Agent(client=UsageScriptedClient([Reply.text("hi")]), name="A", instructions="i").run("x")
    asyncio.run(main())
    metrics.get_meter_provider().force_flush()
    print("METRICS", sorted(set(seen)))
    """
    r = _run_py(code)
    assert r.returncode == 0, r.stderr
    assert "gen_ai.client.token.usage" in r.stdout, r.stdout + r.stderr
    assert "gen_ai.client.operation.duration" in r.stdout


# ---------------------------------------------------------------- 11.3 / 11.4 ----
def test_11_3_workflow_visualization_surface_exists():
    from agent_framework import WorkflowViz  # graphviz export mentioned in 11.3 / 6.5

    assert hasattr(WorkflowViz, "to_mermaid") or hasattr(WorkflowViz, "export")


def test_11_4_logs_pipeline_configured_by_same_call():
    code = """
    import logging
    from agent_framework.observability import configure_otel_providers
    configure_otel_providers(enable_console_exporters=True)
    from opentelemetry._logs import get_logger_provider
    print("LOGPROV", type(get_logger_provider()).__name__)
    """
    r = _run_py(code)
    assert "LOGPROV LoggerProvider" in r.stdout, r.stdout + r.stderr
