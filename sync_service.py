"""ScyllaDB -> Elasticsearch synchronization for Notification API."""

import logging
import os

from cassandra.auth import PlainTextAuthProvider
from cassandra.cluster import Cluster
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import NotFoundError
from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode

logger = logging.getLogger("notification-api")
tracer = trace.get_tracer("notification-api/scylla-elasticsearch-sync")


def _env(name, default):
    value = os.getenv(name)
    return value if value not in (None, "") else default


def _set_client_span_attributes(span, *, system, host, port, namespace, operation):
    """Set stable database/client attributes without exposing credentials."""
    span.set_attribute("db.system", system)
    span.set_attribute("db.namespace", namespace)
    span.set_attribute("db.operation", operation)
    span.set_attribute("db.operation.name", operation)
    span.set_attribute("server.address", host)
    span.set_attribute("server.port", port)


def _record_span_error(span, exc):
    span.record_exception(exc)
    span.set_status(Status(StatusCode.ERROR, str(exc)))


def sync_scylla_to_es(es_client, es_index):
    """Synchronize salary records from ScyllaDB into Elasticsearch.

    The salary table is the trigger for a notification document. Employee
    details are joined from employee_info and the resulting document is
    upserted into Elasticsearch. Existing documents are overwritten so that
    salary/status/employee changes are reflected in Elasticsearch.

    This function keeps the existing business logic intact and adds tracing
    around the actual ScyllaDB and Elasticsearch operations.
    """
    host = _env("SCYLLA_HOST", "scylladb")
    port = int(_env("SCYLLA_PORT", "9042"))
    username = _env("SCYLLA_USERNAME", "scylladb")
    password = _env("SCYLLA_PASSWORD", "password")
    keyspace = _env("SCYLLA_KEYSPACE", "employee_db")

    es_host = _env("ELASTIC_HOST", "elasticsearch")
    es_port = int(_env("ELASTIC_PORT", "9200"))

    auth_provider = PlainTextAuthProvider(
        username=username,
        password=password,
    )

    cluster = Cluster(
        [host],
        port=port,
        auth_provider=auth_provider,
    )

    session = None
    synced_count = 0
    skipped_count = 0

    with tracer.start_as_current_span(
        "ScyllaDB -> Elasticsearch Sync",
        kind=SpanKind.INTERNAL,
    ) as sync_span:
        sync_span.set_attribute("sync.source", "scylladb")
        sync_span.set_attribute("sync.destination", "elasticsearch")
        sync_span.set_attribute("scylla.keyspace", keyspace)
        sync_span.set_attribute("elasticsearch.index", es_index)

        try:
            session = cluster.connect(keyspace)
            logger.info("Connected to ScyllaDB keyspace '%s'", keyspace)

            salary_query = (
                "SELECT id, name, salary, process_date, status "
                "FROM employee_salary"
            )

            with tracer.start_as_current_span(
                "SELECT employee_salary",
                kind=SpanKind.CLIENT,
            ) as span:
                _set_client_span_attributes(
                    span,
                    system="cassandra",
                    host=host,
                    port=port,
                    namespace=keyspace,
                    operation="SELECT",
                )
                span.set_attribute("db.statement", salary_query)

                try:
                    salary_rows = session.execute(salary_query)
                except Exception as exc:
                    _record_span_error(span, exc)
                    raise

            for salary in salary_rows:
                employee_query = (
                    "SELECT id, email, designation, name "
                    "FROM employee_info WHERE id = %s"
                )

                with tracer.start_as_current_span(
                    "SELECT employee_info",
                    kind=SpanKind.CLIENT,
                ) as span:
                    _set_client_span_attributes(
                        span,
                        system="cassandra",
                        host=host,
                        port=port,
                        namespace=keyspace,
                        operation="SELECT",
                    )
                    span.set_attribute("db.statement", employee_query)
                    try:
                        employee = session.execute(
                            employee_query,
                            [salary.id],
                        ).one()
                    except Exception as exc:
                        _record_span_error(span, exc)
                        raise

                if not employee:
                    skipped_count += 1
                    logger.warning(
                        "Employee info not found for salary record id=%s",
                        salary.id,
                    )
                    continue

                # Preserve the notification state of an existing document.
                # Otherwise every sync would set notified=false and could send
                # duplicate emails.
                notified = False
                with tracer.start_as_current_span(
                    "GET employee_index",
                    kind=SpanKind.CLIENT,
                ) as span:
                    _set_client_span_attributes(
                        span,
                        system="elasticsearch",
                        host=es_host,
                        port=es_port,
                        namespace=es_index,
                        operation="GET",
                    )
                    span.set_attribute("db.collection.name", es_index)
                    span.set_attribute("elasticsearch.document.id", employee.email)

                    try:
                        existing = es_client.get(index=es_index, id=employee.email)
                        notified = existing.get("_source", {}).get("notified", False)
                        span.set_attribute("elasticsearch.document.found", True)
                    except NotFoundError:
                        # New document: the notification must be pending.
                        notified = False
                        span.set_attribute("elasticsearch.document.found", False)
                    except Exception as exc:
                        _record_span_error(span, exc)
                        logger.exception(
                            "Unable to read existing ES document for %s",
                            employee.email,
                        )
                        raise

                document = {
                    "employee_id": salary.id,
                    "name": employee.name,
                    "email_id": employee.email,
                    "designation": employee.designation,
                    "salary": salary.salary,
                    "process_date": str(salary.process_date),
                    "status": salary.status,
                    "notified": notified,
                }

                # Use the employee email as the stable ES document ID, matching
                # the existing notification workflow.
                with tracer.start_as_current_span(
                    "INDEX employee_index",
                    kind=SpanKind.CLIENT,
                ) as span:
                    _set_client_span_attributes(
                        span,
                        system="elasticsearch",
                        host=es_host,
                        port=es_port,
                        namespace=es_index,
                        operation="INDEX",
                    )
                    span.set_attribute("db.collection.name", es_index)
                    span.set_attribute("elasticsearch.document.id", employee.email)
                    span.set_attribute("elasticsearch.refresh", False)

                    try:
                        es_client.index(
                            index=es_index,
                            id=employee.email,
                            body=document,
                            refresh=False,
                        )
                    except Exception as exc:
                        _record_span_error(span, exc)
                        raise

                synced_count += 1

            # Make newly indexed documents visible to the notification search.
            if synced_count:
                with tracer.start_as_current_span(
                    "REFRESH employee_index",
                    kind=SpanKind.CLIENT,
                ) as span:
                    _set_client_span_attributes(
                        span,
                        system="elasticsearch",
                        host=es_host,
                        port=es_port,
                        namespace=es_index,
                        operation="REFRESH",
                    )
                    span.set_attribute("db.collection.name", es_index)
                    try:
                        es_client.indices.refresh(index=es_index)
                    except Exception as exc:
                        _record_span_error(span, exc)
                        raise

            sync_span.set_attribute("sync.synced", synced_count)
            sync_span.set_attribute("sync.skipped", skipped_count)
            sync_span.set_status(Status(StatusCode.OK))

            logger.info(
                "ScyllaDB -> Elasticsearch sync completed: synced=%s skipped=%s",
                synced_count,
                skipped_count,
            )

            return {
                "status": "success",
                "synced": synced_count,
                "skipped": skipped_count,
            }

        except Exception as exc:
            _record_span_error(sync_span, exc)
            logger.exception("ScyllaDB -> Elasticsearch sync failed")
            raise

        finally:
            if session is not None:
                session.shutdown()
            cluster.shutdown()
