#!/bin/sh
set -e

ES_HOST="${ELASTIC_HOST:-localhost}"
ES_PORT="${ELASTIC_PORT:-9200}"

echo "Waiting for Elasticsearch at ${ES_HOST}:${ES_PORT}..."

until nc -z "${ES_HOST}" "${ES_PORT}"
do
    echo "Elasticsearch is unavailable. Retrying in 5 seconds..."
    sleep 5
done

echo "Elasticsearch is available."
echo "Starting Notification API..."

exec gunicorn \
    --bind 0.0.0.0:${SERVER_PORT:-8085} \
    --workers 2 \
    --threads 4 \
    --timeout 60 \
    notification_api:app
