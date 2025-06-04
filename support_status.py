import json
from pathlib import Path

STATUS_PATH = Path("support_status.json")

def load_status():
    if STATUS_PATH.exists():
        with open(STATUS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_status(data):
    with open(STATUS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def is_support_open(user_id):
    data = load_status()
    return data.get(str(user_id), False)

def set_support_open(user_id, value=True):
    data = load_status()
    data[str(user_id)] = value
    save_status(data)
