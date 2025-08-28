# main.py
from flask import Flask, request, jsonify
from starlette.middleware.wsgi import WSGIMiddleware
import json
import time
import os

# --- Create your Flask app ---
flask_app = Flask(__name__)

DATA_FILE = "data_store.jsonl"  # each line = one JSON record

def store_data(payload, path):
    """Append a JSON record with timestamp and request path to the data file."""
    entry = {
        "received_at": time.time(),
        "path": path,
        "data": payload
    }
    with open(DATA_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry

# Health check
@flask_app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "Service is running", "status": "ok"}), 200

# Accept POST to root (/)
@flask_app.route("/", methods=["POST"])
def root_post():
    payload = request.get_json(silent=True) or {}
    entry = store_data(payload, "/")
    return jsonify({"message": "Data stored successfully", "entry": entry}), 200

# Dedicated POST /process endpoint
@flask_app.route("/process", methods=["POST"])
def process():
    payload = request.get_json(silent=True) or {}
    entry = store_data(payload, "/process")
    return jsonify({"message": "Data stored successfully", "entry": entry}), 200

# Catch‑all POST handler for any other path
@flask_app.route("/<path:subpath>", methods=["POST"])
def catch_all_post(subpath):
    payload = request.get_json(silent=True) or {}
    entry = store_data(payload, f"/{subpath}")
    return jsonify({"message": "Data stored successfully", "entry": entry}), 200

# Custom 404 for non‑POST requests
@flask_app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Endpoint not found"}), 404

# --- Wrap Flask for ASGI servers (Uvicorn, Hypercorn, etc.) ---
app = WSGIMiddleware(flask_app)  # <— renamed to `app` so Uvicorn can find it

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))  # Render sets PORT automatically
    flask_app.run(host="0.0.0.0", port=port)
