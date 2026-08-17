from pythonjsonlogger import jsonlogger
from opentelemetry import trace


class CustomJsonFormatter(jsonlogger.JsonFormatter):

    def add_fields(self, log_record, record, message_dict):

        super().add_fields(log_record, record, message_dict)

        if "timestamp" not in log_record:
            log_record["timestamp"] = record.created

        span = trace.get_current_span()
        span_context = span.get_span_context()

        if span_context.is_valid:
            log_record["trace_id"] = format(
                span_context.trace_id,
                "032x"
            )

            log_record["span_id"] = format(
                span_context.span_id,
                "016x"
            )

        log_record["service"] = "notification-api"