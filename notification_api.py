#!/usr/bin/env python3
"""
Notification API for OT-Microservices.

This microservice provides REST APIs for sending notifications
through SMTP and retrieving employee notification details from
Elasticsearch.

Author: Opstree Solutions
"""

import logging
import os
import sys
import re

import config_with_yaml as config
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from elasticsearch import Elasticsearch
from flask import Flask, jsonify, request
from flasgger import Swagger
from prometheus_flask_exporter import PrometheusMetrics
from telemetry.telemetry import init_tracing
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode
from cassandra.auth import PlainTextAuthProvider
from cassandra.cluster import Cluster
from elasticsearch.exceptions import NotFoundError
from middleware.logging import register_logging
from utils.log_encoder import CustomJsonFormatter

API_VERSION = "1.0"
CONFIG_FILE = os.environ.get("CONFIG_FILE", "config.yaml")

app = Flask(__name__)

init_tracing()

FlaskInstrumentor().instrument_app(app)

register_logging(app)

swagger_template = {
    "swagger": "2.0",
    "info": {
        "title": "Notification API",
        "description": "REST API for sending employee notifications",
        "version": API_VERSION,
        "contact": {
            "name": "OpsTree Solutions"
        }
    },
    "basePath": "/api/v1/notification"
}

Swagger(app, template=swagger_template)

PrometheusMetrics(app)



FORMATTER = CustomJsonFormatter()


def get_logger():
    """
    Configure application logger.
    """
    logger = logging.getLogger("notification-api")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(FORMATTER)
        logger.addHandler(console_handler)

    return logger


logger = get_logger()
tracer = trace.get_tracer("notification-api")


def read_configuration():
    """
    Load configuration from config.yaml.
    """
    try:
        cfg = config.load(CONFIG_FILE)

        logger.info("Configuration loaded successfully.")

        return cfg

    except Exception as exc:
        logger.exception("Unable to load configuration.")

        raise RuntimeError(
            "Configuration loading failed."
        ) from exc


cfg = read_configuration()

ES_INDEX = os.getenv("ELASTIC_INDEX", cfg.getProperty("elasticsearch.index"))

def es_client():
    """
    Create and return an Elasticsearch client.
    """
    try:
        host = os.getenv("ELASTIC_HOST", cfg.getProperty("elasticsearch.host"))
        port = int(os.getenv("ELASTIC_PORT", str(cfg.getProperty("elasticsearch.port"))))
        username = os.getenv("ELASTIC_USERNAME", cfg.getProperty("elasticsearch.username"))
        password = os.getenv("ELASTIC_PASSWORD", cfg.getProperty("elasticsearch.password"))

        logger.info("Connecting to Elasticsearch at %s:%s", host, port)

        if username and password:
            client = Elasticsearch(
                hosts=[f"http://{host}:{port}"],
                http_auth=(username, password),
            )
        else:
            client = Elasticsearch(
                hosts=[f"http://{host}:{port}"],
            )

        if not client.ping():
            raise ConnectionError("Unable to connect to Elasticsearch")

        logger.info("Successfully connected to Elasticsearch.")
        return client

    except Exception as exc:
        logger.exception("Failed to connect to Elasticsearch.")
        raise RuntimeError("Elasticsearch connection failed.") from exc

def send_mail(
    email_id,
    subject="Salary Slip",
    body="<strong>Your salary slip is generated. Please check.</strong>",
):
    """Send email through SMTP with an OpenTelemetry client span."""
    smtp_host = os.getenv("SMTP_SERVER", cfg.getProperty("smtp.smtp_server"))
    smtp_port = int(os.getenv("SMTP_PORT", str(cfg.getProperty("smtp.smtp_port"))))
    smtp_user = os.getenv("SMTP_USERNAME", cfg.getProperty("smtp.username"))
    smtp_pass = os.getenv("SMTP_PASSWORD", cfg.getProperty("smtp.password"))
    mail_from = os.getenv("SMTP_FROM", cfg.getProperty("smtp.from"))

    with tracer.start_as_current_span("SMTP send email", kind=SpanKind.CLIENT) as span:
        span.set_attribute("server.address", smtp_host)
        span.set_attribute("server.port", smtp_port)
        span.set_attribute("email.recipient", email_id)
        span.set_attribute("email.subject", subject)
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = mail_from
            msg["To"] = email_id
            msg.attach(MIMEText(body, "html"))

            server = smtplib.SMTP(smtp_host, smtp_port)
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(mail_from, [email_id], msg.as_string())
            server.quit()

            span.set_status(Status(StatusCode.OK))
            logger.info("Email sent successfully to %s", email_id)
            return True
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            logger.exception("Failed to send email to %s", email_id)
            return False


