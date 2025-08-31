from flask import Flask, request, jsonify, render_template_string
from starlette.middleware.wsgi import WSGIMiddleware
import os
import psycopg2
import json
import time
from psycopg2.extras import Json, RealDictCursor

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
            (path, Json(payload))
        )
        conn.commit()
        cur.close()
        conn.close()
        return {"received_at": time.time(), "path": path, "data": payload}
    except Exception as e:
        flask_app.logger.error(f"Error storing data: {e}")
        raise

def fetch_data(limit=100):
    """Fetch latest telemetry records."""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM telemetry ORDER BY received_at DESC LIMIT %s", (limit,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        flask_app.logger.error(f"Error fetching data: {e}")
        return []

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

# --- New Routes to VIEW data ---
@flask_app.route("/data", methods=["GET"])
def get_data():
    """Return stored telemetry as JSON (latest 100 rows)."""
    rows = fetch_data()
    return jsonify(rows), 200

@flask_app.route("/dashboard", methods=["GET"])
def dashboard():
    """Simple HTML dashboard to view telemetry data."""
    rows = fetch_data()
    html = """
    <h2>Telemetry Dashboard</h2>
    <table border="1" cellpadding="5">
        <tr>
            <th>ID</th>
            <th>Received At</th>
            <th>Path</th>
            <th>Data</th>
        </tr>
        {% for row in rows %}
        <tr>
            <td>{{row.id}}</td>
            <td>{{row.received_at}}</td>
            <td>{{row.path}}</td>
            <td><pre>{{row.data | tojson(indent=2)}}</pre></td>
        </tr>
        {% endfor %}
    </table>
    """
    return render_template_string(html, rows=rows)

# --- Error Handlers ---
@flask_app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Endpoint not found"}), 404

@flask_app.errorhandler(Exception)
def handle_exception(e):
    flask_app.logger.error(f"Unhandled error: {e}")
    return jsonify({"error": "Internal server error"}), 500

# --- Ensure DB table exists at import time ---
init_db()

# Wrap for ASGI
app = WSGIMiddleware(flask_app)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)
