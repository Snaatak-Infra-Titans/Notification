#!/bin/sh

set -e

SYNC_INTERVAL="${SCYLLA_SYNC_INTERVAL:-5}"

cleanup() {
    echo "Stopping Notification API and sync worker..."
    if [ -n "${SYNC_PID:-}" ]; then
        kill "${SYNC_PID}" 2>/dev/null || true
    fi
}

trap cleanup INT TERM EXIT

echo "Waiting for Elasticsearch..."

until nc -z "${ELASTIC_HOST}" "${ELASTIC_PORT}"
do
    echo "Elasticsearch is unavailable. Retrying in 5 seconds..."
    sleep 5
done

echo "Elasticsearch is available."
echo "Starting automatic ScyllaDB -> Elasticsearch sync worker (every ${SYNC_INTERVAL}s)..."

python /app/sync_worker.py &
SYNC_PID=$!

echo "Starting Notification API..."

gunicorn \
    --bind 0.0.0.0:${SERVER_PORT:-8085} \
    --workers 2 \
    --threads 4 \
    --timeout 60 \
    notification_api:app &
GUNICORN_PID=$!

wait "${GUNICORN_PID}"
