from flask import Flask, jsonify
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os
import datetime
import time
import random

app = Flask(__name__)

# ===============================
# Config
# ===============================
MACHINE_ID = "TEST_01"
SHEET_NAME = "SensorData"   # <-- make sure this matches your Google Sheet name!

# ===============================
# Load Google Sheets credentials
# ===============================
def get_gspread_client():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    if not creds_json:
        raise Exception("Missing GOOGLE_CREDENTIALS environment variable!")

    creds_dict = json.loads(creds_json)

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

# ===============================
# Example Sensor Data
# ===============================
def get_sensor_data():
    return {
        "machine_id": MACHINE_ID,
        "ts": time.time(),
        "temp": 40 + random.random() * 10,          # °C
        "surrounding_temp": 25 + random.random() * 5,  # °C
        "vibration_rms": random.random() * 0.5,     # g
        "rpm": 1000 + int(random.random() * 400),   # rev/min
        "torque": 10 + random.random() * 190        # Nm
    }

# ===============================
# Store Data in Google Sheets
# ===============================
def store_in_google_sheets(data):
    client = get_gspread_client()
    sheet = client.open(SHEET_NAME).sheet1  # open by sheet name
    sheet.append_row([
        data["machine_id"],
        data["ts"],
        data["temp"],
        data["surrounding_temp"],
        data["vibration_rms"],
        data["rpm"],
        data["torque"],
    ])

# ===============================
# API Routes
# ===============================
@app.route("/api/sensors", methods=["GET"])
def sensors():
    data = get_sensor_data()
    store_in_google_sheets(data)
    return jsonify(data)

@app.route("/")
def home():
    return "✅ Flask API is running and logging data to Google Sheets!"

# ===============================
# Run Flask
# ===============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
