from flask import Flask, request, jsonify
import json
import os
import secrets
import string

app = Flask(__name__)
KEYS_FILE = "keys.json"

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

# Проверка ключа — вызывается из мода
@app.route("/check", methods=["GET"])
def check_key():
    key   = request.args.get("key", "").strip().upper()
    hwid  = request.args.get("hwid", "").strip()

    if not key or not hwid:
        return jsonify({"valid": False, "reason": "missing_params"}), 400

    keys = load_keys()

    if key not in keys:
        return jsonify({"valid": False, "reason": "invalid_key"}), 200

    entry = keys[key]

    if not entry.get("active", False):
        return jsonify({"valid": False, "reason": "key_disabled"}), 200

    # Привязка к HWID
    bound_hwid = entry.get("hwid", "")
    if bound_hwid == "":
        # Первый запуск — привязываем HWID
        keys[key]["hwid"] = hwid
        save_keys(keys)
        return jsonify({"valid": True, "message": "Key activated"}), 200

    if bound_hwid != hwid:
        return jsonify({"valid": False, "reason": "wrong_hwid"}), 200

    return jsonify({"valid": True, "message": "OK"}), 200

# Административные endpoints — защищены паролем
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "changeme123")

@app.route("/admin/add", methods=["POST"])
def add_key():
    data = request.json or {}
    if data.get("password") != ADMIN_PASSWORD:
        return jsonify({"error": "unauthorized"}), 403

    keys = load_keys()
    new_key = generate_key()
    keys[new_key] = {"active": True, "nick": "", "note": data.get("note", "")}
    save_keys(keys)
    return jsonify({"key": new_key}), 200

@app.route("/admin/list", methods=["POST"])
def list_keys():
    data = request.json or {}
    if data.get("password") != ADMIN_PASSWORD:
        return jsonify({"error": "unauthorized"}), 403
    return jsonify(load_keys()), 200

@app.route("/admin/disable", methods=["POST"])
def disable_key():
    data = request.json or {}
    if data.get("password") != ADMIN_PASSWORD:
        return jsonify({"error": "unauthorized"}), 403
    keys = load_keys()
    key = data.get("key", "").upper()
    if key not in keys:
        return jsonify({"error": "not found"}), 404
    keys[key]["active"] = False
    save_keys(keys)
    return jsonify({"ok": True}), 200

@app.route("/admin/reset_nick", methods=["POST"])
def reset_nick():
    data = request.json or {}
    if data.get("password") != ADMIN_PASSWORD:
        return jsonify({"error": "unauthorized"}), 403
    keys = load_keys()
    key = data.get("key", "").upper()
    if key not in keys:
        return jsonify({"error": "not found"}), 404
    keys[key]["hwid"] = ""
    save_keys(keys)
    return jsonify({"ok": True}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
