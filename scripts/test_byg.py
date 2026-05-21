import os
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

API_KEY = os.environ.get("RAPIDAPI_KEY", "")
HOST = "kiwi-com-flights-api.p.rapidapi.com"
url = f"https://{HOST}/api/v1/flights/search-oneway"

params = {
    'source': 'BYG',
    'destination': 'BCN',
    'departure_date': '2026-06-04',
    'adults': 1,
    'currency': 'PLN',
    'limit': 3
}

headers = {
    "x-rapidapi-key": API_KEY,
    "x-rapidapi-host": HOST,
}

print("Testing BYG->BCN Search...")
try:
    r = requests.get(url, headers=headers, params=params, timeout=15)
    print(f"Status: {r.status_code}")
    print(f"JSON: {r.json()}")
except Exception as e:
    print(f"Error: {e}")
