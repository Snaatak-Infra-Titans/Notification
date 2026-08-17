# Notification API

The Notification API sends salary notification emails for pending records that are already present in Elasticsearch. It does **not** connect to ScyllaDB and does **not** synchronize ScyllaDB data into Elasticsearch.

## Features

- Send an email to a single employee
- Send emails for all pending Elasticsearch records
- Health and detailed health endpoints
- Swagger API documentation
- Prometheus metrics
- Elasticsearch integration
- SMTP email support
- OpenTelemetry tracing
- Structured application logging

## Architecture

```text
Salary API / upstream producer
            |
            v
     Elasticsearch
     (salary_records)
            |
            | notified=false
            v
    Notification API
            |
            v
       SMTP Server
            |
            v
      Employee Email
            |
            v
     Elasticsearch
       notified=true
```

## Project Structure

```text
Notification/
├── notification_api.py
├── config.yaml
├── entrypoint.sh
├── requirements.txt
├── reset_notification_status.py
├── trigger_notifications.py
├── cleanup.sh
├── middleware/
├── telemetry/
├── utils/
└── test_smoke.py
```

There is intentionally no `sync_service.py` or `sync_worker.py`.

## Configuration

```yaml
elasticsearch:
  host: localhost
  port: 9200
  index: salary_records
```

The application also supports environment variables:

```text
SERVER_HOST
SERVER_PORT
ELASTIC_HOST
ELASTIC_PORT
ELASTIC_USERNAME
ELASTIC_PASSWORD
ELASTIC_INDEX
SMTP_FROM
SMTP_USERNAME
SMTP_PASSWORD
SMTP_SERVER
SMTP_PORT
```

## Run with Gunicorn

```bash
source venv/bin/activate
gunicorn --bind 0.0.0.0:8085 --workers 2 --threads 4 --timeout 60 notification_api:app
```

## Health Checks

```bash
curl http://localhost:8085/api/v1/notification/health
curl http://localhost:8085/api/v1/notification/health/detail
```

## Send Notification

Single employee:

```bash
curl -X POST http://localhost:8085/api/v1/notification/send \
  -H 'Content-Type: application/json' \
  -d '{"email":"employee@example.com"}'
```

Process all pending Elasticsearch records:

```bash
curl -X POST http://localhost:8085/api/v1/notification/send/all
```

The bulk endpoint only reads existing Elasticsearch records and updates `notified=true` after a successful email. It performs no ScyllaDB synchronization.
