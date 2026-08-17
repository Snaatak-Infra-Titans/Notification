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
from sync_service import sync_scylla_to_es
from opentelemetry.instrumentation.flask import FlaskInstrumentor
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
    """
    Send email using Python's smtplib.

    Returns:
        bool: True if email sent successfully.
    """

    try:

        smtp_host = os.getenv(
            "SMTP_SERVER",
            cfg.getProperty("smtp.smtp_server")
        )

        smtp_port = int(
            os.getenv(
                "SMTP_PORT",
                str(cfg.getProperty("smtp.smtp_port"))
            )
        )

        smtp_user = os.getenv(
            "SMTP_USERNAME",
            cfg.getProperty("smtp.username")
        )

        smtp_pass = os.getenv(
            "SMTP_PASSWORD",
            cfg.getProperty("smtp.password")
        )

        mail_from = os.getenv(
            "SMTP_FROM",
            cfg.getProperty("smtp.from")
        )


        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = mail_from
        msg["To"] = email_id

        msg.attach(MIMEText(body, "html"))

        server = smtplib.SMTP(smtp_host, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_pass)

        server.sendmail(
            mail_from,
            [email_id],
            msg.as_string(),
        )

        server.quit()

        logger.info("Email sent successfully to %s", email_id)

        return True

    except Exception:
        logger.exception(
            "Failed to send email to %s",
            email_id,
        )
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
        if (
            cfg.getProperty("smtp.smtp_server")
            and cfg.getProperty("smtp.username")
        ):
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

