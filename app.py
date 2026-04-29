from flask import Flask, request, jsonify
import json, os, secrets, string, time

app = Flask(__name__)
KEYS_FILE = "keys.json"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "changeme123")

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

    # Проверка срока действия
    expires_at = entry.get("expires_at", 0)
    if expires_at > 0 and time.time() > expires_at:
        keys[key]["active"] = False
        save_keys(keys)
        return jsonify({"valid": False, "reason": "key_expired"}), 200

    # Привязка к HWID
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

def admin_check(data):
    return data.get("password") == ADMIN_PASSWORD

@app.route("/admin/add", methods=["POST"])
def add_key():
    data = request.json or {}
    if not admin_check(data):
        return jsonify({"error": "unauthorized"}), 403

    days = int(data.get("days", 30))  # по умолчанию 30 дней
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

    import datetime
    exp_date = datetime.datetime.fromtimestamp(expires_at).strftime("%d.%m.%Y")
    return jsonify({"key": new_key, "expires": exp_date, "days": days}), 200

@app.route("/admin/list", methods=["POST"])
def list_keys():
    data = request.json or {}
    if not admin_check(data):
        return jsonify({"error": "unauthorized"}), 403

    import datetime
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