@app.route("/api/v1/notification/health", methods=["GET"])
def health():
    """
    Health Check API
    ---
    tags:
      - Health
    summary: Notification API Health
    description: Returns basic health status of the Notification API.
    responses:
      200:
        description: Notification API is healthy
        schema:
          type: object
          properties:
            status:
              type: string
              example: UP
            service:
              type: string
              example: notification-api
            version:
              type: string
              example: "1.0"
    """

    logger.info("Health endpoint invoked.")

    return jsonify(
        {
            "status": "UP",
            "service": "notification-api",
            "version": API_VERSION
        }
    ), 200


@app.route("/api/v1/notification/health/detail", methods=["GET"])
def detailed_health():
    """
    Detailed Health Check API
    ---
    tags:
      - Health
    summary: Detailed Notification API Health
    description: Checks Elasticsearch connectivity and SMTP configuration.
    responses:
      200:
        description: Health information
    """

    response = {
        "service": "notification-api",
        "status": "UP",
        "version": API_VERSION,
        "elasticsearch": "DOWN",
        "smtp": "DOWN"
    }

    try:
        es = es_client()

        if es.ping():
            response["elasticsearch"] = "UP"

    except Exception:
        logger.exception("Elasticsearch health check failed.")

    try:
        smtp_host = os.getenv(
            "SMTP_SERVER", cfg.getProperty("smtp.smtp_server")
        )
        smtp_user = os.getenv(
            "SMTP_USERNAME", cfg.getProperty("smtp.username")
        )
        if smtp_host and smtp_user:
            response["smtp"] = "UP"

    except Exception:
        logger.exception("SMTP health check failed.")

    logger.info("Detailed health endpoint invoked.")

    return jsonify(response), 200

@app.route("/api/v1/notification/send", methods=["POST"])
def send_notification():
    """
    Send Notification
    ---
    tags:
      - Notification
    summary: Send notification to a single employee
    description: Sends an email notification to the specified employee.

    consumes:
      - application/json

    produces:
      - application/json

    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - email
          properties:
            email:
              type: string
              example: "john@example.com"
            subject:
              type: string
              example: "Salary Slip"
            message:
              type: string
              example: "<strong>Your salary slip is generated.</strong>"

    responses:
      200:
        description: Email sent successfully

      400:
        description: Invalid request

      500:
        description: Internal server error
    """

    logger.info("Received request to send notification.")

    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "status": "error",
                "message": "Request body is required."
            }), 400

        email = data.get("email")

        if not email:
            return jsonify({
                "status": "error",
                "message": "email field is required."
            }), 400
        
        email_pattern = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
        
        if not re.match(email_pattern, email):
            return jsonify({
                "status": "error",
                "message": "Invalid email address."
            }), 400
        
        subject = data.get(
            "subject",
            "Salary Slip"
        )

        body = data.get(
            "message",
            "<strong>Your salary slip is generated. Please check.</strong>"
        )

        success = send_mail(
            email,
            subject,
            body
        )

        if success:

            logger.info(
                "Notification sent successfully to %s",
                email
            )

            return jsonify({
                "status": "success",
                "message": "Notification sent successfully."
            }), 200

        logger.error(
            "Unable to send notification to %s",
            email
        )

        return jsonify({
            "status": "error",
            "message": "Failed to send notification."
        }), 500

    except Exception:

        logger.exception(
            "Unexpected error while sending notification."
        )
    
        return jsonify({
            "status": "error",
            "message": "Internal Server Error"
        }), 500

def _env(name, default):
    value = os.getenv(name)
    return value if value not in (None, "") else default


