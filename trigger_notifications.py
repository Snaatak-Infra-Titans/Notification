#!/usr/bin/env python3

import requests

URL = "http://127.0.0.1:8085/api/v1/notification/send/all"

try:

    response = requests.post(URL, timeout=30)

    print("=====================================")
    print("Notification Trigger")
    print("=====================================")
    print("Status Code :", response.status_code)
    print(response.text)

except Exception as exc:

    print(f"Failed to trigger Notification API: {exc}")
