import json

SETTINGS_PATH = "settings.json"

def get_settings():
    with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def update_settings(new_data: dict):
    with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.update(new_data)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)