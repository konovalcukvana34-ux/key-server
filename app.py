from flask import Flask, request, jsonify
import json, os, secrets, string, time, datetime

app = Flask(__name__)
KEYS_FILE = "keys.json"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "changeme123")

# ── Хранилище аккаунтов в памяти ──────────────────────────────────────────────
# { nick: { role, stats, last_seen, commands: [] } }
accounts = {}

# Уведомления для бота (бот забирает и очищает)
notifications = []  # [ { type, data } ]

# ── Ключи ─────────────────────────────────────────────────────────────────────

def load_keys():
    if not os.path.exists(KEYS_FILE):
        return {}
    with open(KEYS_FILE, "r") as f:
        return json.load(f)

def save_keys(keys):
    with open(KEYS_FILE, "w") as f:
        json.dump(keys, f, indent=2)

def generate_key():
    chars = string.ascii_uppercase + string.digits
    return "AUTOSELL-" + "-".join("".join(secrets.choice(chars) for _ in range(4)) for _ in range(4))

# ── Проверка ключа (существующий endpoint) ────────────────────────────────────

@app.route("/check", methods=["GET"])
def check_key():
    key  = request.args.get("key", "").strip().upper()
    hwid = request.args.get("hwid", "").strip()

    if not key or not hwid:
        return jsonify({"valid": False, "reason": "missing_params"}), 400

    keys = load_keys()
    if key not in keys:
        return jsonify({"valid": False, "reason": "invalid_key"}), 200

    entry = keys[key]

    if not entry.get("active", False):
        return jsonify({"valid": False, "reason": "key_disabled"}), 200

    expires_at = entry.get("expires_at", 0)
    if expires_at > 0 and time.time() > expires_at:
        keys[key]["active"] = False
        save_keys(keys)
        return jsonify({"valid": False, "reason": "key_expired"}), 200

    bound_hwid = entry.get("hwid", "")
    if bound_hwid == "":
        keys[key]["hwid"] = hwid
        save_keys(keys)
        days_left = int((expires_at - time.time()) / 86400) if expires_at > 0 else 999
        return jsonify({"valid": True, "days_left": days_left}), 200

    if bound_hwid != hwid:
        return jsonify({"valid": False, "reason": "wrong_hwid"}), 200

    days_left = int((expires_at - time.time()) / 86400) if expires_at > 0 else 999
    return jsonify({"valid": True, "days_left": days_left}), 200

# ── Регистрация аккаунта ──────────────────────────────────────────────────────

@app.route("/register", methods=["POST"])
def register():
    data = request.json or {}
    nick = data.get("nick", "").strip()
    role = data.get("role", "").strip().lower()  # monitor / buyer / seller

    if not nick or role not in ("monitor", "buyer", "seller"):
        return jsonify({"error": "bad params"}), 400

    accounts[nick] = {
        "role": role,
        "last_seen": time.time(),
        "stats": {},
        "commands": []
    }
    print(f"[register] {nick} as {role}")
    return jsonify({"ok": True}), 200

# ── Heartbeat (статистика от мода) ────────────────────────────────────────────

@app.route("/heartbeat", methods=["POST"])
def heartbeat():
    data = request.json or {}
    nick = data.get("nick", "").strip()
    if not nick or nick not in accounts:
        return jsonify({"error": "unknown nick"}), 400

    accounts[nick]["last_seen"] = time.time()
    accounts[nick]["stats"] = data.get("stats", {})

    # Проверяем уведомления о крупных покупках
    coins_bought = data.get("coins_bought", 0)
    if coins_bought >= 100:
        notifications.append({
            "type": "big_buy",
            "nick": nick,
            "coins": coins_bought,
            "rate": data.get("rate", 0),
            "money": data.get("money_spent", 0),
            "time": time.time()
        })

    return jsonify({"ok": True}), 200

# ── Получить команду (мод polling'ом берёт команду) ──────────────────────────

@app.route("/commands/<nick>", methods=["GET"])
def get_commands(nick):
    if nick not in accounts:
        return jsonify({"commands": []}), 200

    cmds = accounts[nick].get("commands", [])
    accounts[nick]["commands"] = []  # очищаем после выдачи
    return jsonify({"commands": cmds}), 200

