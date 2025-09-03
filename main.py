# main.py
from flask import Flask, request, jsonify
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
        SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
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


data_store = []  # in-memory history (most recent first is index 0)

def save_to_sheet(record: dict):
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
    return "✅ main.py running - POST telemetry to / or /api/data, GET /api/data or /api/sensors"


@app.route("/", methods=["POST"])
def receive_from_colab():
    incoming = request.get_json(silent=True)
    if not incoming or not isinstance(incoming, dict):
        return jsonify({"error": "No JSON object provided"}), 400

    # normalize
    incoming.setdefault("machine_id", MACHINE_ID)
    incoming.setdefault("ts", time.time())
    # store
    data_store.insert(0, incoming)  # newest-first
    save_to_sheet(incoming)
    return jsonify(incoming), 201


@app.route("/api/data", methods=["POST"])
def collect_data():
    return receive_from_colab()


@app.route("/api/data", methods=["GET"])
def get_data():
    # Always return list
    return jsonify(data_store)


@app.route("/api/sensors", methods=["GET"])
def generate_sensor_data():
    # Generate a sample reading and return as list
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
    # IMPORTANT: return an array so clients can always treat this as a list
    return jsonify([data])


@app.route("/health")
def health():
    return jsonify({"ok": True, "stored_rows": len(data_store)})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
