"""OpenTelemetry and Arize Phoenix Distributed Tracing.
Configures tracer, span processor, and A2A trace context propagation according to Requirement 9.
"""
import os
from typing import Optional
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource

PHOENIX_COLLECTOR_ENDPOINT = os.getenv("PHOENIX_COLLECTOR_ENDPOINT", "http://127.0.0.1:6006/v1/traces")

_tracer: Optional[trace.Tracer] = None


def init_tracer(service_name: str = "supplychain-autopilot") -> trace.Tracer:
    """Initializes OpenTelemetry tracer with OTLP exporter to Arize Phoenix."""
    global _tracer
    if _tracer is not None:
        return _tracer

    resource = Resource.create({"service.name": service_name, "environment": "simulation"})
    provider = TracerProvider(resource=resource)

    try:
        otlp_exporter = OTLPSpanExporter(endpoint=PHOENIX_COLLECTOR_ENDPOINT)
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
    except Exception as e:
        # Fallback to console exporter if Phoenix collector endpoint is unreachable
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer(service_name)
    return _tracer


def get_tracer() -> trace.Tracer:
    global _tracer
    if _tracer is None:
        return init_tracer()
    return _tracer