# ── Отправить команду (бот вызывает этот endpoint) ───────────────────────────

@app.route("/send_command", methods=["POST"])
def send_command():
    data = request.json or {}
    if data.get("password") != ADMIN_PASSWORD:
        return jsonify({"error": "unauthorized"}), 403

    target = data.get("target", "").strip().lower()  # ник или роль (monitor/buyer/seller/all)
    command = data.get("command", "").strip()

    if not command:
        return jsonify({"error": "no command"}), 400

    sent_to = []

    for nick, acc in accounts.items():
        match = (
            target == "all" or
            target == acc["role"] or
            target == "sellers" and acc["role"] == "seller" or
            target == nick.lower()
        )
        if match:
            acc["commands"].append(command)
            sent_to.append(nick)

    return jsonify({"ok": True, "sent_to": sent_to}), 200

# ── Статистика всех аккаунтов ─────────────────────────────────────────────────

@app.route("/admin/accounts", methods=["POST"])
def admin_accounts():
    data = request.json or {}
    if data.get("password") != ADMIN_PASSWORD:
        return jsonify({"error": "unauthorized"}), 403

    now = time.time()
    result = {}
    for nick, acc in accounts.items():
        online = (now - acc["last_seen"]) < 30  # онлайн если heartbeat < 30 сек назад
        result[nick] = {
            "role": acc["role"],
            "online": online,
            "last_seen": int(now - acc["last_seen"]),  # секунд назад
            "stats": acc["stats"]
        }
    return jsonify(result), 200

# ── Уведомления для бота ──────────────────────────────────────────────────────

@app.route("/admin/notifications", methods=["POST"])
def get_notifications():
    data = request.json or {}
    if data.get("password") != ADMIN_PASSWORD:
        return jsonify({"error": "unauthorized"}), 403

    result = notifications.copy()
    notifications.clear()
    return jsonify(result), 200

# ── Управление ключами (существующие endpoints) ───────────────────────────────

def admin_check(data):
    return data.get("password") == ADMIN_PASSWORD

@app.route("/admin/add", methods=["POST"])
def add_key():
    data = request.json or {}
    if not admin_check(data):
        return jsonify({"error": "unauthorized"}), 403

    days = int(data.get("days", 30))
    expires_at = time.time() + days * 86400

    keys = load_keys()
    new_key = generate_key()
    keys[new_key] = {
        "active": True,
        "hwid": "",
        "note": data.get("note", ""),
        "expires_at": expires_at,
        "days": days,
        "created_at": time.time()
    }
    save_keys(keys)

    exp_date = datetime.datetime.fromtimestamp(expires_at).strftime("%d.%m.%Y")
    return jsonify({"key": new_key, "expires": exp_date, "days": days}), 200

@app.route("/admin/list", methods=["POST"])
def list_keys():
    data = request.json or {}
    if not admin_check(data):
        return jsonify({"error": "unauthorized"}), 403

    keys = load_keys()
    result = {}
    for k, v in keys.items():
        exp = v.get("expires_at", 0)
        days_left = max(0, int((exp - time.time()) / 86400)) if exp > 0 else 999
        result[k] = {
            **v,
            "days_left": days_left,
            "expires_str": datetime.datetime.fromtimestamp(exp).strftime("%d.%m.%Y") if exp > 0 else "∞"
        }
    return jsonify(result), 200

@app.route("/admin/disable", methods=["POST"])
def disable_key():
    data = request.json or {}
    if not admin_check(data): return jsonify({"error": "unauthorized"}), 403
    keys = load_keys()
    key = data.get("key", "").upper()
    if key not in keys: return jsonify({"error": "not found"}), 404
    keys[key]["active"] = False
    save_keys(keys)
    return jsonify({"ok": True}), 200

@app.route("/admin/reset_hwid", methods=["POST"])
def reset_hwid():
    data = request.json or {}
    if not admin_check(data): return jsonify({"error": "unauthorized"}), 403
    keys = load_keys()
    key = data.get("key", "").upper()
    if key not in keys: return jsonify({"error": "not found"}), 404
    keys[key]["hwid"] = ""
    save_keys(keys)
    return jsonify({"ok": True}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
