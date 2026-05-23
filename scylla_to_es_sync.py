import time
from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider
from elasticsearch import Elasticsearch

SCYLLA_HOST = '127.0.0.1'
SCYLLA_USER = 'scylladb' 
SCYLLA_PASS = 'password' 
SCYLLA_KEYSPACE = 'employee_db'
TABLE_NAME = 'employee_info'
ES_HOST = "http://127.0.0.1:9200"

auth_provider = PlainTextAuthProvider(username=SCYLLA_USER, password=SCYLLA_PASS)
cluster = Cluster([SCYLLA_HOST], auth_provider=auth_provider)

try:
    session = cluster.connect(SCYLLA_KEYSPACE)
    print(f"Connected to ScyllaDB keyspace: {SCYLLA_KEYSPACE}")
except Exception as e:
    print(f"CRITICAL: Could not connect to ScyllaDB: {e}")
    exit(1)

es = Elasticsearch([ES_HOST])

def sync_data():
    try:
        rows = session.execute(f"SELECT name, email, designation FROM {TABLE_NAME}")
        count = 0
        for row in rows:
            if not es.exists(index="employee-management", id=row.email):
                doc = {
                    "name": row.name,
                    "email_id": row.email,
                    "designation": row.designation,
                    "notified": False
                }
                es.index(index="employee-management", id=row.email, body=doc)
                count += 1
        if count > 0:
            print(f"[{time.ctime()}] Successfully synced {count} NEW records.")
    except Exception as e:
        print(f"[{time.ctime()}] Sync Error: {e}")

if __name__ == "__main__":
    print(f"Smart Bridge Active...")
    while True:
        sync_data()
        time.sleep(30)
