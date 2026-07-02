#!/usr/bin/env python3

from elasticsearch import Elasticsearch
import config_with_yaml as config

CONFIG_FILE = "config.yaml"

cfg = config.load(CONFIG_FILE)

es = Elasticsearch([
    f"http://{cfg.getProperty('elasticsearch.host')}:{cfg.getProperty('elasticsearch.port')}"
])

INDEX = cfg.getProperty("elasticsearch.index")

result = es.update_by_query(
    index=INDEX,
    body={
        "script": {
            "source": "ctx._source.notified = false",
            "lang": "painless"
        },
        "query": {
            "match_all": {}
        }
    },
    refresh=True
)

print("=====================================")
print("Notification Reset Completed")
print("=====================================")
print(f"Updated Documents : {result['updated']}")
print("All employees marked as notified = false")
