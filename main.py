from flask import Flask, jsonify, request
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os
import time
import random

app = Flask(__name__)

# ===============================
# Config
# ===============================
MACHINE_ID = "TEST_01"
SHEET_NAME = "SensorData"   # must match your Google Sheet name!

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

def store_in_google_sheets(data):
    client = get_gspread_client()
    sheet = client.open(SHEET_NAME).sheet1
    sheet.append_row([
        data.get("machine_id"),
        data.get("ts"),
        data.get("temp"),
        data.get("surrounding_temp"),
        data.get("vibration_rms"),
        data.get("rpm"),
        data.get("torque"),
    ])

# ===============================
# API Routes
# ===============================
@app.route("/api/collect", methods=["POST"])
def collect_data():
    data = request.json
    if data:
        store_in_google_sheets(data)
        return jsonify({"status": "success", "data": data})
    return jsonify({"status": "error", "message": "No data received"}), 400

@app.route("/")
def home():
    return "✅ Flask API is running and logging data to Google Sheets!"

# ===============================
# Run Flask
# ===============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
