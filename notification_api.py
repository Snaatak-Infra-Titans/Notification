#!/usr/bin/python3
#pylint: disable = invalid-name, broad-except
"""
A notification application which runs on scheduled basis and send the information to users.
Author:- Opstree Solutions
"""

import argparse
import os
import sys
import logging
import time
import emails
import config_with_yaml as config
from elasticsearch import Elasticsearch
import schedule

CONFIG_FILE = os.environ.get("CONFIG_FILE")
FORMATTER = logging.Formatter("%(asctime)s — %(name)s — %(levelname)s — %(message)s")

def get_logger():
    logger = logging.getLogger("notification-service")
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(FORMATTER)
        logger.addHandler(console_handler)
    return logger

def read_configuration():
    logger = get_logger()
    try:
        return config.load(CONFIG_FILE)
    except Exception as e:
        logger.error("Config error: %s", e)

def send_mail(email_id):
    logger = get_logger()
    cfg = read_configuration()
    try:
        message = emails.html(
            html="<strong>Your salary slip is generated please check</strong>",
            subject="Salary Slip",
            mail_from=cfg.getProperty("smtp.from"),
        )
        message.send(
            to=email_id,
            smtp={
                "host": cfg.getProperty("smtp.smtp_server"),
                "port": cfg.getProperty("smtp.smtp_port"),
                "timeout": 5,
                "user": cfg.getProperty("smtp.username"),
                "password": cfg.getProperty("smtp.password"),
                "tls": False,  
            },
        )
        logger.info("Sent mail to %s", email_id)
        return True
    except Exception as e:
        logger.error("Mail fail for %s: %s", email_id, e)
        return False

def send_mail_to_all_users():
    logger = get_logger()
    cfg = read_configuration()
    try:
        es = Elasticsearch([f"http://{cfg.getProperty('elasticsearch.host')}:{cfg.getProperty('elasticsearch.port')}"])
        result = es.search(
            index="employee-management", 
            body={
                "query": {
                    "bool": {
                        "must_not": [
                            {"term": {"notified": True}}
                        ]
                    }
                }
            }
        )
        
        hits = result["hits"]["hits"]
        if not hits:
            logger.info("No new employees to notify.")
            return

        for data in hits:
            email = data["_source"]["email_id"]
            doc_id = data["_id"]
            
            success = send_mail(email)
            
            # Tag the user in Elasticsearch so they aren't emailed again
            if success:
                es.update(
                    index="employee-management",
                    id=doc_id,
                    body={"doc": {"notified": True}}
                )
                logger.info("Marked %s as notified.", email)

    except Exception as e:
        logger.error("ES Query Error: %s", e)

def schedule_operation():
    logger = get_logger()
    schedule.every(1).minutes.do(send_mail_to_all_users)
    while True:
        logger.info("Worker heartbeat: Checking for new employees...")
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--mode", default="scheduled")
    args = parser.parse_args()
    if args.mode == "scheduled":
        schedule_operation()
    else:
        send_mail_to_all_users()