def _set_client_span_attributes(
    span, *, system, host, port, namespace, operation
):
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
    """Synchronize ScyllaDB salary/employee data into Elasticsearch.

    This function runs only when the API calls /sync or /send/all.
    There is deliberately no background sync worker.
    """
    host = _env("SCYLLA_HOST", "otms.scylladb.internal")
    port = int(_env("SCYLLA_PORT", "9042"))
    username = _env("SCYLLA_USERNAME", "scylladb")
    password = _env("SCYLLA_PASSWORD", "password")
    keyspace = _env("SCYLLA_KEYSPACE", "employee_db")

    es_host = _env("ELASTIC_HOST", "localhost")
    es_port = int(_env("ELASTIC_PORT", "9200"))

    cluster = Cluster(
        [host],
        port=port,
        auth_provider=PlainTextAuthProvider(
            username=username,
            password=password,
        ),
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

            salary_query = (
                "SELECT id, name, salary, process_date, status "
                "FROM employee_salary"
            )
            with tracer.start_as_current_span(
                "SELECT employee_salary", kind=SpanKind.CLIENT
            ) as span:
                _set_client_span_attributes(
                    span, system="cassandra", host=host, port=port,
                    namespace=keyspace, operation="SELECT"
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
                    "SELECT employee_info", kind=SpanKind.CLIENT
                ) as span:
                    _set_client_span_attributes(
                        span, system="cassandra", host=host, port=port,
                        namespace=keyspace, operation="SELECT"
                    )
                    span.set_attribute("db.statement", employee_query)
                    try:
                        employee = session.execute(
                            employee_query, [salary.id]
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

                notified = False
                with tracer.start_as_current_span(
                    "GET employee_index", kind=SpanKind.CLIENT
                ) as span:
                    _set_client_span_attributes(
                        span, system="elasticsearch", host=es_host,
                        port=es_port, namespace=es_index, operation="GET"
                    )
                    span.set_attribute("db.collection.name", es_index)
                    span.set_attribute(
                        "elasticsearch.document.id", employee.email
                    )
                    try:
                        existing = es_client.get(
                            index=es_index, id=employee.email
                        )
                        notified = existing.get("_source", {}).get(
                            "notified", False
                        )
                        span.set_attribute(
                            "elasticsearch.document.found", True
                        )
                    except NotFoundError:
                        span.set_attribute(
                            "elasticsearch.document.found", False
                        )
                    except Exception as exc:
                        _record_span_error(span, exc)
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

                with tracer.start_as_current_span(
                    "INDEX employee_index", kind=SpanKind.CLIENT
                ) as span:
                    _set_client_span_attributes(
                        span, system="elasticsearch", host=es_host,
                        port=es_port, namespace=es_index, operation="INDEX"
                    )
                    span.set_attribute("db.collection.name", es_index)
                    span.set_attribute(
                        "elasticsearch.document.id", employee.email
                    )
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

            if synced_count:
                with tracer.start_as_current_span(
                    "REFRESH employee_index", kind=SpanKind.CLIENT
                ) as span:
                    _set_client_span_attributes(
                        span, system="elasticsearch", host=es_host,
                        port=es_port, namespace=es_index, operation="REFRESH"
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


@app.route("/api/v1/notification/sync", methods=["POST"])
def sync_notifications_data():
    """Synchronize ScyllaDB salary/employee data into Elasticsearch."""

    logger.info("ScyllaDB -> Elasticsearch sync requested.")

    try:
        es = es_client()
        result = sync_scylla_to_es(es, ES_INDEX)

        return jsonify({
            "status": "success",
            "message": "ScyllaDB data synchronized to Elasticsearch.",
            **result,
        }), 200

    except Exception:
        logger.exception("ScyllaDB -> Elasticsearch sync request failed.")
        return jsonify({
            "status": "error",
            "message": "Failed to synchronize ScyllaDB data to Elasticsearch.",
        }), 500


def process_pending_notifications(es):
    """Send email for all pending Elasticsearch notification records."""
    result = es.search(
        index=ES_INDEX,
        body={
            "query": {
                "bool": {
                    "must_not": [{"term": {"notified": True}}]
                }
            }
        },
    )

    hits = result["hits"]["hits"]
    logger.info("Pending notification count: %s", len(hits))

    if not hits:
        return {
            "total_records": 0,
            "notifications_sent": 0,
            "failed_notifications": 0,
        }

    success_count = 0
    failed_count = 0

    for hit in hits:
        source = hit["_source"]
        email = source.get("email_id")

        if not email:
            logger.warning(
                "Skipping document %s because email_id is missing.",
                hit["_id"],
            )
            failed_count += 1
            continue

        if send_mail(email):
            es.update(
                index=ES_INDEX,
                id=hit["_id"],
                body={"doc": {"notified": True}},
            )
            logger.info("Notification sent successfully to %s", email)
            success_count += 1
        else:
            logger.error("Failed to send notification to %s", email)
            failed_count += 1

    logger.info(
        "Notification processing completed. Success=%s Failed=%s",
        success_count,
        failed_count,
    )

    return {
        "total_records": len(hits),
        "notifications_sent": success_count,
        "failed_notifications": failed_count,
    }


@app.route("/api/v1/notification/send/all", methods=["POST"])
def send_all_notifications():
    """Synchronize ScyllaDB data and immediately notify pending employees."""
    logger.info("Bulk notification request received.")

    try:
        es = es_client()
        sync_result = sync_scylla_to_es(es, ES_INDEX)
        notification_result = process_pending_notifications(es)
        es.close()

        return jsonify({
            "status": "success",
            "sync": sync_result,
            **notification_result,
        }), 200

    except Exception:
        logger.exception("Bulk notification processing failed.")
        return jsonify({
            "status": "error",
            "message": "Internal Server Error",
        }), 500

