from flask import Flask, request, jsonify
import os
import json
import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)

# --- Google Sheets Setup ---
# Credentials JSON is stored in environment variable GOOGLE_SHEETS_CREDS
creds_json = os.getenv("GOOGLE_SHEETS_CREDS")

if not creds_json:
    raise Exception("GOOGLE_SHEETS_CREDS environment variable is not set.")

creds_dict = json.loads(creds_json)

creds = Credentials.from_service_account_info(
    creds_dict,
    scopes=["https://www.googleapis.com/auth/spreadsheets"]
)

gc = gspread.authorize(creds)

# Open Google Sheet (must exist beforehand)
SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME", "MyDataSheet")
try:
    sheet = gc.open(SHEET_NAME).sheet1
except gspread.SpreadsheetNotFound:
    raise Exception(f"Google Sheet '{SHEET_NAME}' not found. Create it first.")


# --- Store incoming data ---
data_store = []


@app.route("/api/data", methods=["POST"])
def collect_data():
    """
    Endpoint for Colab to send data
    Example in Colab:
    requests.post("http://<server_ip>:5000/api/data", json={"temperature":25,"humidity":60})
    """
    try:
        incoming = request.get_json()
        if not incoming:
            return jsonify({"error": "No JSON data received"}), 400

        # Save to in-memory store
        data_store.append(incoming)

        # Write to Google Sheet
        headers = sheet.row_values(1)  # First row as header
        if not headers:  # If sheet is empty, create headers
            headers = list(incoming.keys())
            sheet.append_row(headers)

        row = [incoming.get(h, "") for h in headers]
        sheet.append_row(row)

        return jsonify({"status": "success", "data": incoming}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/data", methods=["GET"])
def get_data():
    """Returns all collected data via API"""
    return jsonify(data_store)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
