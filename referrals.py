import json
import random
import string
from pathlib import Path

PATH = Path("referrals.json")


def load_data():
    if PATH.exists():
        data = json.loads(PATH.read_text(encoding="utf-8"))
    else:
        data = {
            "active": True,
            "threshold": 3,          # порог приглашений для 1 билета
            "current_round": 1,      # номер текущего розыгрыша
            "users": {},             # "<user_id>": {"referrer": id, "counted": bool}
            "referrers": {},         # "<referrer_id>": {"referred": [...], "tickets": [...], "round_count": 0}
            "history": []
        }

    # Нормализация и обратная совместимость
    if "current_round" not in data:
        data["current_round"] = 1
    if "referrers" not in data:
        data["referrers"] = {}

    for ref_id, info in data["referrers"].items():
        # tickets всегда как строки
        info["tickets"] = [str(x) for x in info.get("tickets", [])]
        # счётчик текущего розыгрыша
        if "round_count" not in info:
            # Инициализируем нулём, чтобы старые приглашения не влияли на новый раунд
            info["round_count"] = 0

    return data


def save_data(data):
    PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def is_active():
    return load_data().get("active", False)


def _existing_codes(data):
    codes = set()
    for info in data.get("referrers", {}).values():
        for c in info.get("tickets", []):
            codes.add(str(c))
    return codes


def generate_unique_code(data):
    """6-значный уникальный код из цифр."""
    used = _existing_codes(data)
    while True:
        code = "".join(random.choices(string.digits, k=6))
        if code not in used:
            return code
