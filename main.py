from flask import Flask, request, jsonify
from starlette.middleware.wsgi import WSGIMiddleware
import os
import psycopg2
import json
import time
from psycopg2.extras import Json

flask_app = Flask(__name__)

# --- Database helpers ---
def get_db_connection():
    """Get a new database connection using DATABASE_URL."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL environment variable is not set")
    return psycopg2.connect(db_url, sslmode="require")

def init_db():
    """Create telemetry table if it doesn't exist."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS telemetry (
                id SERIAL PRIMARY KEY,
                received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                path TEXT,
                data JSONB
            )
        """)
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        flask_app.logger.error(f"Database initialization failed: {e}")
        raise

def store_data(payload, path):
    """Insert a JSON record into the telemetry table."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO telemetry (path, data) VALUES (%s, %s)",
            (path, Json(payload))  # Json() handles serialization safely
        )
        conn.commit()
        cur.close()
        conn.close()
        return {"received_at": time.time(), "path": path, "data": payload}
    except Exception as e:
        flask_app.logger.error(f"Error storing data: {e}")
        raise

# --- Routes ---
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

@flask_app.errorhandler(Exception)
def handle_exception(e):
    """Catch-all error handler to avoid exposing stack traces."""
    flask_app.logger.error(f"Unhandled error: {e}")
    return jsonify({"error": "Internal server error"}), 500

# --- Ensure DB table exists at import time ---
init_db()

# Wrap for ASGI
app = WSGIMiddleware(flask_app)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)
