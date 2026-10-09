"""Ch 11.1: OpenTelemetry tracing is on by default; you only choose the exporter (snippet chapter_11_01).

Uses an in-memory span exporter, so nothing leaves the process. Swap `exporters=[...]` for
`configure_otel_providers()` (reads OTEL_EXPORTER_OTLP_* env vars) or
`configure_otel_providers(enable_console_exporters=True)` in real use.
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root, for support.fake_client

from agent_framework import Agent, tool
from agent_framework.observability import OBSERVABILITY_SETTINGS, configure_otel_providers
from opentelemetry import trace
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from support.fake_client import Reply, ScriptedChatClient


def make_client(script):
    """Offline ScriptedChatClient by default; set BOOK_CLIENT=openai-compatible for a real endpoint."""
    if os.environ.get("BOOK_CLIENT") == "openai-compatible":
        from agent_framework.openai import OpenAIChatCompletionClient

        return OpenAIChatCompletionClient(
            base_url=os.environ["BOOK_BASE_URL"],
            api_key=os.environ.get("BOOK_API_KEY", "not-needed"),
            model=os.environ["BOOK_MODEL"],
        )
    return ScriptedChatClient(script)


@tool
def get_weather(city: str) -> str:
    """Get the weather for a city."""
    return f"Sunny in {city}"


async def main():
    exporter = InMemorySpanExporter()
    configure_otel_providers(exporters=[exporter])
    print("instrumentation on by default:", OBSERVABILITY_SETTINGS.enable_instrumentation)
    print("sensitive data captured by default:", OBSERVABILITY_SETTINGS.enable_sensitive_data)

    agent = Agent(
        client=make_client([Reply.tool_call("get_weather", {"city": "Seattle"}), Reply.text("Sunny.")]),
        name="WeatherAgent", instructions="Be brief.", tools=get_weather,
    )
    await agent.run("Weather in Seattle? (my secret is hunter2)")

    trace.get_tracer_provider().force_flush()
    spans = sorted(exporter.get_finished_spans(), key=lambda s: s.start_time)
    for s in spans:
        a = s.attributes
        print(f"{s.name:<28} op={a.get('gen_ai.operation.name'):<13} parent={'-' if s.parent is None else 'agent'}"
              f" tool={a.get('gen_ai.tool.name', '-')}")
    leaked = any("hunter2" in str(v) for s in spans for v in s.attributes.values())
    print("prompt content present in spans (should be False):", leaked)


if __name__ == "__main__":
    asyncio.run(main())
