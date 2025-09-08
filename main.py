# main.py
from flask import Flask, request, jsonify, Response, stream_with_context
import os, json, time, random, logging

# Optional Google Sheets integration
try:
    import gspread
    from google.oauth2.service_account import Credentials
except Exception:
    gspread = None

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main-data")

MACHINE_ID = os.getenv("MACHINE_ID", "TEST_01")
SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME", "SensorData")
CREDS_JSON = os.getenv("GOOGLE_CREDENTIALS")

sheet = None
if gspread and CREDS_JSON:
    try:
        creds_dict = json.loads(CREDS_JSON)
        SCOPES = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        gc = gspread.authorize(creds)
        try:
            sheet = gc.open(SHEET_NAME).sheet1
            logger.info("Connected to Google Sheet: %s", SHEET_NAME)
        except gspread.SpreadsheetNotFound:
            logger.warning("Google Sheet '%s' not found. Sheet logging disabled.", SHEET_NAME)
            sheet = None
    except Exception as e:
        logger.exception("Google Sheets init failed, continuing without it: %s", e)
        sheet = None
else:
    if not gspread:
        logger.info("gspread not installed; skipping Google Sheets.")
    else:
        logger.info("GOOGLE_CREDENTIALS not provided; skipping Google Sheets.")

# in-memory history (newest-first)
data_store = []

def save_to_sheet(record: dict):
    """Write a record to Google Sheet if available"""
    if not sheet:
        return
    try:
        headers = sheet.row_values(1)
        if not headers:
            headers = list(record.keys())
            sheet.insert_row(headers, 1)
        row = [record.get(h, "") for h in headers]
        sheet.insert_row(row, 2)
    except Exception as e:
        logger.exception("Failed to write to Google Sheet: %s", e)

@app.after_request
def add_cors(resp):
    resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return resp

@app.route("/", methods=["GET"])
def home():
    return "✅ main.py running - POST telemetry to / or /api/data, GET /api/data (stream), /api/sensors, /api/stream, /dashboard"

@app.route("/", methods=["POST"])
def receive_from_colab():
    incoming = request.get_json(silent=True)
    if not incoming or not isinstance(incoming, dict):
        return jsonify({"error": "No JSON object provided"}), 400

    incoming.setdefault("machine_id", MACHINE_ID)
    incoming.setdefault("ts", time.time())

    data_store.insert(0, incoming)  # newest first
    save_to_sheet(incoming)

    return jsonify(incoming), 201

@app.route("/api/data", methods=["GET"])
def get_data():
    """Return the latest data instantly (newest-first JSON)"""
    if not data_store:
        return jsonify({"error": "no data yet"}), 404
    return jsonify(data_store[0])  # just the newest record


# 🔄 replaced normal /api/data GET with realtime streaming
@app.route("/api/data", methods=["GET"])
def get_data_stream():
    """Realtime streaming version of api/data"""
    def event_stream():
        last_size = 0
        while True:
            if len(data_store) > last_size:
                new_data = data_store[0]
                yield f"data: {json.dumps(new_data)}\n\n"
                last_size = len(data_store)
            time.sleep(0.2)  # check frequently
    return Response(stream_with_context(event_stream()), mimetype="text/event-stream")

@app.route("/api/sensors", methods=["GET"])
def generate_sensor_data():
    """Generate a random reading"""
    data = {
        "machine_id": MACHINE_ID,
        "ts": int(time.time()),
        "temp": round(40 + random.random() * 10, 2),
        "surrounding_temp": round(25 + random.random() * 5, 2),
        "vibration_rms": round(random.random() * 0.5, 3),
        "rpm": int(1000 + random.random() * 400),
        "torque": round(10 + random.random() * 190, 2),
    }
    data_store.insert(0, data)
    save_to_sheet(data)
    return jsonify([data])

@app.route("/api/stream")
def stream():
    """Server-Sent Events (SSE) endpoint for live data"""
    def event_stream():
        last_size = 0
        while True:
            if len(data_store) > last_size:
                new_data = data_store[0]
                yield f"data: {json.dumps(new_data)}\n\n"
                last_size = len(data_store)
            time.sleep(0.5)
    return Response(stream_with_context(event_stream()), mimetype="text/event-stream")

@app.route("/dashboard")
def dashboard():
    """Simple HTML dashboard page with auto-updating live data"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
      <title>Live Sensor Dashboard</title>
      <style>
        body { font-family: Arial, sans-serif; background: #f7f7f7; padding: 20px; }
        #log { background: white; padding: 10px; border-radius: 8px; max-height: 400px; overflow-y: auto; }
        .entry { padding: 5px; border-bottom: 1px solid #ddd; }
      </style>
    </head>
    <body>
      <h1>📡 Live Sensor Dashboard</h1>
      <div id="log"></div>

      <script>
        const logDiv = document.getElementById("log");
        const evtSource = new EventSource("/api/stream");

        evtSource.onmessage = (event) => {
          const data = JSON.parse(event.data);
          const entry = document.createElement("div");
          entry.className = "entry";
          entry.innerHTML = "<b>" + new Date(data.ts * 1000).toLocaleTimeString() + "</b> " +
                            "| Temp: " + (data.temp ?? "-") + "°C " +
                            "| RPM: " + (data.rpm ?? "-") + 
                            " | Torque: " + (data.torque ?? "-");
          logDiv.prepend(entry);
        };
      </script>
    </body>
    </html>
    """

@app.route("/health")
def health():
    return jsonify({"ok": True, "stored_rows": len(data_store)})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)

