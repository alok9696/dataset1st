from flask import Flask, request, jsonify
import os
import json
import gspread
from google.oauth2.service_account import Credentials
import time
import random

app = Flask(__name__)

# ===============================
# Config
# ===============================
MACHINE_ID = os.getenv("MACHINE_ID", "TEST_01")
SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME", "SensorData")

# ===============================
# Google Sheets Setup
# ===============================
creds_json = os.getenv("GOOGLE_CREDENTIALS")
if not creds_json:
    raise Exception("GOOGLE_CREDENTIALS environment variable is not set.")

creds_dict = json.loads(creds_json)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
gc = gspread.authorize(creds)

try:
    sheet = gc.open(SHEET_NAME).sheet1
except gspread.SpreadsheetNotFound:
    raise Exception(
        f"Google Sheet '{SHEET_NAME}' not found. Create it and share with the service account email."
    )

# ===============================
# Local Store
# ===============================
data_store = []


# ===============================
# Helpers
# ===============================
def save_to_sheet(data: dict):
    """Ensure headers exist and insert new row below header."""
    headers = sheet.row_values(1)

    # If sheet is empty, create headers first
    if not headers:
        headers = list(data.keys())
        sheet.insert_row(headers, 1)

    # Create row in same header order
    row = [data.get(h, "") for h in headers]

    # Insert new data right below header (row 2)
    sheet.insert_row(row, 2)


# ===============================
# Routes
# ===============================
@app.route("/", methods=["POST"])
def receive_from_colab():
    """
    Accepts raw POSTs from Colab (or simulator) directly to `/`
    """
    try:
        incoming = request.get_json()
        if not incoming:
            return jsonify({"error": "No JSON data received"}), 400

        # Add machine_id + timestamp if missing
        if "machine_id" not in incoming:
            incoming["machine_id"] = MACHINE_ID
        if "ts" not in incoming:
            incoming["ts"] = time.time()

        # Save locally
        data_store.append(incoming)

        # Save to Google Sheets (new at top, below header)
        save_to_sheet(incoming)

        return jsonify({"status": "success", "data": incoming}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/data", methods=["POST"])
def collect_data():
    """Explicit endpoint for Colab/simulated devices"""
    return receive_from_colab()


@app.route("/api/data", methods=["GET"])
def get_data():
    """Return all collected in-memory data"""
    return jsonify(data_store)


@app.route("/api/sensors", methods=["GET"])
def generate_sensor_data():
    """Generate random sensor data and log to Google Sheets"""
    data = {
        "machine_id": MACHINE_ID,
        "ts": time.time(),
        "temp": 40 + random.random() * 10,
        "surrounding_temp": 25 + random.random() * 5,
        "vibration_rms": random.random() * 0.5,
        "rpm": 1000 + int(random.random() * 400),
        "torque": 10 + random.random() * 190,
    }

    # Save locally
    data_store.append(data)

    # Save to Google Sheets
    save_to_sheet(data)

    return jsonify(data)


@app.route("/", methods=["GET"])
def home():
    return "✅ Flask API is running. Use POST / or POST /api/data to send telemetry. Data is stored in Google Sheets!"


# ===============================
# Run Flask
# ===============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
