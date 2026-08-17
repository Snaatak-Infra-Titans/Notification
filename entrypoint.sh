#!/bin/sh

set -e

echo "Waiting for Elasticsearch..."

until nc -z "${ELASTIC_HOST:-localhost}" "${ELASTIC_PORT:-9200}"
do
    echo "Elasticsearch is unavailable. Retrying in 5 seconds..."
    sleep 5
done

echo "Elasticsearch is available."
echo "Starting Notification API..."

exec gunicorn \
    --bind "${SERVER_HOST:-0.0.0.0}:${SERVER_PORT:-8085}" \
    --workers 2 \
    --threads 4 \
    --timeout 60 \
    notification_api:app
