#!/bin/bash

set -Eeuo pipefail

echo "Stopping Notification services..."

sudo systemctl stop notification-api || true
sudo systemctl stop notification-sync || true

echo "Cleaning Elasticsearch indexes..."

curl -s -X DELETE http://localhost:9200/employee_index >/dev/null || true
curl -s -X DELETE http://localhost:9200/salary_records >/dev/null || true
curl -s -X DELETE http://localhost:9200/attendance_records >/dev/null || true

echo "Cleaning logs..."

rm -rf /home/ubuntu/logs/*

echo "Cleaning Python cache..."

find /home/ubuntu -type d -name "__pycache__" -exec rm -rf {} + || true
find /home/ubuntu -type f -name "*.pyc" -delete || true

echo "Notification cleanup completed."
