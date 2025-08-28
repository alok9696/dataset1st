from flask import Flask, request, jsonify
from starlette.middleware.wsgi import WSGIMiddleware
import os
import psycopg2
import json
import time

flask_app = Flask(__name__)

def store_data(payload, path):
    """Insert a JSON record into the telemetry table."""
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO telemetry (path, data) VALUES (%s, %s)",
        (path, json.dumps(payload))
    )
    conn.commit()
    cur.close()
    conn.close()
    return {"received_at": time.time(), "path": path, "data": payload}

@flask_app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "Service is running", "status": "ok"}), 200

@flask_app.route("/", methods=["POST"])
def root_post():
    payload = request.get_json(silent=True) or {}
    entry = store_data(payload, "/")
    return jsonify({"message": "Data stored successfully", "entry": entry}), 200

@flask_app.route("/process", methods=["POST"])
def process():
    payload = request.get_json(silent=True) or {}
    entry = store_data(payload, "/process")
    return jsonify({"message": "Data stored successfully", "entry": entry}), 200

@flask_app.route("/<path:subpath>", methods=["POST"])
def catch_all_post(subpath):
    payload = request.get_json(silent=True) or {}
    entry = store_data(payload, f"/{subpath}")
    return jsonify({"message": "Data stored successfully", "entry": entry}), 200

@flask_app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Endpoint not found"}), 404

# Wrap for ASGI
app = WSGIMiddleware(flask_app)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)
