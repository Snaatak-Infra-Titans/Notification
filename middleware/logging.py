import logging
import time

from flask import request, g
from opentelemetry import trace

logger = logging.getLogger("notification-api")


def register_logging(app):

    @app.before_request
    def before_request():
        g.start_time = time.time()

    @app.after_request
    def after_request(response):

        latency = round(
            (time.time() - g.start_time) * 1000,
            2,
        )

        span = trace.get_current_span()
        span_context = span.get_span_context()

        trace_id = ""
        span_id = ""

        if span_context.is_valid:
            trace_id = format(
                span_context.trace_id,
                "032x",
            )

            span_id = format(
                span_context.span_id,
                "016x",
            )

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
                "latency_ms": latency,
            },
        )

        return response