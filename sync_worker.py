"""Background worker for automatic ScyllaDB -> Elasticsearch synchronization."""

import logging
import os
import time

from elasticsearch import Elasticsearch

from notification_api import process_pending_notifications
from sync_service import sync_scylla_to_es

logger = logging.getLogger("notification-sync-worker")
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def env(name, default):
    value = os.getenv(name)
    return value if value not in (None, "") else default


def create_es_client():
    host = env("ELASTIC_HOST", "elasticsearch")
    port = int(env("ELASTIC_PORT", "9200"))
    username = os.getenv("ELASTIC_USERNAME", "")
    password = os.getenv("ELASTIC_PASSWORD", "")

    kwargs = {"hosts": [f"http://{host}:{port}"]}
    if username and password:
        kwargs["http_auth"] = (username, password)

    return Elasticsearch(**kwargs)


def main():
    interval = int(env("SCYLLA_SYNC_INTERVAL", "5"))
    es_index = env("ELASTIC_INDEX", "employee_index")

    logger.info(
        "Starting automatic ScyllaDB -> Elasticsearch sync worker "
        "(interval=%ss, index=%s)",
        interval,
        es_index,
    )

    while True:
        try:
            es = create_es_client()
            if not es.ping():
                raise ConnectionError("Elasticsearch ping failed")

            result = sync_scylla_to_es(es, es_index)
            logger.info(
                "Automatic sync completed: synced=%s skipped=%s",
                result["synced"],
                result["skipped"],
            )

            # Immediately process newly synchronized records.
            # This makes the background worker responsible for the full
            # Scylla -> Elasticsearch -> email flow.
            notification_result = process_pending_notifications(es)
            logger.info(
                "Automatic notification processing completed: total=%s sent=%s failed=%s",
                notification_result["total_records"],
                notification_result["notifications_sent"],
                notification_result["failed_notifications"],
            )
            es.close()

        except Exception:
            logger.exception("Automatic ScyllaDB -> Elasticsearch sync failed")

        time.sleep(interval)


if __name__ == "__main__":
    main()
