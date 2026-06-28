#!/bin/sh

set -e

CONFIG_FILE=${CONFIG_FILE:-"/app/config.yaml"}

if [ ! -f "${CONFIG_FILE}" ]; then

cat <<EOF > "${CONFIG_FILE}"
---
server:
  host: "0.0.0.0"
  port: 8085

smtp:
  from: "${FROM}"
  username: "${SMTP_USERNAME}"
  password: "${SMTP_PASSWORD}"
  smtp_server: "${SMTP_SERVER}"
  smtp_port: ${SMTP_PORT}

elasticsearch:
  username: "${ELASTIC_USERNAME}"
  password: "${ELASTIC_PASSWORD}"
  host: "${ELASTIC_HOST}"
  port: ${ELASTIC_PORT}
  index: "${ELASTIC_INDEX:-employee_index}"
EOF

fi

export CONFIG_FILE=${CONFIG_FILE}

echo "===================================================="
echo "Starting Notification API"
echo "Configuration : ${CONFIG_FILE}"
echo "Port          : 8085"
echo "===================================================="

exec gunicorn \
    --bind 0.0.0.0:8085 \
    --workers 2 \
    --threads 4 \
    --timeout 60 \
    notification_api:app
