# Notification API

The Notification API is responsible for sending salary notification emails to employees. It fetches employee records from Elasticsearch, sends emails using SMTP, and updates the notification status to avoid duplicate emails.

---

# Features

- Send email to a single employee
- Send emails to all pending employees
- Health check endpoints
- Swagger API documentation
- Prometheus metrics
- Elasticsearch integration
- SMTP email support

---

# Prerequisites

- Python 3.10+
- Elasticsearch
- SMTP Account (Gmail/App Password)
- Virtual Environment

---

# Project Structure

```
Notification/
├── notification_api.py
├── scylla_to_es_sync.py
├── reset_notification_status.py
├── trigger_notifications.py
├── config.yaml
├── requirements.txt
├── venv/
```

---

# Installation

## Create Virtual Environment

```bash
python3 -m venv venv
```

Activate

```bash
source venv/bin/activate
```

Install dependencies

```bash
pip install -r requirements.txt
```

---

# Configuration

Edit `config.yaml`

```yaml
smtp:
  smtp_server: smtp.gmail.com
  smtp_port: 587
  username: your-email@gmail.com
  password: your-app-password
  from: your-email@gmail.com

elasticsearch:
  host: 127.0.0.1
  port: 9200
  index: employee_index
```

---

# Run Notification API

```bash
source venv/bin/activate

python notification_api.py
```

API

```
http://localhost:8085
```

---

# Health Check

```
GET /api/v1/notification/health
```

Example

```bash
curl http://localhost:8085/api/v1/notification/health
```

---

# Send Notification to One Employee

```
POST /api/v1/notification/send
```

Example

```bash
curl -X POST http://localhost:8085/api/v1/notification/send \
-H "Content-Type: application/json" \
-d '{
  "email":"employee@example.com",
  "subject":"Salary Slip",
  "message":"Salary credited successfully."
}'
```

---

# Send Notifications to All Employees

```
POST /api/v1/notification/send/all
```

Example

```bash
curl -X POST http://localhost:8085/api/v1/notification/send/all
```

The API

- Searches Elasticsearch
- Finds employees where

```
notified = false
```

- Sends emails
- Updates

```
notified = true
```

to prevent duplicate emails.

---

# Monthly Notification Workflow

## Step 1

Reset notification status

```bash
cd Notification

source venv/bin/activate

python reset_notification_status.py
```

This updates every employee

```
notified = false
```

---

## Step 2

Trigger notifications

```bash
python trigger_notifications.py
```

or

```bash
curl -X POST http://localhost:8085/api/v1/notification/send/all
```

The Notification API sends salary emails and updates

```
notified = true
```

---

# ScyllaDB to Elasticsearch Sync

Run

```bash
python scylla_to_es_sync.py
```

The sync worker

- Reads employee data from ScyllaDB
- Reads salary information
- Creates Elasticsearch documents
- Automatically triggers Notification API

---

# Swagger

```
http://localhost:8085/apidocs/
```

---

# Prometheus Metrics

```
http://localhost:8085/metrics
```

---

# Systemd Services

Notification API

```bash
sudo systemctl status notification-api
```

Notification Sync

```bash
sudo systemctl status notification-sync
```

Restart

```bash
sudo systemctl restart notification-api
sudo systemctl restart notification-sync
```

---

# Logs

Notification API

```bash
tail -f ~/logs/notification-api.log
```

Notification Sync

```bash
tail -f ~/logs/notification-sync.log
```

---

# Cron Example

Reset notification status every month

```cron
0 0 1 * * cd /home/ubuntu/OT-Micro-Snatak-P18/Notification && /home/ubuntu/OT-Micro-Snatak-P18/Notification/venv/bin/python reset_notification_status.py
```

Trigger notifications

```cron
5 0 1 * * curl -X POST http://127.0.0.1:8085/api/v1/notification/send/all
```

---

# Notification Flow

```
Employee API
      │
      ▼
ScyllaDB
      │
      ▼
Sync Worker
(sc ylla_to_es_sync.py)
      │
      ▼
Elasticsearch
(notified = false)
      │
      ▼
Notification API
      │
      ▼
SMTP Server
      │
      ▼
Employee Email
      │
      ▼
Elasticsearch
(notified = true)
```

---

# Technology Stack

- Python
- Flask
- Elasticsearch
- ScyllaDB
- SMTP
- Swagger
- Prometheus
- Systemd
- Cron
