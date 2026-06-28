#!/usr/bin/python3
# pylint: disable=invalid-name,broad-except

"""
Notification API
Author: Opstree Solutions
"""

import os
import sys
import logging

import emails
import config_with_yaml as config

from elasticsearch import Elasticsearch
from flask import Flask, request, jsonify

CONFIG_FILE = os.environ.get("CONFIG_FILE")

app = Flask(__name__)

FORMATTER = logging.Formatter(
    "%(asctime)s — %(name)s — %(levelname)s — %(message)s"
)


def get_logger():
    logger = logging.getLogger("notification-service")
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(FORMATTER)
        logger.addHandler(console_handler)

    return logger


def read_configuration():
    logger = get_logger()

    try:
        return config.load(CONFIG_FILE)
    except Exception as e:
        logger.error("Configuration Error : %s", e)
        return None


def get_es_client():
    cfg = read_configuration()

    return Elasticsearch(
        [
            f"http://{cfg.getProperty('elasticsearch.host')}:"
            f"{cfg.getProperty('elasticsearch.port')}"
        ]
    )


def send_mail(email_id):
    logger = get_logger()
    cfg = read_configuration()

    try:
        message = emails.html(
            html="<strong>Your salary slip is generated. Please check.</strong>",
            subject="Salary Slip",
            mail_from=cfg.getProperty("smtp.from"),
        )

        response = message.send(
            to=email_id,
            smtp={
                "host": cfg.getProperty("smtp.smtp_server"),
                "port": cfg.getProperty("smtp.smtp_port"),
                "timeout": 5,
                "user": cfg.getProperty("smtp.username"),
                "password": cfg.getProperty("smtp.password"),
                "tls": True,
            },
        )

        logger.info("Mail sent to %s", email_id)
        logger.debug("SMTP Response : %s", vars(response))

        return True

    except Exception as e:
        logger.error("Failed sending mail to %s : %s", email_id, e)
        return False


def send_mail_to_all_users():

    logger = get_logger()

    try:

        es = get_es_client()

        result = es.search(
            index="employee_index",
            body={
                "query": {
                    "bool": {
                        "must_not": [
                            {
                                "term": {
                                    "notified": True
                                }
                            }
                        ]
                    }
                }
            }
        )

        hits = result["hits"]["hits"]

        if not hits:
            logger.info("No employees pending notification.")

            return {
                "message": "No employees pending notification."
            }

        count = 0

        for data in hits:

            source = data["_source"]

            if "email_id" not in source:

                logger.warning(
                    "Skipping document %s. Email not found.",
                    data["_id"],
                )

                continue

            email = source["email_id"]

            doc_id = data["_id"]

            if send_mail(email):

                es.update(
                    index="employee_index",
                    id=doc_id,
                    body={
                        "doc": {
                            "notified": True
                        }
                    },
                )

                count += 1

        return {
            "message": f"{count} notification(s) sent."
        }

    except Exception as e:

        logger.error("Elasticsearch Error : %s", e)

        return {
            "error": str(e)
        }


@app.route("/api/v1/notification/health", methods=["GET"])
def health():

    return jsonify(
        {
            "status": "UP",
            "service": "Notification API"
        }
    )


@app.route("/api/v1/notification/send", methods=["POST"])
def send_notification():

    data = request.get_json()

    if not data:

        return (
            jsonify(
                {
                    "message": "Invalid JSON body"
                }
            ),
            400,
        )

    email = data.get("email")

    if not email:

        return (
            jsonify(
                {
                    "message": "email field is required"
                }
            ),
            400,
        )

    if send_mail(email):

        return (
            jsonify(
                {
                    "message": "Mail sent successfully."
                }
            ),
            200,
        )

    return (
        jsonify(
            {
                "message": "Mail sending failed."
            }
        ),
        500,
    )


@app.route("/api/v1/notification/send/all", methods=["POST"])
def notify_all():

    result = send_mail_to_all_users()

    return jsonify(result)


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=8083,
        debug=False,
    )
