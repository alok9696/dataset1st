from flask import Flask, request, jsonify
import json
import time
import os

app = Flask(__name__)

DATA_FILE = "data_store.jsonl"  # each line = one JSON record

def store_data(payload):
    """Append a JSON record with timestamp to the data file."""
    entry = {
        "received_at": time.time(),
        "data": payload
    }
    with open(DATA_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry

@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "Service is running", "status": "ok"}), 200

# Accept POST to root (/) for Colab sim compatibility
@app.route("/", methods=["POST"])
def root_post():
    payload = request.get_json(silent=True) or {}
    entry = store_data(payload)
    return jsonify({"message": "Data stored successfully", "entry": entry}), 200

# Dedicated POST /process endpoint
@app.route("/process", methods=["POST"])
def process():
    payload = request.get_json(silent=True) or {}
    entry = store_data(payload)
    return jsonify({"message": "Data stored successfully", "entry": entry}), 200

# Custom 404 handler
@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Endpoint not found"}), 404

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))  # Render sets PORT automatically
    app.run(host="0.0.0.0", port=port)
