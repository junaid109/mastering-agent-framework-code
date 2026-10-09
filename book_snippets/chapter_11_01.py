# from 06-part-5-enterprise\chapter-11-observability-and-monitoring.md:9
from agent_framework.observability import configure_otel_providers

# Reads OTEL_EXPORTER_OTLP_* environment variables automatically
configure_otel_providers()

# Or, for local development with no backend set up yet:
configure_otel_providers(enable_console_exporters=True)
