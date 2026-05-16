import asyncio
from app.services.sheets_validator import validate_and_parse
from app.services.sheets_service import load_sheet

async def test_sheet():
    url = "https://docs.google.com/spreadsheets/d/1ZnbzfT4OtIAnJC475SH4sBuEw6MvQa5V5x1XzV5nBIg/edit?gid=0#gid=0"
    
    print("[TEST] Parsing URL...")
    try:
        parsed = validate_and_parse(url)
        print(f"OK - URL valid. Sheet ID: {parsed.spreadsheet_id}, GID: {parsed.gid}")
    except Exception as e:
        print(f"ERROR - URL parse failed: {e}")
        return
    
    print("[TEST] Attempting to load sheet (via service account auth)...")
    try:
        data = await load_sheet(url)
        print(f"OK - Sheet loaded successfully!")
        print(f"  - Sheet name: {data.get('sheet_name')}")
        print(f"  - Columns: {len(data.get('columns', []))} columns")
        print(f"  - Total rows: {data.get('total_rows')}")
        print(f"  - Preview rows loaded: {len(data.get('preview_rows', []))}")
        if data.get('columns'):
            cols = data['columns'][:5]
            print(f"  - Column names: {cols}{'...' if len(data['columns']) > 5 else ''}")
    except Exception as e:
        print(f"ERROR - Sheet load failed: {e}")

asyncio.run(test_sheet())

