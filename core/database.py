import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(BASE_DIR, "kn_points_data.json")
HISTORY_FILE = os.path.join(BASE_DIR, "mines_history.json")

# ✅ 追加：初期化関数
def init_db():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({"points": {}}, f, ensure_ascii=False, indent=2)
    if not os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)

def load_all():
    if not os.path.exists(DATA_FILE):
        return {"points": {}}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"points": {}}

def save_all(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_points(user_id):
    return load_all().get("points", {}).get(str(user_id), 0)

def set_points(user_id, value):
    data = load_all()
    data.setdefault("points", {})[str(user_id)] = int(value)
    save_all(data)

def add_points(user_id, delta):
    current = get_points(user_id)
    set_points(user_id, current + delta)

def add_history(entry):
    logs = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                logs = json.load(f)
        except Exception:
            pass
    logs.insert(0, entry)
    logs = logs[:200]
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)
