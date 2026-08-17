"""OpenTelemetry setup for the Notification service."""

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

_SERVICE_NAME = "notification-api"
_TRACER_NAME = "notification-api"


def init_tracing():
    """Initialize OTLP tracing once per Notification process."""
    if isinstance(trace.get_tracer_provider(), TracerProvider):
        return

    resource = Resource.create(
        {
            "service.name": _SERVICE_NAME,
        }
    )

    provider = TracerProvider(resource=resource)

    exporter = OTLPSpanExporter(
        endpoint="http://otel-collector:4318/v1/traces"
    )

    provider.add_span_processor(
        BatchSpanProcessor(exporter)
    )

    trace.set_tracer_provider(provider)


def get_tracer():
    """Return the tracer used by Notification application instrumentation."""
    return trace.get_tracer(_TRACER_NAME)
