import time
import requests
from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider
from elasticsearch import Elasticsearch

# ==========================================
# ScyllaDB Configuration
# ==========================================

SCYLLA_HOST = 'scylladb.otms.internal'
SCYLLA_USER = 'scylladb'
SCYLLA_PASS = 'password'

KEYSPACE = 'employee_db'

EMPLOYEE_TABLE = 'employee_info'
SALARY_TABLE = 'employee_salary'

# ==========================================
# Elasticsearch Configuration
# ==========================================

ES_HOST = "http://127.0.0.1:9200"
ES_INDEX = "employee_index"

# ==========================================
# Cassandra Connection
# ==========================================

auth_provider = PlainTextAuthProvider(
    username=SCYLLA_USER,
    password=SCYLLA_PASS
)

cluster = Cluster(
    [SCYLLA_HOST],
    auth_provider=auth_provider
)

try:
    session = cluster.connect(KEYSPACE)
    print(f"Connected to ScyllaDB keyspace: {KEYSPACE}")
except Exception as e:
    print(f"CRITICAL: Could not connect to ScyllaDB: {e}")
    exit(1)

# ==========================================
# Elasticsearch Connection
# ==========================================

es = Elasticsearch([ES_HOST])

# ==========================================
# Sync Function
# ==========================================

def sync_data():

    try:

        # Fetch salary records
        salary_rows = session.execute(
            f"SELECT id, name, salary, process_date, status FROM {SALARY_TABLE}"
        )

        synced_count = 0

        for salary in salary_rows:

            employee_id = salary.id

            # Fetch employee info using ID
            employee_query = session.execute(
                f"SELECT id, email, designation, name FROM {EMPLOYEE_TABLE} WHERE id = %s",
                [employee_id]
            )

            employee = employee_query.one()

            if not employee:
                print(f"Employee info not found for ID: {employee_id}")
                continue

            email = employee.email

            # Skip already indexed employees
            if es.exists(index=ES_INDEX, id=email):
                continue

            # Elasticsearch document
            doc = {
                "employee_id": employee_id,
                "name": employee.name,
                "email_id": employee.email,
                "designation": employee.designation,
                "salary": salary.salary,
                "process_date": str(salary.process_date),
                "status": salary.status,
                "notified": False
            }

            # Index document
            es.index(
                index=ES_INDEX,
                id=email,
                body=doc,
                refresh="wait_for"
            )

            synced_count += 1

            print(f"Indexed Employee: {employee.name}")

        if synced_count > 0:
            print(f"[{time.ctime()}] Successfully synced {synced_count} new records.")

            try:
                response = requests.post(
                    "http://127.0.0.1:8085/api/v1/notification/send/all",
                    timeout=15
                )
                print(f"Notification API Response: {response.status_code}")
            except Exception as exc:
                print(f"Failed to trigger Notification API: {exc}")

        else:
            print(f"[{time.ctime()}] No new records to sync.")

    except Exception as e:
        print(f"[{time.ctime()}] Sync Error: {e}")

# ==========================================
# Main Loop
# ==========================================

if __name__ == "__main__":

    print("ScyllaDB → Elasticsearch Sync Service Started")

    while True:

        sync_data()

        time.sleep(2)
