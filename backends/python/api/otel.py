import logging

_INITIALIZED = False


def get_current_trace_id() -> str:
    """Return the current OTel trace_id as a 32-char hex string, or '' if unavailable."""
    try:
        from opentelemetry import trace
        ctx = trace.get_current_span().get_span_context()
        if ctx and ctx.is_valid:
            return format(ctx.trace_id, "032x")
    except Exception:
        pass
    return ""


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
    log = logging.getLogger(__name__)

    # ── Traces ────────────────────────────────────────────────────────────────
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

        log.info("OpenTelemetry traces initialized: service=%s endpoint=%s", service_name, endpoint)
    except Exception as exc:
        log.warning("OpenTelemetry traces setup failed: %s", exc)
        resource = None

    # ── Logs ──────────────────────────────────────────────────────────────────
    try:
        from opentelemetry.sdk.resources import Resource as _Resource

        _resource = resource if resource is not None else _Resource({"service.name": service_name})

        try:
            from opentelemetry.sdk.logs import LoggerProvider
            from opentelemetry.sdk.logs.export import BatchLogRecordProcessor
        except ImportError:
            from opentelemetry.sdk._logs import LoggerProvider
            from opentelemetry.sdk._logs.export import BatchLogRecordProcessor

        try:
            from opentelemetry.exporter.otlp.proto.http.log_exporter import OTLPLogExporter
        except ImportError:
            from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter

        try:
            from opentelemetry._logs import set_logger_provider
        except ImportError:
            from opentelemetry.sdk._logs import set_logger_provider

        logger_provider = LoggerProvider(resource=_resource)
        logger_provider.add_log_record_processor(
            BatchLogRecordProcessor(OTLPLogExporter(endpoint=f"{endpoint.rstrip('/')}/v1/logs"))
        )
        set_logger_provider(logger_provider)

        from opentelemetry.instrumentation.logging import LoggingInstrumentor
        try:
            LoggingInstrumentor().instrument(set_logging_format=True, logger_provider=logger_provider)
        except TypeError:
            LoggingInstrumentor().instrument(set_logging_format=True)

        log.info("OpenTelemetry logs initialized: service=%s endpoint=%s", service_name, endpoint)
    except Exception as exc:
        log.warning("OpenTelemetry logs setup failed: %s", exc)
