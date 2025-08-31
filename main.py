from flask import Flask, request, jsonify, render_template_string, Response
from starlette.middleware.wsgi import WSGIMiddleware
import os
import psycopg2
import time
import csv
import io
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

def fetch_all_data():
    """Fetch all telemetry records (for download)."""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM telemetry ORDER BY received_at DESC")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        flask_app.logger.error(f"Error fetching all data: {e}")
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

# --- New Routes to VIEW & DOWNLOAD data ---
@flask_app.route("/data", methods=["GET"])
def get_data():
    """Return stored telemetry as JSON (latest 100 rows)."""
    rows = fetch_data()
    return jsonify(rows), 200

@flask_app.route("/download/json", methods=["GET"])
def download_json():
    """Download all telemetry data as JSON file."""
    rows = fetch_all_data()
    return Response(
        response=jsonify(rows).get_data(as_text=True),
        mimetype="application/json",
        headers={"Content-Disposition": "attachment;filename=telemetry.json"}
    )

@flask_app.route("/download/csv", methods=["GET"])
def download_csv():
    """Download all telemetry data as CSV file."""
    rows = fetch_all_data()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "received_at", "path", "data"])  # header
    for row in rows:
        writer.writerow([row["id"], row["received_at"], row["path"], json.dumps(row["data"])])
    return Response(
        response=output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=telemetry.csv"}
    )

@flask_app.route("/dashboard", methods=["GET"])
def dashboard():
    """Real-time telemetry dashboard without full page reload."""
    html = """
    <h2>Telemetry Dashboard (Live Data)</h2>
    <button onclick="window.location.href='/download/json'">Download JSON</button>
    <button onclick="window.location.href='/download/csv'">Download CSV</button>
    <br><br>
    <table id="data-table" border="1" cellpadding="5">
        <thead>
            <tr>
                <th>ID</th>
                <th>Received At</th>
                <th>Path</th>
                <th>Data</th>
            </tr>
        </thead>
        <tbody></tbody>
    </table>

    <script>
        async function fetchData() {
            try {
                let response = await fetch('/data');
                let rows = await response.json();

                let tbody = document.querySelector("#data-table tbody");
                tbody.innerHTML = "";  // clear old data

                rows.forEach(row => {
                    let tr = document.createElement("tr");

                    tr.innerHTML = `
                        <td>${row.id}</td>
                        <td>${row.received_at}</td>
                        <td>${row.path}</td>
                        <td><pre>${JSON.stringify(row.data, null, 2)}</pre></td>
                    `;
                    tbody.appendChild(tr);
                });
            } catch (err) {
                console.error("Error fetching data:", err);
            }
        }

        // fetch immediately
        fetchData();

        // update every 5 seconds
        setInterval(fetchData, 5000);
    </script>
    """
    return render_template_string(html)

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
