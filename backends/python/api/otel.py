import logging

_INITIALIZED = False


def setup_otel() -> None:
    global _INITIALIZED
    if _INITIALIZED:
        return

    from config import config
    if not getattr(config, "otel_enabled", False):
        return

    endpoint = (config.otel_endpoint or "").strip()
    if not endpoint:
        return
    _INITIALIZED = True

    service_name = config.otel_service_name or "excel-migration-api"

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource({"service.name": service_name})
        tracer_provider = TracerProvider(resource=resource)
        tracer_provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{endpoint.rstrip('/')}/v1/traces"))
        )
        trace.set_tracer_provider(tracer_provider)

        from opentelemetry.instrumentation.django import DjangoInstrumentor
        DjangoInstrumentor().instrument()

        from opentelemetry.instrumentation.logging import LoggingInstrumentor
        LoggingInstrumentor().instrument(set_logging_format=True)

        logging.getLogger(__name__).info(
            "OpenTelemetry initialized: service=%s endpoint=%s", service_name, endpoint
        )
    except Exception as exc:
        logging.getLogger(__name__).warning("OpenTelemetry setup failed: %s", exc)
