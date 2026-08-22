import os
import requests

MANAGER_URL = os.getenv("MANAGER_URL", "http://localhost:8001")

def rollback_flag(flag_name: str) -> None:

    url = f"{MANAGER_URL}/flags/{flag_name}"
    response = requests.put(url, json={"rollout_percentage": 0})
    response.raise_for_status()

