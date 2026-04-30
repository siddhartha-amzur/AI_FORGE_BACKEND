import os
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

# Load .env
load_dotenv()

# Get JSON path from .env
json_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
sheet_id = os.getenv("GOOGLE_SHEET_ID")  # Add this to .env

# Create credentials
creds = Credentials.from_service_account_file(
    json_path,
    scopes=["https://www.googleapis.com/auth/spreadsheets"]
)

# Authorize client
client = gspread.authorize(creds)

# Open sheet by ID (doesn't require Drive API)
if sheet_id:
    sheet = client.open_by_key(sheet_id).sheet1
else:
    # Fallback: open by name (requires Drive API to be enabled)
    sheet = client.open("Test-AI-Forge").sheet1

# Fetch data
data = sheet.get_all_records()

print(data)