import logging
import time

from flask import g, request
from opentelemetry import trace

from telemetry.telemetry import get_http_metrics


logger = logging.getLogger("notification-api")


def register_logging(app):

    @app.before_request
    def before_request():
        g.start_time = time.perf_counter()

    @app.after_request
    def after_request(response):
        start_time = getattr(g, "start_time", time.perf_counter())
        latency_ms = round(
            (time.perf_counter() - start_time) * 1000,
            2,
        )

        # Prefer the Flask route template over the raw URL so metric
        # cardinality remains bounded.
        route = request.url_rule.rule if request.url_rule else request.path

        span = trace.get_current_span()
        span_context = span.get_span_context()

        trace_id = ""
        span_id = ""

        if span_context.is_valid:
            trace_id = format(span_context.trace_id, "032x")
            span_id = format(span_context.span_id, "016x")

        # -------------------------
        # OTEL HTTP metrics
        # -------------------------
        request_counter, request_duration = get_http_metrics()

        attributes = {
            "http.method": request.method,
            "http.route": route,
            "http.status_code": response.status_code,
        }

        if request_counter is not None:
            request_counter.add(1, attributes)

        if request_duration is not None:
            request_duration.record(latency_ms, attributes)

        # -------------------------
        # Application JSON log
        # -------------------------
        logger.info(
            "HTTP REQUEST STATUS",
            extra={
                "service": "notification-api",
                "trace_id": trace_id,
                "span_id": span_id,
                "http_method": request.method,
                "request_uri": request.full_path,
                "status_code": response.status_code,
                "client_ip": request.remote_addr,
                "latency_ms": latency_ms,
            },
        )

        return response
