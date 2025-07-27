import json
from pathlib import Path
from datetime import datetime

PATH = Path("referrals.json")

# Структура JSON:
# {
#   "active": true,
#   "threshold": 3,
#   "last_ticket": 0,
#   "users": { "<user_id>": { "referrer": <referrer_id>, "counted": true } },
#   "referrers": {
#       "<referrer_id>": {
#           "referred": [<user_id>, ...],
#           "tickets": [<ticket_number>, ...]
#       }
#   },
#   "history": [
#     { "action": "paused", "time": "2025-07-27T12:00:00", "participants": 42, "tickets": 14 },
#     { "action": "started", "time": "2025-07-28T09:00:00" }
#   ]
# }

def load_data():
    if PATH.exists():
        return json.loads(PATH.read_text(encoding="utf-8"))
    # дефолтная структура
    return {
        "active": True,
        "threshold": 3,
        "last_ticket": 0,
        "users": {},
        "referrers": {},
        "history": []
    }

def save_data(data):
    PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def is_active():
    return load_data()["active"]

def record_start(user_id):
    data = load_data()
    # попадаем сюда при /start?start=ref_<referrer>
    args = user_id  # в вызывающем коде передаём actual_arg
    # (ниже детали реализации в handlers.py)
