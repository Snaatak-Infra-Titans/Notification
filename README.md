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
- ScyllaDB integration and ScyllaDB → Elasticsearch synchronization
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
├── sync_service.py
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

scylla:
  host: 127.0.0.1
  port: 9042
  username: scylladb
  password: password
  keyspace: employee_db
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

# Synchronize ScyllaDB to Elasticsearch

```
POST /api/v1/notification/sync
```

Example:

```bash
curl -X POST http://localhost:8085/api/v1/notification/sync
```

The endpoint reads salary records from `employee_salary`, joins employee
details from `employee_info`, and upserts them into the `employee_index`
Elasticsearch index. Existing `notified` state is preserved.

The `POST /api/v1/notification/send/all` endpoint performs this synchronization
before processing pending notifications, so no separate sync process is needed.

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

ScyllaDB is the source of truth for employee and salary data. The
Notification API now owns the ScyllaDB → Elasticsearch synchronization.
There is no separate `scylla-sync` service.

## Manual Sync

```bash
curl -X POST http://localhost:8085/api/v1/notification/sync
```

The API reads salary records from `employee_salary`, joins employee details
from `employee_info`, and upserts the resulting document into the
`employee_index` Elasticsearch index. Existing `notified` state is preserved
so synchronization does not cause duplicate emails.

## Notification Workflow

```text
ScyllaDB
   │
   │ employee_salary + employee_info
   ▼
Notification API
   │
   ├── Sync / upsert
   ▼
Elasticsearch
   │
   ├── find notified=false
   ▼
Send Email
   │
   ▼
Update notified=true
```

The `POST /api/v1/notification/send/all` endpoint performs the sync first and
then processes pending notifications. Existing cron jobs or manual calls to
`send/all` therefore continue to work without a separate sync worker.

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
Employee API / Salary API
      │
      ▼
ScyllaDB
      │
      ▼
Notification API
(Scylla → Elasticsearch sync)
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
